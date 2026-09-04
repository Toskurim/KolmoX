"""
KolmoX - Structured Text Columnar Demuxer

Groups lines by structural shape (field count, optionally the leading token)
and transposes every group into column-major order, so homogeneous values
(timestamps, coordinates, ids) end up adjacent for the entropy coder.

The transform is purely mechanical - split on a single-byte delimiter, rejoin
with the same delimiter - so it is bit-exact for arbitrary input, including
quoted CSV fields and mixed line endings.
"""
import struct
from typing import List, Tuple


class ColumnarTextEngine:
    VERSION = 1
    MIN_LINES = 8
    MAX_CLASSES = 255
    HEADER_FMT = "<BBII"
    HEADER_LEN = 10
    CLASS_META_FMT = "<III"
    CLASS_META_LEN = 12

    # Separatori di campo plausibili, in ordine di preferenza a parita' di
    # punteggio. La virgola resta il default storico.
    DELIMITER_CANDIDATES = (b",", b";", b"\t", b"|")
    DETECT_SAMPLE_LINES = 400

    @classmethod
    def detect_delimiter(cls, raw_data: bytes,
                         candidates: Tuple[bytes, ...] = None) -> bytes:
        """Sceglie il separatore di campo osservando la struttura, non
        assumendola.

        Il criterio e' quello che si e' rivelato affidabile sui dati reali:
        a parita' di condizioni vince il separatore che produce **meno classi
        di forma**, cioe' il conteggio di campi piu' uniforme fra le righe. Su
        AirQualityUCI.csv la virgola ne produce 5 (perche' spezza i decimali
        del locale europeo) e il punto e virgola 2, di cui una copre 9.472
        righe su 9.473.

        Un candidato che non compare affatto darebbe una sola classe, cioe' il
        punteggio migliore: viene quindi scartato richiedendo che il conteggio
        di campi piu' frequente sia almeno 2.

        Lavora interamente a livello di byte. Nessuna decodifica: il modulo che
        ospitava questa euristica prima decodificava con errors="replace" e
        distruggeva irreversibilmente i byte non-UTF8.
        """
        candidates = candidates or cls.DELIMITER_CANDIDATES
        sample = [ln for ln in raw_data.split(b"\n")[: cls.DETECT_SAMPLE_LINES] if ln]
        if not sample:
            return candidates[0]

        best = None
        for delim in candidates:
            counts = {}
            for ln in sample:
                n = ln.count(delim) + 1
                counts[n] = counts.get(n, 0) + 1
            modal_fields = max(counts, key=lambda n: counts[n])
            if modal_fields < 2:
                continue                       # il separatore non compare
            # meno classi e' meglio; a parita', piu' campi e' meglio
            score = (len(counts), -modal_fields)
            if best is None or score < best[0]:
                best = (score, delim)

        return best[1] if best else candidates[0]

    @classmethod
    def transform(
        cls, raw_data: bytes, delimiter: bytes = None, group_by_first_token: bool = False
    ) -> Tuple[bytes, bytes]:
        # Il separatore finisce nell'header del primary, quindi la
        # decompressione lo ritrova da sola: rilevarlo qui non cambia il
        # formato e i container gia' scritti restano leggibili.
        if delimiter is None:
            delimiter = cls.detect_delimiter(raw_data)

        lines = raw_data.split(b"\n")
        if len(lines) < cls.MIN_LINES:
            raise ValueError("Too few lines for columnar demux")

        class_index = {}
        line_class = bytearray()
        buckets: List[List[List[bytes]]] = []

        for line in lines:
            tokens = line.split(delimiter)
            key = (tokens[0], len(tokens)) if group_by_first_token else len(tokens)
            idx = class_index.get(key)
            if idx is None:
                idx = len(buckets)
                if idx >= cls.MAX_CLASSES:
                    raise ValueError("Too many structural classes for columnar demux")
                class_index[key] = idx
                buckets.append([])
            line_class.append(idx)
            buckets[idx].append(tokens)

        meta = bytearray()
        blobs = []
        for rows in buckets:
            # zip(*rows) walks the rows column-first at C speed
            column_major = [token for column in zip(*rows) for token in column]
            blob = delimiter.join(column_major)
            meta += struct.pack(cls.CLASS_META_FMT, len(rows), len(rows[0]), len(blob))
            blobs.append(blob)

        primary = (
            struct.pack(cls.HEADER_FMT, cls.VERSION, delimiter[0], len(lines), len(buckets))
            + bytes(line_class)
            + bytes(meta)
            + b"".join(blobs)
        )
        return primary, b""

    @classmethod
    def inverse(cls, primary: bytes) -> bytes:
        version, delim_byte, num_lines, num_classes = struct.unpack(
            cls.HEADER_FMT, primary[: cls.HEADER_LEN]
        )
        if version != cls.VERSION:
            raise ValueError(f"Unsupported columnar demux version {version}")

        delimiter = bytes([delim_byte])
        offset = cls.HEADER_LEN
        line_class = primary[offset : offset + num_lines]
        offset += num_lines

        metas = []
        for _ in range(num_classes):
            metas.append(struct.unpack(cls.CLASS_META_FMT, primary[offset : offset + cls.CLASS_META_LEN]))
            offset += cls.CLASS_META_LEN

        buckets = []
        for num_rows, num_tokens, blob_len in metas:
            blob = primary[offset : offset + blob_len]
            offset += blob_len
            column_major = blob.split(delimiter)
            columns = [column_major[j * num_rows : (j + 1) * num_rows] for j in range(num_tokens)]
            buckets.append(list(zip(*columns)))

        cursors = [0] * num_classes
        out_lines = []
        for class_id in line_class:
            rows = buckets[class_id]
            out_lines.append(delimiter.join(rows[cursors[class_id]]))
            cursors[class_id] += 1

        return b"\n".join(out_lines)
