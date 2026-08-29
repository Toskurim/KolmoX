"""
KolmoX - Delta Engine with fast XOR logic
"""
from typing import Optional
import zstandard as zstd


def fast_xor(a: bytes, b: bytes) -> bytes:
    l = min(len(a), len(b))
    # Python 3 fast int from buffer XOR
    return bytes(x ^ y for x, y in zip(a[:l], b[:l]))


class DeltaEngine:
    def __init__(self, compression_level: int = 19):
        self.cctx = zstd.ZstdCompressor(level=compression_level)
        self.dctx = zstd.ZstdDecompressor()

    def compute_residual(self, original_data: bytes, reconstructed_data: bytes) -> bytes:
        orig_len = len(original_data)
        if len(reconstructed_data) < orig_len:
            reconstructed_data = reconstructed_data.ljust(orig_len, b"\x00")
        elif len(reconstructed_data) > orig_len:
            reconstructed_data = reconstructed_data[:orig_len]

        xor_diff = fast_xor(original_data, reconstructed_data)
        return self.cctx.compress(xor_diff)

    def apply_residual(self, reconstructed_data: bytes, residual_data: bytes, original_len: Optional[int] = None) -> bytes:
        xor_diff = self.dctx.decompress(residual_data)
        target_len = original_len if original_len is not None else len(xor_diff)

        if len(reconstructed_data) < target_len:
            reconstructed_data = reconstructed_data.ljust(target_len, b"\x00")
        elif len(reconstructed_data) > target_len:
            reconstructed_data = reconstructed_data[:target_len]

        return fast_xor(xor_diff, reconstructed_data)