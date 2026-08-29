"""
KolmoX - Core Unified Pipeline
"""

import struct
from typing import Optional
import zstandard as zstd
from kolmox.core.chunker import BlockCompressor
from kolmox.core.container import KolmoXContainer
from kolmox.core.delta import DeltaEngine
from kolmox.sandbox.runner import SandboxRunner

MAGIC_CONTAINER = b"KMX3"


class KolmoXPipeline:
    def __init__(self, chunk_size: int = 65536, delta_level: int = 19):
        self.chunk_size = chunk_size
        self.delta_level = delta_level
        self.delta_engine = DeltaEngine(compression_level=delta_level)
        self.block_comp = BlockCompressor(delta_level=delta_level)
        self.runner = SandboxRunner()
        self.cctx = zstd.ZstdCompressor(level=delta_level)
        self.dctx = zstd.ZstdDecompressor()

    def compress_with_script(self, original_data: bytes, script_source: str) -> bytes:
        reconstructed = self.runner.execute(script_source)
        residual_data = self.delta_engine.compute_residual(original_data, reconstructed)
        return KolmoXContainer.pack(
            script_source=script_source,
            residual_data=residual_data,
            original_size=len(original_data),
        )

    def compress(self, data: bytes) -> bytes:
        chunks = [data[i : i + self.chunk_size] for i in range(0, len(data), self.chunk_size)]
        block_payloads = []
        
        for c in chunks:
            block_payloads.append(self.block_comp.compress_block(c))

        combined = bytearray()
        combined.extend(struct.pack(">I", len(chunks)))
        for bp in block_payloads:
            combined.extend(struct.pack(">I", len(bp)))
            combined.extend(bp)

        compressed_stream = self.cctx.compress(bytes(combined))
        header = struct.pack(">4sQI", MAGIC_CONTAINER, len(data), len(chunks))
        return header + compressed_stream

    def decompress(self, kmx_data: bytes) -> bytes:
        header_len = struct.calcsize(">4sQI")
        if kmx_data[:4] == b"KMX2":
            unpacked = KolmoXContainer.unpack(kmx_data)
            reconstructed = self.runner.execute(unpacked["script_source"])
            return self.delta_engine.apply_residual(reconstructed, unpacked["residual_data"])

        magic, orig_size, chunk_count = struct.unpack(">4sQI", kmx_data[:header_len])
        if magic != MAGIC_CONTAINER:
            raise ValueError(f"Invalid magic header: {magic}")

        decompressed_stream = self.dctx.decompress(kmx_data[header_len:])
        num_chunks = struct.unpack(">I", decompressed_stream[:4])[0]
        
        offset = 4
        restored_buffer = bytearray()
        for _ in range(num_chunks):
            bp_len = struct.unpack(">I", decompressed_stream[offset : offset + 4])[0]
            offset += 4
            block_bytes = decompressed_stream[offset : offset + bp_len]
            offset += bp_len

            restored_block, _ = self.block_comp.decompress_block(block_bytes)
            restored_buffer.extend(restored_block)

        return bytes(restored_buffer)