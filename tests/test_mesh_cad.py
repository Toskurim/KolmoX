"""
KolmoX - Unit Tests for 3D Mesh & CAD Geometric Transform Engine
"""
import pytest
from kolmox.core.mesh_cad import MeshCADEngine
from kolmox.core.pipeline import KolmoXPipeline


def test_mesh_cad_detection():
    obj_sample = b"# Test OBJ\nv 1.0 2.0 3.0\nv 4.0 5.0 6.0\nv 7.0 8.0 9.0\nv 10.0 11.0 12.0\nv 13.0 14.0 15.0\nf 1 2 3\n"
    random_bin = b"\x00\xff\x12\x34\x56\x78\x9a\xbc\xde\xf0"
    
    assert MeshCADEngine.is_obj_mesh(obj_sample) is True
    assert MeshCADEngine.is_obj_mesh(random_bin) is False


def test_mesh_cad_roundtrip_bit_exact():
    raw_lines = [
        "# KolmoX CAD Unit Test Model\n",
        "g Surface_A\n"
    ]
    for i in range(500):
        raw_lines.append(f"v {i * 0.125:.4f} {i * 0.250:.4f} {i * 0.375:.4f}\n")
    for i in range(1, 499):
        raw_lines.append(f"f {i} {i+1} {i+2}\n")
    
    raw_obj = "".join(raw_lines).encode("utf-8")

    # 1. Geometric transposition
    meta_header, packed_geom = MeshCADEngine.transpose_mesh(raw_obj)
    intermediate = len(meta_header).to_bytes(4, "big") + meta_header + packed_geom

    # 2. Pipeline compression & decompression
    pipeline = KolmoXPipeline(compression_level=9)
    compressed = pipeline.compress_bytes(intermediate)
    decompressed_intermediate = pipeline.decompress_bytes(compressed)

    # 3. Geometric untransposition
    h_len = int.from_bytes(decompressed_intermediate[:4], "big")
    dec_meta = decompressed_intermediate[4:4 + h_len]
    dec_geom = decompressed_intermediate[4 + h_len:]
    restored_obj = MeshCADEngine.untranspose_mesh(dec_meta, dec_geom)

    # 4. Strict bit-exact verification
    assert restored_obj == raw_obj
    assert len(compressed) < len(raw_obj)