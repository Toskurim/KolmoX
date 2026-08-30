import numpy as np
from kolmox.engines.extended_domains import ScientificFloatEngine, BinaryBCJEngine

def test_c_abi_equivalence_float32():
    floats = np.linspace(-50.0, 50.0, 1000, dtype=np.float32)
    raw = floats.tobytes()
    sliced = ScientificFloatEngine.transform_f32_byte_plane(raw)
    restored = ScientificFloatEngine.inverse_f32_byte_plane(sliced)
    assert restored == raw

def test_c_abi_equivalence_bcj():
    raw_bin = b"\xe8\x00\x01\x00\x00\x90\xe9\xff\x00\x00\x00"
    filtered = BinaryBCJEngine.transform_x86(raw_bin)
    restored = BinaryBCJEngine.inverse_x86(filtered)
    assert restored == raw_bin
