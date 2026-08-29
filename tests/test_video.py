"""
Unit tests for the Multi-Frame Video Temporal Engine.
"""
import numpy as np
from kolmox.engines.video_engine import VideoEngine


def test_video_temporal_roundtrip_bit_exact():
    width, height, channels = 64, 64, 3
    num_frames = 5
    frames = []

    y, x = np.mgrid[:height, :width]

    # Genera una sequenza con un gradiente che si sposta nel tempo
    for t in range(num_frames):
        r = ((x * 2) + (y * 3) + (t * 5)) % 256
        g = ((x * 4) - (y * 2) + (t * 2)) % 256
        b = ((x + y + t * 4) * 2) % 256
        raw_frame = np.stack([r, g, b], axis=-1).astype(np.uint8).tobytes()
        frames.append(raw_frame)

    packed = VideoEngine.compress_sequence(frames, width, height, channels)
    restored = VideoEngine.decompress_sequence(packed)

    assert len(restored) == num_frames
    for orig, rec in zip(frames, restored):
        assert orig == rec