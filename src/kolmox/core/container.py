"""
KolmoX - High-Efficiency Binary Container Format (.kmx)
"""

import struct
import zstandard as zstd
from typing import Dict, Any

MAGIC_HEADER = b"KMX2"


class KolmoXContainer:
    @staticmethod
    def pack(script_source: str, residual_data: bytes, original_size: int) -> bytes:
        cctx = zstd.ZstdCompressor(level=19)
        compressed_script = cctx.compress(script_source.encode("utf-8"))
        header = struct.pack(">4sQI", MAGIC_HEADER, original_size, len(compressed_script))
        return header + compressed_script + residual_data

    @staticmethod
    def unpack(packed_data: bytes) -> Dict[str, Any]:
        header_size = struct.calcsize(">4sQI")
        if len(packed_data) < header_size:
            raise ValueError("Invalid KolmoX file: Header truncated.")

        magic, original_size, script_len = struct.unpack(
            ">4sQI", packed_data[:header_size]
        )
        if magic != MAGIC_HEADER:
            raise ValueError(f"Invalid magic header: {magic}")

        dctx = zstd.ZstdDecompressor()
        script_end = header_size + script_len
        script_source = dctx.decompress(packed_data[header_size:script_end]).decode("utf-8")
        residual_data = packed_data[script_end:]

        return {
            "original_size": original_size,
            "script_source": script_source,
            "residual_data": residual_data,
        }