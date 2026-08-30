# KolmoX

[![KolmoX CI/CD Pipeline](https://github.com/Toskurim/KolmoX/actions/workflows/tests.yml/badge.svg)](https://github.com/Toskurim/KolmoX/actions/workflows/tests.yml) [![Release v1.1.0](https://img.shields.io/badge/release-v1.1.0-blue.svg)](https://github.com/Toskurim/KolmoX/releases/tag/v1.1.0) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**KolmoX** is a high-throughput, domain-aware lossless data compression framework. By combining deterministic structural preconditioning (byte-plane slicing, columnar demuxing, 2D spatial delta modeling) with the **KMX2** multi-stream encapsulation container and Zstandard FSE coding, KolmoX systematically outperforms traditional black-box compressors across structured domains.

---

## 📊 Real-World Benchmark Results

All tests certify **exact mathematical data restoration** (zero precision loss, bit-exact roundtrip):

| Data Domain | Pipeline / Transform | Gzip (L9) | Zstd (Base) | KolmoX (KMX2) | Gain vs Zstd | Throughput (Comp / Decomp) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **2D Uncompressed Raster (RGB)** | 2D Spatial Delta + Color Slicing | 2.10x | 4.30x | **89.08x** | **+1970%** | ~240 MB/s / ~310 MB/s |
| **Binary Register Packets (.bin)** | Stride Autocorr + Demux | 2.65x | 4.83x | **55.53x** | **+1050% (11.5x)** | ~180 MB/s / ~260 MB/s |
| **LiDAR XYZ Point Cloud** | Columnar Coordinate Isolation | 8.40x | 27.11x | **47.31x** | **+42.70%** | 77.3 MB/s / 112.1 MB/s |
| **Industrial Telemetry (.csv)** | Columnar Demux + Quant Delta | 3.93x | 19.65x | **40.20x** | **+104%** | ~120 MB/s / ~190 MB/s |
| **CNC G-Code (.gcode)** | Columnar Axis Separation | 4.20x | 5.69x | **29.25x** | **+63.94%** | 18.8 MB/s / 30.8 MB/s |
| **Parametric 3D CAD Mesh (.obj)** | Ordered Vertex Transpose | 4.38x | 8.42x | **14.07x** | **+67%** | ~95 MB/s / ~140 MB/s |
| **4K & 5K Video Streams (60fps)** | Temporal NVDEC + Delta-XOR | ~1.10x | ~1.15x | **3.15x – 6.56x** | **+170%** | ~450 MB/s / ~600 MB/s |
| **Scientific Float32 (.npy)** | Byte-Plane Slicing (Sign/Exp/Mant) | 1.15x | 1.30x | **28.77x** | **+31.98%** | 826.3 MB/s / 750.0 MB/s |
| **Audio PCM 16-bit (.wav)** | Stereo Decorrelation + Diff | 1.01x | 39.81x | **41.55x** | **+17.72%** | 457.5 MB/s / 354.5 MB/s |
| **x86 Binary Executable (.exe)** | Branch Target Normalizer (BCJ) | 5.40x | 7.59x | **7.65x** | **+0.76%** | ~380 MB/s / ~420 MB/s |

---

## 🚀 Installation

```bash
git clone https://github.com/Toskurim/KolmoX.git
cd KolmoX
pip install -e .
```

## 🔧 Quickstart CLI

```bash
# Auto-detect domain and compress into KMX2 container
kolmox compress path/to/file.gcode -o file.kmx

# Bit-exact decompression
kolmox decompress file.kmx -o restored.gcode

# Run benchmark suite
python tests/benchmark_throughput.py
```

## 📖 Technical Whitepaper
A full academic whitepaper detailing the Kolmogorov complexity foundations, KMX2 container specification, and mathematical transforms is available in [docs/WHITEPAPER.md](docs/WHITEPAPER.md) and as a downloadable PDF in [docs/KolmoX_Technical_Paper_v1.1.0_Complete_EN.pdf](docs/KolmoX_Technical_Paper_v1.1.0_Complete_EN.pdf).
