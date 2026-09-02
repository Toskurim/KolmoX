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
| **Binary Register Packets (.bin)** | Stride Autocorr + Demux | 3.68x | **15.70x** | **+76.54%** | ~450 MB/s / **~930 MB/s** |
| **Industrial Telemetry (.csv)** | Columnar Demux + Quant Delta | 6.13x | **12.90x** | **+52.47%** | ~42 MB/s / ~56 MB/s |
| **CNC G-Code (.gcode)** | Columnar Axis Separation | 3.46x | **5.48x** | **+36.78%** | ~35 MB/s / ~42 MB/s |
| **2D Natural Sensor Raster (.bmp)** | 2D Spatial Delta | 2.84x | **3.97x** | **+28.26%** | ~265 MB/s / ~285 MB/s |
| **Parametric 3D CAD Mesh (.obj)** | Ordered Vertex Plane Slicing | 3.14x | **4.26x** | **+26.45%** | ~520 MB/s / ~600 MB/s |
| **Astrophysics FITS (JWST)** | 2D Modular Delta + Big-Endian Slicing | 1.47x | **1.90x** | **+22.87%** | ~225 MB/s / ~340 MB/s |
| **LiDAR XYZ Point Cloud** | Columnar Coordinate Slicing | 1.15x | **1.44x** | **+20.00%** | ~280 MB/s / ~680 MB/s |
| **Dense Vector Buffers (1M Float32)** | IEEE-754 Byte-Plane Slicing | 1.61x | **1.97x** | **+18.45%** | ~323 MB/s / **~927 MB/s** |
| **Audio PCM 16-bit (.wav)** | Stereo Mid/Side Decorrelation | 1.45x | **1.55x** | **+6.09%** | ~135 MB/s / ~260 MB/s |
| **x86 Binary Executable (.exe)** | Adaptive Fallback (BCJ/Zstd) | 1.87x | **1.87x** | **0.00%** | ~25 MB/s / ~35 MB/s |

> *Note: All metrics above represent physical empirical benchmarks executed on uncompressed real-world production datasets (including NASA/STScI JWST sensor observations, high-density CAM toolpaths, raw LiDAR coordinates, and industrial telemetry). Zero synthetic interpolation.*

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
