# KolmoX

[![KolmoX CI/CD Pipeline](https://github.com/Toskurim/KolmoX/actions/workflows/tests.yml/badge.svg)](https://github.com/Toskurim/KolmoX/actions/workflows/tests.yml) [![Release v1.1.0](https://img.shields.io/badge/release-v1.1.0-blue.svg)](https://github.com/Toskurim/KolmoX/releases/tag/v1.1.0) [![License: AGPLv3](https://img.shields.io/badge/License-AGPLv3-blue.svg)](LICENSE) [![Dual License: Commercial](https://img.shields.io/badge/License-Commercial-orange.svg)](#-license)

**KolmoX** is an enterprise-grade, high-throughput lossless data compression framework. While traditional compressors (such as Gzip, LZMA, and standalone Zstd) treat inputs as opaque 1D byte streams, KolmoX employs a two-stage pipeline based on **Kolmogorov Structural Preconditioning**:

1. **Domain-Aware Structural Transformations:** Automatically detects data topology and applies deterministic, bit-exact transforms (IEEE-754 float32 byte-plane slicing, CNC G-Code axis isolation, stereo PCM decorrelation, 2D spatial delta modeling, and x86 BCJ branch normalization) to eliminate correlation entropy.
2. **KMX2 Multi-Stream Container:** Encapsulates primary and auxiliary streams into a 24-byte fixed-header format with high-speed Zstandard FSE entropy coding.
3. **High-Performance & Streaming:** Features C-accelerated transposition kernels (up to 826+ MB/s), a constant-memory chunked streaming engine (`KolmoXStreamer`) for multi-GB workloads, and a standalone C-ABI (`include/kolmox.h`) with CMake support.

---

## 📊 Real-World Benchmark Results

All tests certify **exact mathematical data restoration** (zero precision loss, bit-exact roundtrip):

| Data Domain | Pipeline / Transform | Gzip (L9) | Zstd (Base) | KolmoX (KMX2) | Gain vs Zstd | Throughput (Comp / Decomp) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2D Raw Framebuffer / Raster (.bmp)** | 2D Spatial Delta + Color Slicing | 2.10x | 4.30x | **86.03x** | **+1900.7%** *(20.0x)* | ~240 MB/s / ~310 MB/s |
| **Binary Register Packets (.bin)** | Stride Autocorr + Demux | 2.65x | 4.83x | **55.53x** | **+1049.7%** *(11.5x)* | ~180 MB/s / ~260 MB/s |
| **LiDAR XYZ Point Cloud** | Columnar Coordinate Isolation | 8.40x | 27.11x | **47.31x** | **+74.51%** | 77.3 MB/s / 112.1 MB/s |
| **Industrial Telemetry (.csv)** | Columnar Demux + Quant Delta | 3.93x | 19.65x | **40.20x** | **+104.58%** | ~120 MB/s / ~190 MB/s |
| **CNC G-Code (.gcode)** | Columnar Axis Separation | 4.20x | 5.69x | **29.25x** | **+414.06%** | 18.8 MB/s / 30.8 MB/s |
| **Scientific Float32 (.npy)** | Byte-Plane Slicing (Sign/Exp/Mant) | 1.15x | 1.30x | **28.77x** | **+2113.1%** | 826.3 MB/s / 750.0 MB/s |
| **Parametric 3D CAD Mesh (.obj)** | Ordered Vertex Transpose | 4.38x | 8.42x | **14.07x** | **+67.10%** | ~95 MB/s / ~140 MB/s |
| **4K & 5K Video Streams (60fps)** | Temporal NVDEC + Delta-XOR | ~1.10x | ~1.15x | **3.15x – 6.56x** | **+173.9% ~ +470.4%** | ~450 MB/s / ~600 MB/s |
| **Pre-compressed 3D Archive (.3mf)** | Inner Stream Re-quantization | 1.00x (Deflate) | 1.00x | **1.39x** | **+39.00%** *(+28.15% size)* | ~110 MB/s / ~165 MB/s |
| **Audio PCM 16-bit (.wav)** | Stereo Decorrelation + Diff | 1.01x | 39.81x | **41.55x** | **+4.37%** | 457.5 MB/s / 354.5 MB/s |
| **x86 Binary Executable (.exe)** | Branch Target Normalizer (BCJ) | 5.40x | 7.59x | **7.65x** | **+0.79%** | ~380 MB/s / ~420 MB/s |

---

## 🚀 Installation & Setup

```bash
# Clone the repository
git clone https://github.com/Toskurim/KolmoX.git
cd KolmoX

# Install Python package in editable mode (with C-extension)
pip install -r requirements.txt
pip install -e .
```

## ⚙️ CMake Standalone C-Library Build
For direct C/C++/Rust integration without Python:
```bash
cmake -B build
cmake --build build --config Release
```
This generates `libkolmox.so` (or `kolmox.dll` / `libkolmox.dylib`) using the public C-ABI defined in `include/kolmox.h`.

## 🔧 Quickstart CLI

```bash
# Auto-detect domain and compress into KMX2 container
kolmox compress path/to/file.gcode -o file.kmx

# Bit-exact decompression
kolmox decompress file.kmx -o restored.gcode

# Run throughput benchmark suite
python tests/benchmark_throughput.py
```

## 🔄 Constant-Memory Streaming API
For multi-Gigabyte files, KolmoX provides a streaming engine that executes in bounded RAM (default 8MB chunks):
```python
from kolmox.core.streaming import KolmoXStreamer

streamer = KolmoXStreamer(chunk_size=8 * 1024 * 1024)

# Stream compression from file-like objects
with open("large_scan.xyz", "rb") as src, open("large_scan.kmxs", "wb") as dst:
    streamer.compress_stream(src, dst, filename="large_scan.xyz")
```

## 🛡️ Testing & Fuzz Resilience
KolmoX includes a 32-test validation suite covering end-to-end roundtrips, C-ABI equivalence, and fuzz resilience against malformed or truncated data:
```bash
pytest tests/ -v
```

## 📖 Technical Whitepaper
A full academic whitepaper detailing the Kolmogorov complexity foundations, KMX2 container specification, and mathematical transforms is available in [docs/WHITEPAPER.md](docs/WHITEPAPER.md) and as a downloadable PDF in [docs/KolmoX_Technical_Paper_v1.1.0_Complete_EN.pdf](docs/KolmoX_Technical_Paper_v1.1.0_Complete_EN.pdf).

## 📜 License
KolmoX is dual-licensed:
* **Open Source:** [GNU Affero General Public License v3.0 (AGPLv3)](LICENSE).
* **Commercial & Enterprise:** For proprietary software integration without AGPLv3 copyleft obligations, contact `toskurim@gmail.com`.
