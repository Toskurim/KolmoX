from .base import BaseDomainEngine
import zstandard as zstd
import numpy as np
"""
KolmoX Extended Domain Preconditioning Engines (v1.1.0)
Bit-exact, high-throughput transforms with C-acceleration and NumPy fallback.
"""

import operator
import re
import struct
import numpy as np
from typing import Tuple, List

try:
    from kolmox.core import fast_transforms
    HAS_C_EXT = True
except ImportError:
    HAS_C_EXT = False


class ScientificFloatEngine(BaseDomainEngine):
    @staticmethod
    def transform_f32_byte_plane(raw_data: bytes) -> bytes:
        num_bytes = len(raw_data)
        if num_bytes % 4 != 0 or num_bytes == 0:
            return raw_data
        if HAS_C_EXT:
            return fast_transforms.transpose_f32(raw_data)
        arr = np.frombuffer(raw_data, dtype=np.uint8).reshape(-1, 4)
        return arr.T.tobytes()

    @staticmethod
    def inverse_f32_byte_plane(sliced_data: bytes) -> bytes:
        num_bytes = len(sliced_data)
        if num_bytes % 4 != 0 or num_bytes == 0:
            return sliced_data
        if HAS_C_EXT:
            return fast_transforms.untranspose_f32(sliced_data)
        n = num_bytes // 4
        arr = np.frombuffer(sliced_data, dtype=np.uint8).reshape(4, n)
        return arr.T.tobytes()


class AudioPCMEngine(BaseDomainEngine):
    @staticmethod
    def is_wav(data: bytes) -> bool:
        return len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WAVE"

    # Formato del sidecar da v1.3.1. Il precedente era il solo header WAV:
    # la coda di PCM non multipla di 4 byte e qualunque chunk RIFF dopo `data`
    # (LIST/INFO, cue, id3 ...) andavano persi. KMXA2 li conserva entrambi.
    # Un sidecar legacy inizia con b"RIFF" oppure e' vuoto, quindi non e'
    # confondibile col marcatore.
    AUX_MAGIC = b"KMXA2"

    @staticmethod
    def _find_data_chunk(raw_data: bytes):
        """(inizio, fine) del payload del chunk `data`, percorrendo i chunk RIFF.

        Cercare b"data" con find() puo' cadere dentro un altro chunk; qui si
        salta da un chunk all'altro con le loro taglie dichiarate.
        """
        pos = 12
        n = len(raw_data)
        while pos + 8 <= n:
            cid = raw_data[pos : pos + 4]
            (size,) = struct.unpack_from("<I", raw_data, pos + 4)
            start = pos + 8
            if cid == b"data":
                return start, min(start + size, n)
            pos = start + size + (size & 1)
        return None

    @staticmethod
    def transform_stereo_pcm16(raw_data: bytes) -> Tuple[bytes, bytes]:
        if AudioPCMEngine.is_wav(raw_data):
            span = AudioPCMEngine._find_data_chunk(raw_data)
            if span is None:
                raise ValueError("WAV senza chunk data")
            start, end = span
            header = raw_data[:start]
            pcm = raw_data[start:end]
            trailer = raw_data[end:]
        else:
            header = b""
            pcm = raw_data
            trailer = b""

        num_samples = len(pcm) // 4
        if num_samples == 0:
            raise ValueError("PCM troppo corto per la trasformazione stereo")
        tail = pcm[num_samples * 4 :]
        aux = (
            AudioPCMEngine.AUX_MAGIC
            + struct.pack("<III", len(header), len(tail), len(trailer))
            + header
            + tail
            + trailer
        )
        return aux, AudioPCMEngine._encode_samples(pcm[: num_samples * 4])

    @staticmethod
    def _encode_samples(pcm: bytes) -> bytes:
        samples = np.frombuffer(pcm, dtype=np.int16).reshape(-1, 2)
        left = samples[:, 0].astype(np.int32)
        right = samples[:, 1].astype(np.int32)

        diff = (left - right).astype(np.int16)
        delta_left = np.empty_like(left, dtype=np.int16)
        delta_left[0] = left[0]
        delta_left[1:] = (left[1:] - left[:-1]).astype(np.int16)

        return delta_left.tobytes() + diff.tobytes()

    @staticmethod
    def inverse_stereo_pcm16(header: bytes, processed: bytes) -> bytes:
        if header.startswith(AudioPCMEngine.AUX_MAGIC):
            off = len(AudioPCMEngine.AUX_MAGIC)
            h_len, t_len, tr_len = struct.unpack_from("<III", header, off)
            off += 12
            if off + h_len + t_len + tr_len != len(header):
                raise ValueError("KMXA2: sidecar incoerente")
            wav_header = header[off : off + h_len]
            tail = header[off + h_len : off + h_len + t_len]
            trailer = header[off + h_len + t_len :]
            if len(processed) % 4:
                raise ValueError("KMXA2: payload PCM non multiplo di 4")
            return AudioPCMEngine._legacy_inverse(wav_header, processed) + tail + trailer
        return AudioPCMEngine._legacy_inverse(header, processed)

    @staticmethod
    def _legacy_inverse(header: bytes, processed: bytes) -> bytes:
        num_samples = len(processed) // 4
        if num_samples == 0:
            return header + processed

        delta_left = np.frombuffer(processed[: num_samples * 2], dtype=np.int16).astype(np.int32)
        diff = np.frombuffer(processed[num_samples * 2 :], dtype=np.int16).astype(np.int32)

        left = np.cumsum(delta_left).astype(np.int16)
        right = (left.astype(np.int32) - diff).astype(np.int16)

        stereo = np.empty((num_samples, 2), dtype=np.int16)
        stereo[:, 0] = left
        stereo[:, 1] = right

        return header + stereo.tobytes()


