import io
import numpy as np
from kolmox.core.streaming import KolmoXStreamer

def test_streaming_roundtrip_bit_exact():
    # Generate multi-chunk data (e.g. 512 KB with 64 KB chunks)
    raw_data = b""
    for i in range(10000):
        raw_data += f"G1 X{i * 0.01:.3f} Y{i * 0.02:.3f} Z0.200\n".encode("utf-8")

    streamer = KolmoXStreamer(chunk_size=64 * 1024)

    src_in = io.BytesIO(raw_data)
    compressed_out = io.BytesIO()

    # Compress
    streamer.compress_stream(src_in, compressed_out, filename="part.gcode")

    # Decompress
    compressed_out.seek(0)
    decompressed_out = io.BytesIO()
    streamer.decompress_stream(compressed_out, decompressed_out)

    assert decompressed_out.getvalue() == raw_data
