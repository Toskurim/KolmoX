"""
KolmoX - Bit-Exact Delta Engine
Calculates and restores deterministic XOR residuals with sparse-run optimization.
"""

import struct
from typing import Tuple
import zstandard as zstd


class DeltaEngine:
    def __init__(self, compression_level: int = 19):
        self.cctx = zstd.ZstdCompressor(level=compression_level)
        self.dctx = zstd.ZstdDecompressor()

    def compute_residual(self, original: bytes, reconstructed: bytes) -> bytes:
        if len(original) != len(reconstructed):
            raise ValueError(
                f"Size mismatch: original ({len(original)}) vs reconstructed ({len(reconstructed)})"
            )

        xor_mask = bytearray(len(original))
        diff_count = 0
        for i in range(len(original)):
            diff = original[i] ^ reconstructed[i]
            xor_mask[i] = diff
            if diff != 0:
                diff_count += 1

        # Mode 1: Sparse offset list if error rate is under 5%
        if diff_count < (len(original) * 0.05):
            sparse_buf = bytearray()
            sparse_buf.append(1)  # Flag: Sparse Mode
            sparse_buf.extend(struct.pack(">I", diff_count))
            for i in range(len(original)):
                if xor_mask[i] != 0:
                    sparse_buf.extend(struct.pack(">IB", i, xor_mask[i]))
            return self.cctx.compress(bytes(sparse_buf))

        # Mode 2: Dense Bitmask
        dense_payload = b"\x00" + bytes(xor_mask)
        return self.cctx.compress(dense_payload)

    def apply_residual(self, reconstructed: bytes, compressed_residual: bytes) -> bytes:
        raw_mask = self.dctx.decompress(compressed_residual)
        mode = raw_mask[0]

        original = bytearray(reconstructed)

        if mode == 1:  # Sparse Mode
            diff_count = struct.unpack(">I", raw_mask[1:5])[0]
            offset = 5
            for _ in range(diff_count):
                idx, val = struct.unpack(">IB", raw_mask[offset : offset + 5])
                original[idx] ^= val
                offset += 5
        else:  # Dense Mode
            mask_bytes = raw_mask[1:]
            for i in range(len(original)):
                original[i] ^= mask_bytes[i]

        return bytes(original)