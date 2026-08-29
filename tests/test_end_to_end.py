"""
End-to-End Pipeline Verification Test.
"""

from kolmox.core.pipeline import KolmoXPipeline


def test_full_pipeline_compression_cycle():
    pipeline = KolmoXPipeline()

    # Target: Structured repeated pattern + tiny variations (e.g. sensor/telemetry series)
    original_data = bytearray()
    for i in range(10000):
        val = (i * 7) % 256
        # Introduce a few anomalies
        if i % 500 == 0:
            val = 255
        original_data.append(val)
    original_data = bytes(original_data)

    # Deterministic micro-generator simulating code synthesis output
    synthesized_script = (
        "def generate():\n"
        "    buf = bytearray(10000)\n"
        "    for i in range(10000):\n"
        "        buf[i] = (i * 7) % 256\n"
        "    return bytes(buf)\n"
    )

    # Compress
    kmx_compressed = pipeline.compress_with_script(original_data, synthesized_script)

    # Decompress
    restored_data = pipeline.decompress(kmx_compressed)

    # Bit-exact assertion
    assert restored_data == original_data

    # Verify compression efficiency (original is 10,000 bytes)
    assert len(kmx_compressed) < len(original_data)