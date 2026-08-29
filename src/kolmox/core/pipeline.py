"""
KolmoX - Core Hybrid Compression Pipeline
Integrates Multiblock Chunker, Synthesis XOR Delta, Spatial Mesh, 2D Raster, and Temporal Video.
"""
from typing import Optional, List
import zstandard as zstd
from kolmox.core.chunker import BlockCompressor
from kolmox.core.delta import DeltaEngine, KolmoXContainer
from kolmox.engines.raster_engine import RasterEngine
from kolmox.engines.video_engine import VideoEngine


class KolmoXPipeline:
    def __init__(self, chunk_size: int = 65536, compression_level: int = 19):
        self.chunk_size = chunk_size
        self.level = compression_level
        self.compressor = BlockCompressor()
        self.delta_engine = DeltaEngine()
        self.zstd_cctx = zstd.ZstdCompressor(level=compression_level)
        self.zstd_dctx = zstd.ZstdDecompressor()

    def compress(self, data: bytes) -> bytes:
        """Alias for multiblock chunking pipeline."""
        return self.compressor.compress_block(data)

    def decompress(self, compressed_data: bytes) -> bytes:
        """Alias for multiblock dechunking pipeline."""
        return self.compressor.decompress_block(compressed_data)

    def compress_with_script(self, data: bytes, script: str) -> bytes:
        """Compresses data against a synthesized program using XOR delta residuals."""
        target_len = len(data)
        synthetic_data = self.delta_engine.execute_generator(script)
        if len(synthetic_data) < target_len:
            synthetic_data = synthetic_data.ljust(target_len, b"\x00")
        else:
            synthetic_data = synthetic_data[:target_len]

        xor_diff = self.delta_engine.compute_xor_delta(data, synthetic_data)
        compressed_delta = self.zstd_cctx.compress(xor_diff)
        return KolmoXContainer.pack(script, compressed_delta)

    def decompress_with_script(self, container_bytes: bytes) -> bytes:
        """Restores bit-exact data from script container."""
        script, compressed_delta = KolmoXContainer.unpack(container_bytes)
        xor_diff = self.zstd_dctx.decompress(compressed_delta)
        synthetic_data = self.delta_engine.execute_generator(script)
        if len(synthetic_data) < len(xor_diff):
            synthetic_data = synthetic_data.ljust(len(xor_diff), b"\x00")
        else:
            synthetic_data = synthetic_data[: len(xor_diff)]
        return self.delta_engine.apply_xor_delta(synthetic_data, xor_diff)

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
        if compressed_data.startswith(b"KMX2"):
            return self.decompress_with_script(compressed_data)
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