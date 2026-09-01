# KolmoX

![CI/CD](https://github.com/Toskurim/KolmoX/actions/workflows/tests.yml/badge.svg?branch=main)
[![PyPI](https://img.shields.io/pypi/v/kolmox.svg)](https://pypi.org/project/kolmox/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-blue.svg)](LICENSE)
[![License: Commercial](https://img.shields.io/badge/License-Commercial-orange.svg)](#dual-licensing--commercial-use)


Let's be honest: standard general-purpose compressors (Gzip, LZMA, Snappy, and even vanilla Zstandard) are brilliant at what they were designed for, but they have a blind spot. They treat every single input as a flat, opaque 1D stream of bytes. While feeding raw LiDAR scans, 4K framebuffers, IEEE-754 float matrices, or multi-axis CNC paths into a sliding-window compressor technically works, it forces the algorithm to guess geometric and mathematical structures that we already know exist. It's like putting a high-precision mechanical blueprint through an office shredder before trying to tape it back together.

KolmoX bridges this gap. It is an enterprise-grade, high-throughput lossless compression framework built on Kolmogorov Structural Preconditioning. Instead of treating data blindly, KolmoX understands the underlying topology of modern workloads, rearranging it into high-correlation and low-entropy planes before handing it over to entropy coders:

* **Domain-Aware Structural Transformations**: Automatically identifies data topology and applies deterministic, bit-exact transforms (such as Float32 byte-plane slicing to isolate sign/exponent bytes from high-entropy mantissas, 2D spatial delta modeling for FITS scientific imaging, CNC G-Code axis demuxing, and stereo PCM decorrelation) to eliminate structural correlation entropy.
* **Continuous Dense Vector Slicing**: Decouples IEEE-754 Float32 memory streams (e.g. 1M+ raw embedding/sensor vectors) into discrete sign/exponent and mantissa byte planes. By separating predictable structural exponents from high-entropy mantissas, KolmoX provides near-instantaneous streaming compression (~930 MB/s decompression throughput, <5 ns per float) ideal for high-throughput in-memory caching tiers.
* **KMX2 Multi-Stream Container**: Encapsulates primary and split auxiliary streams into a resilient 24-byte fixed-header format backed by high-speed Zstandard FSE entropy coding.
* **High Performance & Constant-Memory Streaming**: Powered by native C-accelerated transposition kernels reaching up to 826+ MB/s, featuring KolmoXStreamer for bounded-RAM streaming on multi-gigabyte files, and a standalone C-ABI (include/kolmox.h) for zero-overhead C/C++/Rust integration.

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
| **x86 Binary Executable (.exe)** | Branch Target Normalizer (BCJ) | 1.87x | **1.86x** | **-0.66%** | ~25 MB/s / ~35 MB/s |

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
