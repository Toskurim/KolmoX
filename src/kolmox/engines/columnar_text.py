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

    @classmethod
    def transform(
        cls, raw_data: bytes, delimiter: bytes, group_by_first_token: bool = False
    ) -> Tuple[bytes, bytes]:
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
