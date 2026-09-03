# KolmoX

[![PyPI version](https://img.shields.io/pypi/v/kolmox.svg)](https://pypi.org/project/kolmox/) [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)

> **Architectural Positioning**: KolmoX is **not** a general-purpose replacement for Zstandard, Snappy, or Deflate. 
> Exactly as the PNG Delta Filter or the FLAC Mid/Side Decorrelator operate ahead of Deflate, KolmoX is a **domain-specific structural preconditioner**. It linearizes physical coordinates, IEEE-754 mantissas, and multi-dimensional matrices *before* entropy coding, eliminating topological correlations that sliding-window (LZ77) engines cannot detect.
>
> For production workloads, use the dedicated engine classes directly (`FitsEngine`, `ScientificFloatEngine`, `GCodeEngine`, etc.). An **Adaptive Competitive Fallback** ensures KolmoX output is mathematically guaranteed never to exceed plain Zstandard.

---

### Evidence Tiers

* **✅ Tier 1 (Reproducible In-Script)**: Synthetic-but-realistic datasets generated programmatically via `python benchmarks/benchmark_extended.py`. Fully reproducible by any third party with zero external dependencies.
* **📋 Tier 2 (Production Data / Reported)**: Benchmarked against production binary streams (NASA/STScI James Webb MIRI FITS, 5-axis CNC toolpaths, and Modbus/PLC telemetry registers). Reproducible via `python benchmarks/download_datasets.py` for publicly licensed archives.

---

## Why KolmoX Matters: Today and in the Multi-Petabyte Future

We live in an era where data generation has outpaced network bandwidth and storage interconnect speeds.

* **The Scientific & AI Bottleneck**: Modern AI pipelines, LLM checkpointing, physics engines, and space telescopes (JWST, Roman) generate billions of IEEE-754 floating-point numbers. Standard compressors choke on shot noise and mantissa entropy. KolmoX delivers up to 15.7x on binary registers and 1.97x on dense vectors and +22.8% net savings over Zstd on raw JWST FITS datasets without altering a single bit.
* **Smart Manufacturing & Industry 4.0**: Robotics, CNC machining, 3D additive manufacturing, and autonomous vehicle LiDAR streams churn out terabytes of continuous telemetry daily. Squeezing columnar telemetry by 12x–16x drastically cuts cloud egress bills and edge-to-cloud transmission latency.
* **Lossless is Non-Negotiable**: In medical imaging, astrophysics, engineering CAD, industrial telemetry, and legal compliance, lossy compression artifacts are unacceptable. KolmoX proves that "lossless" doesn't have to mean "poor compression ratios".

## Real-World Benchmark Results

All tests certify exact mathematical data restoration (zero precision loss, bit-exact roundtrip):

| Data Domain | Pipeline / Transform | Baseline (Zstd L3) | KolmoX (KMX2) | Gain vs Zstd | Throughput (Comp / Decomp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CNC G-Code (.gcode)** † | Columnar Axis Separation | 5.69x | **15.84x** | **+64.10%** | ~24 MB/s / ~35 MB/s |
| **Parametric 3D CAD Mesh (.obj)** † | Prefix-Grouped Vertex Plane Slicing | 6.00x | **16.27x** | **+63.12%** | ~40 MB/s / ~80 MB/s |
| **Audio PCM 16-bit (.wav)** † | Stereo Mid/Side Decorrelation | 1.02x | **2.59x** | **+60.48%** | ~172 MB/s / ~284 MB/s |
| **LiDAR XYZ Point Cloud** † ¹ | Columnar Coordinate Slicing | 27.11x | **65.79x** | **+58.79%** | ~80 MB/s / ~106 MB/s |
| **Binary Register Packets (.bin)** † | Stride Autocorr + Demux | 1.86x | **4.10x** | **+54.67%** | ~158 MB/s / ~1094 MB/s |
| **Industrial Telemetry (.csv)** † | Shape-Grouped Columnar Demux | 4.59x | **8.23x** | **+44.24%** | ~47 MB/s / ~98 MB/s |
| **Temporal Video Sequence (.kmxvraw)** † | Frame XOR Delta (SIMD) | 1.00x | **1.77x** | **+43.45%** | ~120 MB/s / ~189 MB/s |
| **2D Natural Sensor Raster (.bmp)** † | 2D Spatial Delta | 1.07x | **1.80x** | **+40.38%** | ~37 MB/s / ~2.4 MB/s |
| **Dense Float32 Buffer (250k values)** † | IEEE-754 Byte-Plane Slicing | 1.29x | **1.89x** | **+31.86%** | ~236 MB/s / ~642 MB/s |
| **Astrophysics FITS (JWST) — real data** | IEEE-754 Byte-Plane Slicing (auto-routed) | 1.47x | **1.76x** | **+16.31%** | ~213 MB/s / ~714 MB/s |
| **x86 Binary Executable (.exe)** † ² | Adaptive Fallback (BCJ/Zstd) | 7.59x | **7.56x** | **-0.46%** | ~13 MB/s / ~879 MB/s |

> *Methodology: every row above was measured on 2026-09-03 by running the data through the public `KolmoXPipeline.compress_bytes()` / `decompress_bytes()` API - the same path a user gets - with a bit-exact roundtrip assertion on each. Figures produced by calling engine classes directly, outside the pipeline, are not reported here: they omit the 24-byte KMX2 container header and bypass the adaptive competitive fallback. Every † row is reproducible with `python benchmarks/benchmark_extended.py`, which regenerates each dataset from a fixed seed and re-asserts every roundtrip. Compression ratios are deterministic; the throughput columns are single-run samples and vary by roughly ±15% between runs.*
>
> † *Synthetic dataset, generated programmatically. Only the Astrophysics FITS row uses a real-world production capture (a 117 MB NASA/STScI JWST MIRI observation of the Carina Nebula, compressed whole-file through the automatic domain router). Extracting just the pixel plane with astropy and compressing that instead yields 1.26x → 1.61x (+21.41%).*
>
> ¹ *The LiDAR dataset is a deterministic arithmetic ramp, which is why even the plain Zstd baseline reaches 27.11x. It demonstrates the transform works, but it is **not** representative of real scanner output - treat this row as a mechanism check, not a performance claim.*
>
> ² *A 40 KB synthetic instruction stream; at that size the throughput timings are dominated by measurement noise.*
>
> *Domain gains depend on the data actually having the structure the transform exploits. On a high-entropy input - a random-walk mesh with 6 decimals of noise per coordinate, or the x86 stream above - the transform yields nothing, the adaptive competitive fallback discards it, and the stored result is the plain Zstd baseline plus the 24-byte KMX2 header. The raster decompression figure (~2.4 MB/s) reflects a pure-Python pixel loop whose sequential dependency has not yet been ported to the C extension; it is the current honest number, not a target.*

## Installation & Setup

```bash
# Clone the repository
git clone https://github.com/Toskurim/KolmoX.git
cd KolmoX

# Install Python package in editable mode (with C-extension)
pip install -r requirements.txt
pip install -e .
```

## CMake Standalone C-Library Build

For direct C/C++/Rust integration without Python:

```bash
cmake -B build
cmake --build build --config Release
```

This generates `libkolmox.so` (or `kolmox.dll` / `libkolmox.dylib`) using the public C-ABI defined in `include/kolmox.h`.

## Quickstart CLI

```bash
# Auto-detect domain and compress into KMX2 container
kolmox compress path/to/file.gcode -o file.kmx

# Bit-exact decompression
kolmox decompress file.kmx -o restored.gcode

# Run throughput benchmark suite
python tests/benchmark_throughput.py
```

## Constant-Memory Streaming API

For multi-Gigabyte files, KolmoX provides a streaming engine that executes in bounded RAM (default 8MB chunks):

```python
from kolmox.core.streaming import KolmoXStreamer

streamer = KolmoXStreamer(chunk_size=8 * 1024 * 1024)

# Stream compression from file-like objects
with open("large_scan.xyz", "rb") as src, open("large_scan.kmxs", "wb") as dst:
    streamer.compress_stream(src, dst, filename="large_scan.xyz")
```

## Testing & Fuzz Resilience

KolmoX includes a 33-test validation suite covering end-to-end roundtrips, C-ABI equivalence, astrophysics FITS preconditioning, and fuzz resilience against malformed or truncated data:

```bash
pytest tests/ -v
```

## Technical Whitepaper

A full academic whitepaper detailing the Kolmogorov complexity foundations, KMX2 container specification, and mathematical transforms is available in `docs/WHITEPAPER.md` and as a downloadable PDF in `docs/KolmoX_Technical_Paper_v1.1.0_Complete_EN.pdf`.

## License

KolmoX is dual-licensed:

* **Open Source**: GNU Affero General Public License v3.0 (AGPLv3).
* **Commercial & Enterprise**: For proprietary software integration without AGPLv3 copyleft obligations, contact toskurim@gmail.com.
