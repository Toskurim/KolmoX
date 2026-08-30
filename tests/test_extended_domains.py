"""
Unit tests for all 5 extended preconditioning domains (v1.1.0)
"""

import numpy as np
import struct
from kolmox.engines.extended_domains import (
    GCodeEngine,
    ScientificFloatEngine,
    AudioPCMEngine,
    PointCloudEngine,
    BinaryBCJEngine,
)


def test_gcode_roundtrip_bit_exact():
    raw_gcode = (
        "; Generated GCode\n"
        "G21 ; millimeter units\n"
        "G90 ; absolute coordinates\n"
        "G1 X12.500 Y45.120 Z0.200 F3000 E0\n"
        "G1 X13.200 Y45.980 Z0.200 F3000 E0.125\n"
        "G1 X14.000 Y46.500 Z0.200 F3000 E0.250\n"
        "M104 S210\n"
    ).encode("utf-8")

    assert GCodeEngine.is_gcode(raw_gcode)
    template, coords = GCodeEngine.transform(raw_gcode)
    restored = GCodeEngine.inverse(template, coords)
    assert restored == raw_gcode


def test_scientific_f32_byte_plane_roundtrip():
    np.random.seed(42)
    floats = np.random.uniform(-1000.0, 1000.0, 2000).astype(np.float32)
    raw_bytes = floats.tobytes()

    sliced = ScientificFloatEngine.transform_f32_byte_plane(raw_bytes)
    restored = ScientificFloatEngine.inverse_f32_byte_plane(sliced)
    assert restored == raw_bytes


def test_audio_pcm16_stereo_roundtrip():
    samplerate = 44100
    t = np.linspace(0, 0.1, int(samplerate * 0.1), endpoint=False)
    left = (np.sin(2 * np.pi * 440 * t) * 30000).astype(np.int16)
    right = (np.cos(2 * np.pi * 880 * t) * 30000).astype(np.int16)
    pcm_raw = np.column_stack([left, right]).tobytes()

    head, stream = AudioPCMEngine.transform_stereo_pcm16(pcm_raw)
    restored = AudioPCMEngine.inverse_stereo_pcm16(head, stream)
    assert restored == pcm_raw


def test_point_cloud_xyz_roundtrip():
    raw_xyz = (
        "10.500000 20.300000 1.200000\n"
        "10.650000 20.450000 1.250000\n"
        "10.800000 20.600000 1.300000\n"
        "11.000000 20.900000 1.400000\n"
    ).encode("utf-8")

    manifest, payload = PointCloudEngine.transform_xyz_ascii(raw_xyz)
    restored = PointCloudEngine.inverse_xyz_ascii(manifest, payload)
    assert restored == raw_xyz


def test_binary_bcj_filter_roundtrip():
    stream = bytearray(bytes([0x90, 0x90, 0x90, 0x90]))
    stream.extend(bytes([0xE8]) + struct.pack("<I", 0x00045000))
    stream.extend(bytes([0x90, 0x90]))
    stream.extend(bytes([0xE9]) + struct.pack("<I", 0x00082000))
    stream.extend(bytes([0xCC, 0xC3]))

    raw_bin = bytes(stream)
    filtered = BinaryBCJEngine.transform_x86(raw_bin)
    restored = BinaryBCJEngine.inverse_x86(filtered)
    assert restored == raw_bin