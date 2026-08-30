import os
import pytest
from kolmox.core.pipeline import KolmoXPipeline
from kolmox.core.streaming import KolmoXStreamer
import io

def test_corrupted_header_handling():
    pipeline = KolmoXPipeline()
    # Random garbage instead of KMX2 header
    garbage = os.urandom(1024)
    with pytest.raises((ValueError, Exception)):
        pipeline.decompress_bytes(garbage)

def test_truncated_container_payload():
    pipeline = KolmoXPipeline()
    data = b"G1 X10 Y20 Z30\n" * 500
    compressed = pipeline.compress_bytes(data, filename="model.gcode")
    # Truncate in the middle of the container
    truncated = compressed[: len(compressed) // 2]
    with pytest.raises((ValueError, Exception)):
        pipeline.decompress_bytes(truncated)

def test_streaming_corruption_rejection():
    streamer = KolmoXStreamer()
    invalid_stream = io.BytesIO(b"KMXS\x01\x00\x00\x00\xff")
    out_stream = io.BytesIO()
    with pytest.raises((ValueError, IOError, Exception)):
        streamer.decompress_stream(invalid_stream, out_stream)