class GCodeEngine(BaseDomainEngine):
    @staticmethod
    def is_gcode(data: bytes) -> bool:
        sample = data[:1024].decode("utf-8", errors="ignore").upper()
        return "G1 " in sample or "G0 " in sample or "M104" in sample

    # Numero di riga RS-274/NGC. Nel G-code reale segue spesso direttamente la
    # parola d'asse senza spazio: "N430X[...]" e non "N430 X...".
    _N_WORD = re.compile(rb"^N(\d+)")
    # G0/G1 espliciti, senza catturare G10/G17/...
    _EXPLICIT_MOVE = re.compile(rb"^G[01](?![0-9])")
    # Riga modale: il comando e' stato dichiarato prima e persiste, quindi la
    # riga inizia direttamente con una parola d'asse.
    _MODAL_MOVE = re.compile(rb"^[XYZ]")
    # Un valore estraibile deve essere un numero letterale. Le espressioni
    # parametriche di LinuxCNC (X[#<xscale>*52.972]) restano nel template:
    # smontarle richiederebbe di modellare la sintassi di quel dialetto.
    _NUMERIC = re.compile(rb"^[-+]?[0-9]*\.?[0-9]+$")

    @classmethod
    def _split_line_number(cls, line: bytes) -> Tuple[bytes, bytes]:
        """Separa il numero di riga opzionale. Ritorna (numero o b"", resto)."""
        m = cls._N_WORD.match(line)
        if not m:
            return b"", line
        return m.group(1), line[m.end():]

    @classmethod
    def transform(cls, raw_data: bytes) -> Tuple[bytes, bytes]:
        lines = raw_data.split(b"\n")
        template_lines = []
        vals_x, vals_y, vals_z, vals_n = [], [], [], []

        for line in lines:
            n_val, body = cls._split_line_number(line)
            is_move = bool(cls._EXPLICIT_MOVE.match(body) or cls._MODAL_MOVE.match(body))

            if is_move:
                new_parts = []
                for p in body.split(b" "):
                    axis = p[:1]
                    value = p[1:]
                    if axis in (b"X", b"Y", b"Z") and cls._NUMERIC.match(value):
                        {b"X": vals_x, b"Y": vals_y, b"Z": vals_z}[axis].append(value)
                        new_parts.append(axis + b"\x00")
                    else:
                        new_parts.append(p)
                body = b" ".join(new_parts)

            if n_val:
                vals_n.append(n_val)
                body = b"N\x00" + body
            template_lines.append(body)

        template = b"\n".join(template_lines)
        return template, cls._pack_coords(vals_x, vals_y, vals_z, vals_n)

    # Il vecchio formato separava le sezioni con una riga "---", ma si rompe
    # quando una sezione e' vuota: b"---\n---\n---\n10".split(b"\n---\n") ne
    # restituisce due invece di quattro. Il formato KMXG2 dichiara i conteggi
    # in testa, quindi le sezioni vuote non sono ambigue. I coords scritti col
    # vecchio schema restano leggibili.
    COORDS_MAGIC = b"KMXG2"
    _COORDS_HEADER_LEN = 5 + 16

    @classmethod
    def _pack_coords(cls, vals_x, vals_y, vals_z, vals_n) -> bytes:
        counts = struct.pack(">IIII", len(vals_x), len(vals_y), len(vals_z), len(vals_n))
        body = b"\n".join(vals_x + vals_y + vals_z + vals_n)
        return cls.COORDS_MAGIC + counts + body

    @classmethod
    def _unpack_coords(cls, coords: bytes):
        if coords.startswith(cls.COORDS_MAGIC):
            nx, ny, nz, nn = struct.unpack(">IIII", coords[5:cls._COORDS_HEADER_LEN])
            body = coords[cls._COORDS_HEADER_LEN:]
            total = nx + ny + nz + nn
            vals = body.split(b"\n") if total else []
            i = 0
            out = []
            for n in (nx, ny, nz, nn):
                out.append(vals[i:i + n])
                i += n
            return out

        # Percorso legacy: sezioni separate da "---", nessun numero di riga.
        sections = coords.split(b"\n---\n")
        get = lambda k: sections[k].split(b"\n") if len(sections) > k and sections[k] else []
        return [get(0), get(1), get(2), []]

    @classmethod
    def inverse(cls, template: bytes, coords: bytes) -> bytes:
        if not coords:
            return template
        vals_x, vals_y, vals_z, vals_n = cls._unpack_coords(coords)

        ix = iy = iz = i_n = 0
        out_lines = []

        for line in template.split(b"\n"):
            if b"\x00" not in line:
                out_lines.append(line)
                continue

            prefix = b""
            if line.startswith(b"N\x00"):
                if i_n < len(vals_n):
                    prefix = b"N" + vals_n[i_n]
                    i_n += 1
                line = line[2:]

            new_parts = []
            for p in line.split(b" "):
                if p == b"X\x00" and ix < len(vals_x):
                    new_parts.append(b"X" + vals_x[ix]); ix += 1
                elif p == b"Y\x00" and iy < len(vals_y):
                    new_parts.append(b"Y" + vals_y[iy]); iy += 1
                elif p == b"Z\x00" and iz < len(vals_z):
                    new_parts.append(b"Z" + vals_z[iz]); iz += 1
                else:
                    new_parts.append(p)
            out_lines.append(prefix + b" ".join(new_parts))

        return b"\n".join(out_lines)


