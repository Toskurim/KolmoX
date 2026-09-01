import pytest
import numpy as np
from kolmox.engines.extended_domains import FitsEngine

def test_fits_engine_synthetic_array():
    engine = FitsEngine(level=3)
    # Genera matrice simulata deep-sky float32 Big-Endian (>f4)
    np.random.seed(42)
    fake_sky = (np.ones((64, 64), dtype=">f4") * 15.0) + np.random.normal(0, 0.5, (64, 64)).astype(">f4")
    
    # Mock header FITS minimo + payload
    hdr = b"SIMPLE  =                    T / file does conform to FITS standard             "
    hdr += b"BITPIX  =                  -32 / number of bits per data pixel                  "
    hdr += b"NAXIS   =                    2 / number of data axes                            "
    hdr += b"NAXIS1  =                   64 / length of data axis 1                          "
    hdr += b"NAXIS2  =                   64 / length of data axis 2                          "
    hdr += b"END" + b" " * 77
    raw_fits = hdr.ljust(2880, b" ") + fake_sky.tobytes()

    compressed = engine.compress(raw_fits)
    assert len(compressed) > 0
    assert len(compressed) < len(raw_fits)
