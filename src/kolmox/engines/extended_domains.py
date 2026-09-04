from .base import BaseDomainEngine
import zstandard as zstd
import numpy as np
"""
KolmoX Extended Domain Preconditioning Engines (v1.1.0)
Bit-exact, high-throughput transforms with C-acceleration and NumPy fallback.
"""

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

    @staticmethod
    def transform_stereo_pcm16(raw_data: bytes) -> Tuple[bytes, bytes]:
        if AudioPCMEngine.is_wav(raw_data):
            data_pos = raw_data.find(b"data")
            if data_pos != -1 and len(raw_data) >= data_pos + 8:
                data_len = struct.unpack("<I", raw_data[data_pos + 4 : data_pos + 8])[0]
                header = raw_data[: data_pos + 8]
                pcm = raw_data[data_pos + 8 : data_pos + 8 + data_len]
            else:
                header = raw_data[:44]
                pcm = raw_data[44:]
        else:
            header = b""
            pcm = raw_data

        num_samples = len(pcm) // 4
        if num_samples == 0:
            return header, pcm

        samples = np.frombuffer(pcm[: num_samples * 4], dtype=np.int16).reshape(-1, 2)
        left = samples[:, 0].astype(np.int32)
        right = samples[:, 1].astype(np.int32)

        diff = (left - right).astype(np.int16)
        delta_left = np.empty_like(left, dtype=np.int16)
        delta_left[0] = left[0]
        delta_left[1:] = (left[1:] - left[:-1]).astype(np.int16)

        processed = delta_left.tobytes() + diff.tobytes()
        return header, processed

    @staticmethod
    def inverse_stereo_pcm16(header: bytes, processed: bytes) -> bytes:
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
    @staticmethod
    def transform_xyz_ascii(raw_data: bytes) -> Tuple[bytes, bytes]:
        lines = raw_data.split(b"\n")
        xs, ys, zs = [], [], []
        for line in lines:
            parts = line.split()
            if len(parts) == 3:
                xs.append(parts[0])
                ys.append(parts[1])
                zs.append(parts[2])
        manifest = struct.pack("<I", len(xs))
        payload = b"\n".join(xs + [b"---"] + ys + [b"---"] + zs)
        return manifest, payload

    @staticmethod
    def inverse_xyz_ascii(manifest: bytes, payload: bytes) -> bytes:
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

