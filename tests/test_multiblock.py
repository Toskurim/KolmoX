"""
Unit test for heterogeneous multi-block compression.
"""

import math
from kolmox.core.pipeline import KolmoXPipeline


def test_heterogeneous_multiblock_pipeline():
    pipeline = KolmoXPipeline(chunk_size=16384)

    # Block 1: Modulo Progression
    b1 = bytes([(i * 5) % 256 for i in range(16384)])
    # Block 2: Sine Wave
    b2 = bytearray(16384)
    for i in range(16384):
        b2[i] = max(0, min(255, int(128 + 100 * math.sin(i * 0.1))))
    # Block 3: Periodic repetition
    b3 = b"KOLMOX_ENTERPRISE_SYSTEMS_2026_" * 512

    dataset = b1 + bytes(b2) + b3
    compressed = pipeline.compress(dataset)
    restored = pipeline.decompress(compressed)

    assert restored == dataset
    assert len(restored) == len(dataset)
    # With competitive fallback, size is guaranteed to be extremely small
    assert len(compressed) < (len(dataset) * 0.05)  # Must be < 5% of original