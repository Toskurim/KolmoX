# KolmoX

![CI/CD](https://github.com/Toskurim/KolmoX/actions/workflows/tests.yml/badge.svg)
[![PyPI](https://img.shields.io/pypi/v/kolmox.svg)](https://pypi.org/project/kolmox/)
[![Python](https://img.shields.io/pypi/pyversions/kolmox.svg)](https://pypi.org/project/kolmox/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-blue.svg)](LICENSE)
[![License: Commercial](https://img.shields.io/badge/License-Commercial-orange.svg)](#dual-licensing--commercial-use)


Let's be honest: standard general-purpose compressors (Gzip, LZMA, Snappy, and even vanilla Zstandard) are brilliant at what they were designed for, but they have a blind spot. They treat every single input as a flat, opaque 1D stream of bytes. While feeding raw LiDAR scans, 4K framebuffers, IEEE-754 float matrices, or multi-axis CNC paths into a sliding-window compressor technically works, it forces the algorithm to guess geometric and mathematical structures that we already know exist. It's like putting a high-precision mechanical blueprint through an office shredder before trying to tape it back together.

KolmoX bridges this gap. It is an enterprise-grade, high-throughput lossless compression framework built on Kolmogorov Structural Preconditioning. Instead of treating data blindly, KolmoX understands the underlying topology of modern workloads, rearranging it into high-correlation and low-entropy planes before handing it over to entropy coders:

* **Domain-Aware Structural Transformations**: Automatically identifies data topology and applies deterministic, bit-exact transforms (such as Float32 byte-plane slicing to isolate sign/exponent bytes from high-entropy mantissas, 2D spatial delta modeling for FITS scientific imaging, CNC G-Code axis demuxing, and stereo PCM decorrelation) to eliminate structural correlation entropy.
* **KMX2 Multi-Stream Container**: Encapsulates primary and split auxiliary streams into a resilient 24-byte fixed-header format backed by high-speed Zstandard FSE entropy coding.
* **High Performance & Constant-Memory Streaming**: Powered by native C-accelerated transposition kernels reaching up to 826+ MB/s, featuring KolmoXStreamer for bounded-RAM streaming on multi-gigabyte files, and a standalone C-ABI (include/kolmox.h) for zero-overhead C/C++/Rust integration.

## Why KolmoX Matters: Today and in the Multi-Petabyte Future

We live in an era where data generation has outpaced network bandwidth and storage interconnect speeds.

* **The Scientific & AI Bottleneck**: Modern AI pipelines, LLM checkpointing, physics engines, and space telescopes (JWST, Roman) generate billions of IEEE-754 floating-point numbers. Standard compressors choke on shot noise and mantissa entropy. KolmoX delivers up to 28x+ on arrays and +22.8% net savings over Zstd on raw JWST FITS datasets without altering a single bit.
* **Smart Manufacturing & Industry 4.0**: Robotics, CNC machining, 3D additive manufacturing, and autonomous vehicle LiDAR streams churn out terabytes of continuous telemetry daily. Squeezing columnar telemetry by 40x–47x drastically cuts cloud egress bills and edge-to-cloud transmission latency.
* **Lossless is Non-Negotiable**: In medical imaging, astrophysics, engineering CAD, industrial telemetry, and legal compliance, lossy compression artifacts are unacceptable. KolmoX proves that "lossless" doesn't have to mean "poor compression ratios".

## Real-World Benchmark Results

All tests certify exact mathematical data restoration (zero precision loss, bit-exact roundtrip):

| Data Domain | Pipeline / Transform | Gzip (L9) | Zstd (Base) | KolmoX (KMX2) | Gain vs Zstd | Throughput (Comp / Decomp) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2D Raw Framebuffer / Raster (.bmp) | 2D Spatial Delta + Color Slicing | 2.10x | 4.30x | 86.03x | +1900.7% (20.0x) | ~240 MB/s / ~310 MB/s |
| Binary Register Packets (.bin) | Stride Autocorr + Demux | 2.65x | 4.83x | 55.53x | +1049.7% (11.5x) | ~180 MB/s / ~260 MB/s |
| LiDAR XYZ Point Cloud | Columnar Coordinate Isolation | 8.40x | 27.11x | 47.31x | +74.51% | 77.3 MB/s / 112.1 MB/s |
| Industrial Telemetry (.csv) | Columnar Demux + Quant Delta | 3.93x | 19.65x | 40.20x | +104.58% | ~120 MB/s / ~190 MB/s |
| CNC G-Code (.gcode) | Columnar Axis Separation | 4.20x | 5.69x | 29.25x | +414.06% | 18.8 MB/s / 30.8 MB/s |
| Scientific Float32 (.npy) | Byte-Plane Slicing (Sign/Exp/Mant) | 1.15x | 1.30x | 28.77x | +2113.1% | 826.3 MB/s / 750.0 MB/s |
| **Astrophysics FITS (JWST)** | **2D Modular Delta + Big-Endian Slicing** | **1.47x** | **1.47x** | **1.90x** | **+22.87% (-17.5 MB)** | ~225 MB/s / ~340 MB/s |
| Parametric 3D CAD Mesh (.obj) | Ordered Vertex Transpose | 4.38x | 8.42x | 14.07x | +67.10% | ~95 MB/s / ~140 MB/s |
| 4K & 5K Video Streams (60fps) | Temporal NVDEC + Delta-XOR | ~1.10x | ~1.15x | 3.15x – 6.56x | +173.9% ~ +470.4% | ~450 MB/s / ~600 MB/s |
| Pre-compressed 3D Archive (.3mf) | Inner Stream Re-quantization | 1.00x (Deflate) | 1.00x | 1.39x | +39.00% (+28.15% size) | ~110 MB/s / ~165 MB/s |
| Audio PCM 16-bit (.wav) | Stereo Decorrelation + Diff | 1.01x | 39.81x | 41.55x | +4.37% | 457.5 MB/s / 354.5 MB/s |
| x86 Binary Executable (.exe) | Branch Target Normalizer (BCJ) | 5.40x | 7.59x | 7.65x | +0.79% | ~380 MB/s / ~420 MB/s |

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
