"""
End-to-End Test Suite for KolmoX Extended Domains Container Pipeline.
"""

import numpy as np
import struct
from kolmox.core.pipeline import KolmoXPipeline


def test_e2e_gcode_pipeline():
    pipeline = KolmoXPipeline()
    raw = (
        "; Generated GCode\n"
        "G21 ; millimeter units\n"
        "G90 ; absolute coordinates\n"
        "G1 X12.500 Y45.120 Z0.200 F3000 E0.000\n"
        "G1 X13.200 Y45.980 Z0.200 F3000 E0.125\n"
        "G1 X14.000 Y46.500 Z0.200 F3000 E0.250\n"
        "M104 S210\n"
    ).encode("utf-8")

    compressed = pipeline.compress_bytes(raw, filename="part.gcode")
    decompressed = pipeline.decompress_bytes(compressed)
    assert decompressed == raw


def test_e2e_scientific_f32_pipeline():
    pipeline = KolmoXPipeline()
    floats = np.linspace(-50.0, 50.0, 1024, dtype=np.float32)
    raw = floats.tobytes()

    compressed = pipeline.compress_bytes(raw, filename="matrix.npy")
    decompressed = pipeline.decompress_bytes(compressed)
    assert decompressed == raw


def test_e2e_audio_pcm_pipeline():
    pipeline = KolmoXPipeline()
    t = np.linspace(0, 0.05, int(44100 * 0.05), endpoint=False)
    left = (np.sin(2 * np.pi * 440 * t) * 20000).astype(np.int16)
    right = (np.cos(2 * np.pi * 440 * t) * 20000).astype(np.int16)
    raw = np.column_stack([left, right]).tobytes()

    compressed = pipeline.compress_bytes(raw, filename="track.pcm")
    decompressed = pipeline.decompress_bytes(compressed)
    assert decompressed == raw


def test_e2e_pointcloud_pipeline():
    pipeline = KolmoXPipeline()
    raw = (
        "10.500000 20.300000 1.200000\n"
        "10.650000 20.450000 1.250000\n"
        "10.800000 20.600000 1.300000\n"
        "11.000000 20.900000 1.400000\n"
    ).encode("utf-8")

    compressed = pipeline.compress_bytes(raw, filename="scan.xyz")
    decompressed = pipeline.decompress_bytes(compressed)
    assert decompressed == raw


def test_e2e_bcj_binary_pipeline():
    pipeline = KolmoXPipeline()
    stream = bytearray(bytes([0x90, 0x90, 0x90, 0x90]))
    stream.extend(bytes([0xE8]) + struct.pack("<I", 0x00045000))
    stream.extend(bytes([0x90, 0x90]))
    stream.extend(bytes([0xE9]) + struct.pack("<I", 0x00082000))
    stream.extend(bytes([0xCC, 0xC3]))
    raw = bytes(stream)

    compressed = pipeline.compress_bytes(raw, filename="app.exe")
    decompressed = pipeline.decompress_bytes(compressed)
    assert decompressed == raw