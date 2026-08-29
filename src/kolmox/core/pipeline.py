"""
KolmoX - Core Hybrid Compression Pipeline
Integrates Multiblock Chunker, Spatial Mesh, 2D Raster, and Temporal Video engines.
"""
from typing import Optional, List
import zstandard as zstd
from kolmox.core.chunker import BlockCompressor
from kolmox.engines.raster_engine import RasterEngine
from kolmox.engines.video_engine import VideoEngine


class KolmoXPipeline:
    def __init__(self, chunk_size: int = 65536, compression_level: int = 19):
        self.chunk_size = chunk_size
        self.level = compression_level
        self.compressor = BlockCompressor(chunk_size=chunk_size, compression_level=compression_level)
        self.zstd_cctx = zstd.ZstdCompressor(level=compression_level)
        self.zstd_dctx = zstd.ZstdDecompressor()

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
        return self.compressor.compress_block(data)

    def decompress_bytes(self, compressed_data: bytes) -> bytes:
        if compressed_data.startswith(b"\x28\xb5\x2f\xfd"):  # Standard Zstd magic frame
            decomp = self.zstd_dctx.decompress(compressed_data)
            if decomp.startswith(RasterEngine.MAGIC_HEADER):
                return RasterEngine.decompress_rgb(decomp)
            return decomp
        return self.compressor.decompress_block(compressed_data)

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