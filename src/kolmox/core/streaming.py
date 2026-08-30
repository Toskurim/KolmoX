"""
KolmoX Constant-Memory Streaming Engine (v1.1.0)
Processes arbitrarily large datasets in bounded RAM chunks.
"""

import io
import struct
from typing import BinaryIO, Iterator, Optional
from kolmox.core.pipeline import KolmoXPipeline

DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB per chunk
STREAM_MAGIC = b"KMXS"               # KolmoX Stream Magic


class KolmoXStreamer:
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, compression_level: int = 3):
        self.chunk_size = chunk_size
        self.pipeline = KolmoXPipeline(compression_level=compression_level)

    def compress_stream(self, src: BinaryIO, dst: BinaryIO, filename: Optional[str] = None) -> int:
        """Compresses an input stream into an output stream with bounded RAM."""
        dst.write(STREAM_MAGIC)
        total_written = len(STREAM_MAGIC)

        while True:
            chunk = src.read(self.chunk_size)
            if not chunk:
                break

            compressed_chunk = self.pipeline.compress_bytes(chunk, filename=filename)
            header = struct.pack("<I", len(compressed_chunk))
            dst.write(header)
            dst.write(compressed_chunk)
            total_written += 4 + len(compressed_chunk)

        # EOS (End of Stream) Marker
        dst.write(struct.pack("<I", 0))
        return total_written + 4

    def decompress_stream(self, src: BinaryIO, dst: BinaryIO) -> int:
        """Decompresses a KolmoX stream into an output stream."""
        magic = src.read(4)
        if magic != STREAM_MAGIC:
            raise ValueError("Invalid KolmoX stream header.")

        total_unpacked = 0
        while True:
            len_buf = src.read(4)
            if len(len_buf) < 4:
                break
            chunk_len = struct.unpack("<I", len_buf)[0]
            if chunk_len == 0:
                break  # EOS

            chunk_data = src.read(chunk_len)
            if len(chunk_data) != chunk_len:
                raise IOError("Unexpected end of stream data.")

            restored = self.pipeline.decompress_bytes(chunk_data)
            dst.write(restored)
            total_unpacked += len(restored)

        return total_unpacked
