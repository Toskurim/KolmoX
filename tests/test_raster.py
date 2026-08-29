import numpy as np
from kolmox.engines.raster_engine import RasterEngine

def test_raster_roundtrip_bit_exact():
    width, height, channels = 64, 64, 3
    y, x = np.ogrid[:height, :width]
    r = ((x * 4) + (y * 2)) % 256
    g = ((x * 2) - (y * 3)) % 256
    b = ((x + y) * 3) % 256
    raw = np.stack([r, g, b], axis=-1).astype(np.uint8).tobytes()
    packed = RasterEngine.compress_rgb(raw, width, height, channels)
    restored = RasterEngine.decompress_rgb(packed)
    assert restored == raw
