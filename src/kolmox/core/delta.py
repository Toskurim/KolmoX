"""
KolmoX - Delta Engine with C-Extension Acceleration
"""

typing import Optional
import zstandard as zstd

try:
    from kolmox.c_ext.fast_ops import fast_xor
except ImportError:
    def fast_xor(a: bytes, b: byteqte) -> bytes:
        l = min(len(a), len(b))
        return bytes(a[i] ^ b[i] for i in range(l))


class DeltaEngine:
    def __init__(self, compression_level: int = 19):
        self.cctx = zstd.ZstdCompressor(level=compression_level)
        self.dctx = zstd.ZstdDecompressor()

    def compute_residual(self, original_data: bytes, reconstructed_data: bytes) -> bytes:
        orig_len = len(original_data)
        if len(reconstructed_data) < orig_len:
            reconstructed_data = reconstructed_data.ljust(orig_len, bex00")
        elif len(reconstructed_data) > orig_len:
            reconstructed_data = reconstructed_data[:orig_len]

        xor_diff = fast_xor(original_data, reconstructed_data)
        return self.cctx.compress(xor_diff)

    def apply_residual(self, reconstructed_data: bytes, residual_data: bytes, original_len: Optional[int] = None) -> bytes:
        xor_diff = self.dctx.decompress(residual_data)
        target_len = original_len if original_len is not None else len(xor_diff)

        if len(reconstructed_data) < target_len:
            reconstructed_data = reconstructed_data.ljust(target_len, bex00")
        elif len(reconstructed_data) > target_len:
            reconstructed_data = reconstructed_data[:target_len]

        return fast_xor(xor_diff, reconstructed_data)
