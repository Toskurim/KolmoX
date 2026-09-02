"""
Unit tests for extended CAD formats (OBJ, Binary STL, ISO 10303-21 STEP)
"""

import struct
from kolmox.core.mesh_cad import MeshCADEngine


def test_binary_stl_roundtrip_bit_exact():
    # Exactly 80 bytes for header
    header = b"KolmoX Synthetic Binary STL Test Header".ljust(80, b"\x00")
    num_triangles = 100
    header_with_count = header + struct.pack("<I", num_triangles)

    facets = bytearray()
    for i in range(num_triangles):
        # Normal (3x float) + 3 vertices (9x float) + 1 attr (uint16)
        facets.extend(struct.pack("<12fH", 0.0, 0.0, 1.0, float(i), 1.0, 2.0, float(i+1), 3.0, 4.0, float(i+2), 5.0, 6.0, 0))

    raw_stl = bytes(header_with_count + facets)
    assert MeshCADEngine.is_stl(raw_stl)

    head, geom = MeshCADEngine.transpose_stl_binary(raw_stl)
    restored = MeshCADEngine.untranspose_stl_binary(head, geom)
    assert restored == raw_stl


def test_step_iso10303_roundtrip_bit_exact():
    step_data = (
        "ISO-10303-21;\n"
        "HEADER;\n"
        "FILE_DESCRIPTION(('KolmoX STEP Benchmark'),'2;1');\n"
        "ENDSEC;\n"
        "DATA;\n"
        "#10=CARTESIAN_POINT('',(12.345678,98.765432,-45.102030));\n"
        "#20=DIRECTION('',(0.0,1.0,0.0));\n"
        "#30=VERTEX_POINT('',#10);\n"
        "ENDSEC;\n"
        "END-ISO-10303-21;\n"
    ).encode("utf-8")

    assert MeshCADEngine.is_step(step_data)

    template, geom = MeshCADEngine.transpose_step(step_data)
    restored = MeshCADEngine.untranspose_step(template, geom)
    assert restored == step_data
