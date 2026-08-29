"""
KolmoX - High-Performance Text & CSV Columnar Engine
"""

from typing import Tuple, Optional, List


class TextColumnarEngine:
    @staticmethod
    def is_tabular_text(data: bytes) -> Tuple[bool, str]:
        try:
            preview = data[:min(8192, len(data))].decode("utf-8", errors="ignore")
            lines = [l for l in preview.splitlines() if l.strip()]
            if len(lines) < 3:
                return False, ""

            for sep in [",", "\t", ";", "|"]:
                counts = [l.count(sep) for l in lines[:5]]
                if counts[0] > 0 and len(set(counts)) == 1:
                    return True, sep
        except Exception:
            pass

        return False, ""

    @staticmethod
    def transpose_text(data: bytes, delimiter: str) -> Tuple[bytes, bytes]:
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        if len(lines) < 2:
            return b"", data

        header = lines[0].encode("utf-8")
        rows = [l.rstrip("\r\n").split(delimiter) for l in lines[1:] if l.strip()]
        if not rows:
            return header, b"".join([l.encode("utf-8") for l in lines[1:]])

        num_cols = len(rows[0])
        columns = [[] for _ in range(num_cols)]
        for r in rows:
            for c_idx in range(min(num_cols, len(r))):
                columns[c_idx].append(r[c_idx])

        # Pack each column separately
        col_payloads = ["\n".join(col).encode("utf-8") for col in columns]
        packed_columns = b"\x00".join(col_payloads)
        return header, packed_columns

    @staticmethod
    def untranspose_text(header_bytes: bytes, columnar_payload: bytes, delimiter: str) -> bytes:
        header_text = header_bytes.decode("utf-8", errors="replace")
        col_blobs = columnar_payload.split(b"\x00")
        columns = [b.decode("utf-8", errors="replace").split("\n") for b in col_blobs]

        num_rows = len(columns[0]) if columns else 0
        num_cols = len(columns)

        newline = "\r\n" if header_text.endswith("\r\n") else "\n"
        result = [header_text]

        for r_idx in range(num_rows):
            row_items = [columns[c_idx][r_idx] for c_idx in range(num_cols) if r_idx < len(columns[c_idx])]
            result.append(delimiter.join(row_items) + newline)

        return "".join(result).encode("utf-8")