class PointCloudEngine(BaseDomainEngine):
    """Nuvole di punti ASCII (.xyz, .pts) e, piu' in generale, tabelle numeriche
    separate da spazi o tab.

    Formato KMXP2 (da v1.3.1). Il formato precedente teneva solo le righe con
    esattamente tre campi e le ricostruiva con spazi singoli e "\\n": una
    quarta colonna, un commento, un header, un tab o un CRLF andavano persi.
    KMXP2 e' una biiezione per costruzione:

    - il file si divide su b"\\n"; ogni riga e' "di dati" solo se e' la
      giustapposizione esatta di campi numerici con un unico separatore
      (spazio o tab), senza spazi iniziali/finali ne' separatori doppi, con un
      eventuale "\\r" finale. Tutto il resto e' una riga "verbatim" conservata
      byte per byte;
    - ogni riga di dati e' descritta da una forma (numero di colonne,
      separatore, CR): la sequenza delle forme va nel manifest, i valori vanno
      nel payload colonna per colonna, che e' cio' che Zstd sfrutta.

    I container scritti col vecchio formato restano leggibili.
    """

    MANIFEST_MAGIC = b"KMXP2"
    _MAX_SHAPES = 255  # l'id di forma sta in un byte; 0 = riga verbatim

    # Per la biiezione basta che i campi siano non vuoti e senza "\n"; che
    # siano numeri serve solo a scegliere righe che valga la pena separare in
    # colonne. Il controllo usa translate() (C puro) invece di una regex per
    # campo: e' la parte calda della trasformazione.
    _NUMERIC_CHARS = b"0123456789.+-eE"
    _DEL_SPACE = _NUMERIC_CHARS + b" "
    _DEL_TAB = _NUMERIC_CHARS + b"\t"

    @classmethod
    def _data_shape(cls, line: bytes):
        """(campi, separatore, cr) se la riga e' di dati, altrimenti None."""
        cr = line.endswith(b"\r")
        body = line[:-1] if cr else line
        if b" " in body:
            if b"\t" in body or body.translate(None, cls._DEL_SPACE):
                return None
            sep = b" "
        elif b"\t" in body:
            if body.translate(None, cls._DEL_TAB):
                return None
            sep = b"\t"
        else:
            return None
        fields = body.split(sep)
        if b"" in fields:  # separatori doppi, iniziali o finali
            return None
        return fields, sep, cr

    @classmethod
    def _uniform_fast_path(cls, raw_data: bytes, lines: List[bytes]):
        """Colonne del caso comune (tutte le righe con la stessa forma, niente
        CR, eventuale newline finale), calcolate con operazioni sull'intero
        buffer invece che riga per riga. None se il caso non si applica: allora
        decide il percorso generale, che produce lo stesso identico formato.
        """
        if b"\r" in raw_data:
            return None
        has_space = b" " in raw_data
        has_tab = b"\t" in raw_data
        if has_space == has_tab:
            return None
        sep = b" " if has_space else b"\t"
        body_lines = lines[:-1] if lines and lines[-1] == b"" else lines
        if not body_lines:
            return None
        delete = cls._DEL_SPACE if has_space else cls._DEL_TAB
        if raw_data.translate(None, delete + b"\n"):
            return None
        counts = set(map(operator.methodcaller("count", sep), body_lines))
        if len(counts) != 1:
            return None
        ncols = counts.pop() + 1
        if ncols < 2:
            return None
        flat = sep.join(body_lines).split(sep)
        if b"" in flat:
            return None
        columns = [flat[j::ncols] for j in range(ncols)]
        kinds = b"\x01" * len(body_lines) + (b"\x00" if len(body_lines) < len(lines) else b"")
        verbatim = [b""] if len(body_lines) < len(lines) else []
        return [(ncols, sep, False)], bytearray(kinds), columns, verbatim

    @classmethod
    def transform_xyz_ascii(cls, raw_data: bytes) -> Tuple[bytes, bytes]:
        lines = raw_data.split(b"\n")
        fast = cls._uniform_fast_path(raw_data, lines)
        if fast is not None:
            shapes, kinds, columns, verbatim = fast
            return cls._pack(len(lines), shapes, kinds, columns, verbatim)
        shape_ids = {}
        shapes = []
        kinds = bytearray()
        columns: List[List[bytes]] = []
        verbatim: List[bytes] = []

        for line in lines:
            parsed = cls._data_shape(line)
            if parsed is None:
                kinds.append(0)
                verbatim.append(line)
                continue
            fields, sep, cr = parsed
            key = (len(fields), sep, cr)
            sid = shape_ids.get(key)
            if sid is None:
                if len(shapes) >= cls._MAX_SHAPES:
                    raise ValueError("POINTCLOUD_XYZ: troppe forme di riga distinte")
                shapes.append(key)
                sid = shape_ids[key] = len(shapes)
            kinds.append(sid)
            while len(columns) < len(fields):
                columns.append([])
            for j, f in enumerate(fields):
                columns[j].append(f)

        if not shapes:
            raise ValueError("POINTCLOUD_XYZ: nessuna riga numerica, niente da trasformare")
        return cls._pack(len(lines), shapes, kinds, columns, verbatim)

    @classmethod
    def _pack(cls, n_lines, shapes, kinds, columns, verbatim) -> Tuple[bytes, bytes]:
        verbatim_blob = b"\n".join(verbatim)
        manifest = bytearray(cls.MANIFEST_MAGIC)
        manifest += struct.pack("<IHH", n_lines, len(shapes), len(columns))
        for ncols, sep, cr in shapes:
            manifest += struct.pack("<HBB", ncols, sep[0], int(cr))
        for col in columns:
            manifest += struct.pack("<I", len(col))
        manifest += struct.pack("<I", len(verbatim))
        manifest += kinds
        manifest += verbatim_blob

        payload = b"\n".join(v for col in columns for v in col)
        return bytes(manifest), payload

    @classmethod
    def inverse_xyz_ascii(cls, manifest: bytes, payload: bytes) -> bytes:
        if manifest.startswith(cls.MANIFEST_MAGIC):
            return cls._inverse_kmxp2(manifest, payload)
        return cls._inverse_legacy(manifest, payload)

    @classmethod
    def _inverse_kmxp2(cls, manifest: bytes, payload: bytes) -> bytes:
        off = len(cls.MANIFEST_MAGIC)
        n_lines, n_shapes, n_cols = struct.unpack_from("<IHH", manifest, off)
        off += 8
        shapes = [None]
        for _ in range(n_shapes):
            ncols, sep, cr = struct.unpack_from("<HBB", manifest, off)
            off += 4
            shapes.append((ncols, bytes([sep]), b"\r" if cr else b""))
        col_counts = []
        for _ in range(n_cols):
            col_counts.append(struct.unpack_from("<I", manifest, off)[0])
            off += 4
        (n_verbatim,) = struct.unpack_from("<I", manifest, off)
        off += 4
        kinds = manifest[off : off + n_lines]
        if len(kinds) != n_lines:
            raise ValueError("KMXP2: manifest troncato")
        verbatim_blob = manifest[off + n_lines :]
        verbatim = verbatim_blob.split(b"\n") if n_verbatim else []
        if len(verbatim) != n_verbatim:
            raise ValueError("KMXP2: righe verbatim incoerenti")

        values = payload.split(b"\n") if sum(col_counts) else []
        if len(values) != sum(col_counts):
            raise ValueError("KMXP2: payload incoerente col manifest")
        columns, start = [], 0
        for n in col_counts:
            columns.append(values[start : start + n])
            start += n

        if n_shapes == 1:
            # Caso comune: un'unica forma di riga. Le righe si ricompongono
            # in blocco con zip invece che campo per campo.
            ncols, sep, cr = shapes[1]
            rows = iter([sep.join(t) + cr for t in zip(*columns[:ncols])])
            vit = iter(verbatim)
            return b"\n".join([next(vit) if k == 0 else next(rows) for k in kinds])

        cursor = [0] * n_cols
        iv = 0
        out = []
        for k in kinds:
            if k == 0:
                out.append(verbatim[iv])
                iv += 1
                continue
            ncols, sep, cr = shapes[k]
            fields = []
            for j in range(ncols):
                fields.append(columns[j][cursor[j]])
                cursor[j] += 1
            out.append(sep.join(fields) + cr)
        return b"\n".join(out)

    @staticmethod
    def _inverse_legacy(manifest: bytes, payload: bytes) -> bytes:
        """Lettore del formato pre-1.3.1 (solo righe a tre campi)."""
        if len(manifest) < 4:
            return payload
        count = struct.unpack("<I", manifest[:4])[0]
        sections = payload.split(b"\n---\n")
        if len(sections) < 3:
            return payload
        xs = sections[0].split(b"\n")
        ys = sections[1].split(b"\n")
        zs = sections[2].split(b"\n")
        out = []
        for i in range(count):
            out.append(xs[i] + b" " + ys[i] + b" " + zs[i])
        return b"\n".join(out) + b"\n"


