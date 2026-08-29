"""
KolmoX - Core Hybrid Compression Pipeline
Integrates Multiblock Chunker, Generative Synthesis, Spatial Mesh, 2D Raster, and Temporal Video.
"""
from typing import Optional, List
import struct
import zstandard as zstd
from kolmox.core.chunker import BlockCompressor
from kolmox.core.delta import DeltaEngine
from kolmox.sandbox.runner import SandboxRunner
from kolmox.engines.raster_engine import RasterEngine
from kolmox.engines.video_engine import VideoEngine


class KolmoXPipeline:
    MAGIC_MULTIBLOCK = b"KMX3"

    def __init__(self, chunk_size: int = 65536, compression_level: int = 19):
        self.chunk_size = chunk_size
        self.level = compression_level
        self.compressor = BlockCompressor(delta_level=compression_level)
        self.delta_engine = DeltaEngine(compression_level=compression_level)
        self.runner = SandboxRunner()
        self.zstd_cctx = zstd.ZstdCompressor(level=compression_level)
        self.zstd_dctx = zstd.ZstdDecompressor()

    def compress(self, data: bytes) -> bytes:
        if len(data) <= self.chunk_size:
            return self.compressor.compress_block(data)

        blocks = []
        for i in range(0, len(data), self.chunk_size):
            chunk = data[i : i + self.chunk_size]
            compressed_chunk = self.compressor.compress_block(chunk)
            blocks.append(compressed_chunk)

        payload = bytearray(struct.pack(">4sI", self.MAGIC_MULTIBLOCK, len(blocks)))
        for b in blocks:
            payload.extend(struct.pack(">I", len(b)))
            payload.extend(b)
        return bytes(payload)

    def decompress(self, compressed_data: bytes) -> bytes:
        if compressed_data.startswith(self.MAGIC_MULTIBLOCK):
            magic, num_blocks = struct.unpack(">4sI", compressed_data[:8])
            offset = 8
            restored = bytearray()
            for _ in range(num_blocks):
                block_len = struct.unpack(">I", compressed_data[offset : offset + 4])[0]
                offset += 4
                block_data = compressed_data[offset : offset + block_len]
                offset += block_len
                chunk_bytes, _ = self.compressor.decompress_block(block_data)
                restored.extend(chunk_bytes)
            return bytes(restored)

        restored_bytes, _ = self.compressor.decompress_block(compressed_data)
        return restored_bytes

    def compress_with_script(self, data: bytes, script: str) -> bytes:
        orig_len = len(data)
        reconstructed = self.runner.execute(script)
        residual = self.delta_engine.compute_residual(data, reconstructed)
        script_bytes = script.encode("utf-8")
        header = struct.pack(">BIII", 1, len(script_bytes), orig_len, 0)
        return header + script_bytes + residual

    def decompress_with_script(self, container_bytes: bytes) -> bytes:
        restored, _ = self.compressor.decompress_block(container_bytes)
        return restored

    def compress_bytes(
        self,
        data: bytes,
        format_hint: Optional[str] = None,
        width: int = 0,
        height: int = 0,
        channels: int = 3
    ) -> bytes:
        if format_hint == "raster" and width > 0 and height > 0:
            filtered = RasterEngine.compress_rgb(data, width, height, channels)
            return self.zstd_cctx.compress(filtered)
        return self.compress(data)

    def decompress_bytes(self, compressed_data: bytes) -> bytes:
        if compressed_data.startswith(b"\x28\xb5\x2f\xfd"):
            decomp = self.zstd_dctx.decompress(compressed_data)
            if decomp.startswith(RasterEngine.MAGIC_HEADER):
                return RasterEngine.decompress_rgb(decomp)
            return decomp
        return self.decompress(compressed_data)

    def compress_video_frames(
        self,
        frames: List[bytes],
        width: int,
        height: int,
        channels: int = 3
    ) -> bytes:
        packed = VideoEngine.compress_sequence(frames, width, height, channels)
        return self.zstd_cctx.compress(packed)

    def decompress_video_frames(self, compressed_data: bytes) -> List[bytes]:
        decomp = self.zstd_dctx.decompress(compressed_data)
        return VideoEngine.decompress_sequence(decomp)