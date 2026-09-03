"""
Unit tests for the Structured Text Columnar Demuxer.
"""
import numpy as np
import pytest

from kolmox.core.domain_router import DomainRouter, DomainType
from kolmox.core.pipeline import KolmoXPipeline
from kolmox.engines.columnar_text import ColumnarTextEngine


EDGE_CASES = [
    b"a,b,c\n1,2,3\n4,5,6\n7,8,9\n10,11,12\n13,14,15\n16,17,18\n19,20,21\n",
    b"a,b,c\n1,2,3\n4,5,6\n7,8,9\n10,11,12\n13,14,15\n16,17,18\n19,20,21",
    b"a,b,c\r\n1,2,3\r\n4,5,6\r\n7,8,9\r\n10,11,12\r\n13,14,15\r\n16,17,18\r\n19,20,21\r\n",
    b"a,b,c\n1,2\n4,5,6,7\n8\n9,10,11\n12,13\n14,15,16\n17,18,19\n",
    b'id,note\n1,"hello, world"\n2,"a,b,c"\n3,plain\n4,"x, y"\n5,plain\n6,plain\n7,plain\n',
    b"a,b,c\n1,2,3\n\n4,5,6\n\n\n7,8,9\n10,11,12\n",
    b"\n\n\n\n\n\n\n\n\n",
    b"a,b,c\n,,\n1,,3\n,2,\n,,\n4,5,6\n,,\n7,8,9\n",
    b"a,b\n\xff\xfe,\x00\x01\n\x80\x81,\xc0\xc1\n1,2\n3,4\n5,6\n7,8\n9,10\n",
]


@pytest.mark.parametrize("data", EDGE_CASES)
def test_columnar_roundtrip_bit_exact(data):
    primary, aux = ColumnarTextEngine.transform(data, b",")
    assert aux == b""
    assert ColumnarTextEngine.inverse(primary) == data


def test_columnar_roundtrip_obj_mixed_line_types():
    obj = (
        b"# commento\no Mesh\n"
        b"v 1.0 2.0 3.0\nv 4.0 5.0 6.0\n"
        b"vn 0.0 0.0 1.0\nvt 0.5 0.5\n"
        b"f 1/1/1 2/2/1 3/3/1\nf 2/2/1 3/3/1 4/4/1\n"
        b"s off\nv 7.0 8.0 9.0\n"
    )
    primary, _ = ColumnarTextEngine.transform(obj, b" ", group_by_first_token=True)
    assert ColumnarTextEngine.inverse(primary) == obj


def test_columnar_fuzz_never_returns_wrong_bytes():
    """Su input arbitrario: o roundtrip bit-exact, o ValueError. Mai output errato."""
    rng = np.random.default_rng(0)
    for _ in range(200):
        size = int(rng.integers(0, 600))
        data = bytes(rng.integers(0, 256, size=size, dtype=np.uint8))
        for delimiter, group in ((b",", False), (b" ", True)):
            try:
                primary, _ = ColumnarTextEngine.transform(data, delimiter, group_by_first_token=group)
            except ValueError:
                continue
            assert ColumnarTextEngine.inverse(primary) == data


def test_pipeline_csv_uses_columnar_transform_and_beats_zstd():
    rows = ["timestamp,sensor_id,temp_c,pressure_kpa"]
    temp, press = 21.5, 101.3
    for i in range(4000):
        temp += 0.001
        press += 0.002
        rows.append(f"2026-08-29T00:00:{i%60:02d}.000Z,{1 + i%8},{temp:.3f},{press:.3f}")
    data = ("\n".join(rows) + "\n").encode("utf-8")

    assert DomainRouter.detect_domain(data, "telemetry.csv") == DomainType.TELEMETRY_CSV

    pipeline = KolmoXPipeline()
    compressed = pipeline.compress_bytes(data, filename="telemetry.csv")
    assert pipeline.decompress_bytes(compressed) == data
    # La trasformazione deve aver vinto il confronto competitivo col baseline Zstd
    assert compressed[6] == int(DomainType.TELEMETRY_CSV)
