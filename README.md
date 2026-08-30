# KolmoX ⚡

[![CI Status](https://github.com/toskurim/KolmoX/workflows/CI/badge.svg)](https://github.com/toskurim/KolmoX/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)

**KolmoX** is a high-performance, **100% bit-exact** compression framework designed to surpass generic entropy coders (like standard Gzip and Zstandard) by combining **structural domain-specific preconditioners**, **geometric/columnar transforms**, **hardware-accelerated decompression (CUDA/NVDEC)**, and **model-driven synthesis**.

---

## 🚀 Key Features

- **100% Bit-Exact Guarantee:** Flawless mathematical reconstruction verified via cryptographic hash (SHA-256) across all supported data domains.
- **Domain-Specific Preconditioning:**
  - **CAD & 3D Mesh Engine:** Vertex coordinate separation and planarization for `.obj` files while strictly preserving line order.
  - **Text & Telemetry Columnar Demuxer:** Contiguous column reorganization for industrial logs, CSVs, and tabular streams.
  - **Binary Stride Demuxer:** Automatic periodic binary interleaving detection via autocorrelation.
  - **2D & Temporal Video Stream Engine:** Spatial and temporal predictive differences (Delta-XOR) with NVDEC/CUDA hardware acceleration for uncompressed video streams (high-framerate 1080p, 4K UHD, and 5K @ 60 FPS).
- **Generative Synthesis (LLM & Heuristic):** Generation and application of compact predictive deltas on algorithmically reproducible payloads.
- **Multi-Thread & Streaming Pipeline:** Asynchronous chunk processing with robust pipe buffers for high-throughput streaming.

---

## 📊 Real-World Benchmark Results

All tests certify exact mathematical data restoration (zero precision loss):

| Data Domain | Pipeline / Format | Gzip (Lvl 9) | Zstd (Lvl 19) | **KolmoX (Structural)** | Gain vs Zstd |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Industrial Telemetry (`.csv`)** | Columnar Demux + Zstd | 3.93x | 19.65x | **40.20x** | **+104%** |
| **Binary Register Packets (`.bin`)** | Stride Autocorr + Demux | 2.65x | 4.83x | **55.53x** | **+1050% (11.5x)** |
| **Parametric 3D CAD Mesh (`.obj`)** | Ordered Vertex Transpose | 4.38x | 8.42x | **14.07x** | **+67%** |
| **2D Uncompressed Raster (RGB)** | 2D Spatial Delta | 2.10x | 4.30x | **89.08x** | **+1970%** |
| **4K & 5K Video Streams (60fps)** | CUDA / NVDEC + Delta-XOR | ~1.10x | ~1.15x | **3.15x – 6.56x** | **+170%** |

---

## 🛠️ Installation

```bash
# Clone repository
git clone https://github.com/toskurim/KolmoX.git
cd KolmoX

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

---

## 💻 CLI Usage

### Lossless Video Stream Compression & Decompression

KolmoX includes an asynchronous streaming engine using FFmpeg and GPU acceleration (CUDA) to compress and restore high-resolution RAW video streams:

```bash
# Compress video stream with NVDEC/CUDA acceleration
python -m src.kolmox.cli.main compress-video "input_video.mp4" "output_stream.kmxv" --max-frames 1000

# Decompress container restoring bit-exact RAW stream
python -m src.kolmox.cli.main decompress-video "output_stream.kmxv" "restored_stream.raw"
```

### Generic File Compression & Structural Pipeline

```bash
# Generic file compression
python -m src.kolmox.cli.main compress "dataset.csv" "dataset.kmx" -l 19

# Decompression
python -m src.kolmox.cli.main decompress "dataset.kmx" "restored.csv"
```

---

## 🧪 Test Suite & Validation

Run the full unit test suite with bit-exact verification:

```bash
pytest tests/ -v
```

Run the real-world benchmark suite:

```bash
python benchmarks/real_world_bench.py
```

---

## 📄 License

Distributed under the **MIT** License. See [LICENSE](LICENSE) for details.