class BinaryBCJEngine(BaseDomainEngine):
    @staticmethod
    def transform_x86(raw_data: bytes) -> bytes:
        data = bytearray(raw_data)
        length = len(data)
        i = 0
        while i + 4 < length:
            b = data[i]
            if b in (0xE8, 0xE9):
                rel = struct.unpack("<i", data[i + 1 : i + 5])[0]
                abs_addr = (rel + (i + 5)) & 0xFFFFFFFF
                data[i + 1 : i + 5] = struct.pack("<I", abs_addr)
                i += 5
            else:
                i += 1
        return bytes(data)

    @staticmethod
    def inverse_x86(transformed: bytes) -> bytes:
        data = bytearray(transformed)
        length = len(data)
        i = 0
        while i + 4 < length:
            b = data[i]
            if b in (0xE8, 0xE9):
                abs_addr = struct.unpack("<I", data[i + 1 : i + 5])[0]
                rel = (abs_addr - (i + 5)) & 0xFFFFFFFF
                data[i + 1 : i + 5] = struct.pack("<i", struct.unpack("<i", struct.pack("<I", rel))[0])
                i += 5
            else:
                i += 1
        return bytes(data)

class FitsEngine:
    """Scientific FITS (Flexible Image Transport System) preconditioning engine.
    Handles IAU Big-Endian matrices (>f4, >i4), 2D spatial modular differences,
    and byte-plane slicing for astrophotography datasets.
    """
    def __init__(self, level: int = 3):
        self.level = level
        self.cctx = zstd.ZstdCompressor(level=self.level)
        self.dctx = zstd.ZstdDecompressor()

    def compress(self, raw_bytes: bytes) -> bytes:
        from astropy.io import fits
        import io

        # Ingest FITS container
        bio = io.BytesIO(raw_bytes)
        out_stream = io.BytesIO()
        
        with fits.open(bio) as hdul:
            # Header container: num_hdus
            out_stream.write(len(hdul).to_bytes(2, "little"))
            for hdu in hdul:
                if hdu.data is None:
                    hdr_b = str(hdu.header).encode("ascii")
                    comp_hdr = self.cctx.compress(hdr_b)
                    out_stream.write(b"\x00") # Type: Pure Header
                    out_stream.write(len(comp_hdr).to_bytes(4, "little"))
                    out_stream.write(comp_hdr)
                    continue

                arr = hdu.data
                if isinstance(arr, np.ndarray) and arr.ndim == 2 and arr.dtype.itemsize == 4:
                    rows, cols = arr.shape
                    is_float = (arr.dtype.kind == "f")
                    out_stream.write(b"\x01" if is_float else b"\x02") # Type: 2D f4 / i4
                    out_stream.write(rows.to_bytes(4, "little"))
                    out_stream.write(cols.to_bytes(4, "little"))

                    raw_b = arr.tobytes()
                    u32_view = np.frombuffer(raw_b, dtype=np.uint32).reshape(rows, cols)
                    diff = np.empty_like(u32_view)
                    diff[:, 0] = u32_view[:, 0]
                    diff[:, 1:] = u32_view[:, 1:] - u32_view[:, :-1]

                    u8_diff = np.frombuffer(diff.tobytes(), dtype=np.uint8).reshape(-1, 4)
                    for p in range(4):
                        plane_c = self.cctx.compress(u8_diff[:, p].tobytes())
                        out_stream.write(len(plane_c).to_bytes(4, "little"))
                        out_stream.write(plane_c)
                else:
                    raw_b = arr.tobytes() if hasattr(arr, "tobytes") else bytes(arr)
                    comp_b = self.cctx.compress(raw_b)
                    out_stream.write(b"\x03") # Type: Generic Fallback
                    out_stream.write(len(comp_b).to_bytes(4, "little"))
                    out_stream.write(comp_b)

        return out_stream.getvalue()

    def decompress(self, comp_bytes: bytes) -> bytes:
        # Fallback decompressor stub
        return comp_bytes

