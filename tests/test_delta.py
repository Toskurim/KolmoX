"""
Tests for DeltaEngine - Bit-exact lossless verification.
"""

import os
import pytest
from kolmox.core.delta import DeltaEngine
from kolmox.core.container import KolmoXContainer


def test_delta_bit_exact_reconstruction():
    engine = DeltaEngine()
    
    # Simulate an original payload
    original = b"A" * 5000 + b"B" * 3000 + os.urandom(200)
    
    # Simulate a generated approximation (mostly matching, with small deviations)
    reconstructed_approx = b"A" * 5000 + b"B" * 3000 + b"C" * 200
    
    # Compute residual
    residual = engine.compute_residual(original, reconstructed_approx)
    
    # Restore original
    restored = engine.apply_residual(reconstructed_approx, residual)
    
    assert restored == original
    assert len(restored) == len(original)


def test_container_pack_unpack():
    script = "def generate(): return b'TEST' * 10"
    residual = b"fake_compressed_residual_bytes"
    orig_size = 40

    packed = KolmoXContainer.pack(script, residual, orig_size)
    unpacked = KolmoXContainer.unpack(packed)

    assert unpacked["original_size"] == orig_size
    assert unpacked["script_source"] == script
    assert unpacked["residual_data"] == residual
