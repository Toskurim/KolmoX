# KolmoX Engineering Roadmap

This document outlines the strategic milestones and technical roadmap for advancing **KolmoX**, a high-performance bit-exact compression framework.

---

## 🞷 Milestone Overview

```
Phase 1: Rich CLI & Telemetry
   │
   ▼
Phase 2: Multi-Threaded Chunked Pipeline (Large Files)
   │
   ▼
Phase 3: Extended CAD Formats (STEP / STL / IGES)
   │
   ▼
Phase 4: PyPI Packaging & Automated CD Release
```

---

## 📌 Phase 1: Modern CLI Interface & Live Telemetry (Current)
- [ ] **Rich Terminal Integration**: Replace basic stdout logging with styled output via `rich`.
- [ ] **Live Progress Bars**: Real-time progress tracking displaying throughput (MB/s), ETA, and elapsed time.
- [ ] **Post-Compression Summary Cards**: Render formatted result tables showing:
  - Input & Output byte sizes.
  - Compression ratio ($X.XX\times$) and space savings percentage.
  - Processing duration and peak throughput.
- [ ] **Quiet/Scriptable Mode**: Add `--quiet` / `-q` flags to suppress visual UI during headless scripts or CI runs.

---

## 📌 Phase 2: Parallel Chunked Processing (Large-Scale Data)
- [ ] **Dynamic Chunking Engine**: Split large files (>128 MB) into independent, parallelizable blocks (16–64 MB).
- [ ] **Multi-Process Execution**: Utilize Python's `ProcessPoolExecutor` to saturate all CPU cores during preprocessing and compression.
- [ ] **Header Manifest V2**: Extend container metadata with chunk boundary offsets and per-chunk checksums (CRC32/SHA-256) for parallel random-access decompression.
- [ ] **Memory-Bounded Streaming**: Ensure strict peak RAM limits (<2 GB) even when processing files exceeding 50 GB.

---

## 📌 Phase 3: Parametric CAD & Mesh Expansion
- [ ] **STL Geometry Support**: Binary and ASCII STL vertex deduplication and triangle strip delta encoding.
- [ ] **STEP / STP Preconditioning**: Structural parser for ISO 10303-21 STEP entities, isolating topological structures from numeric float matrices.
- [ ] **Adaptive Floating-Point Predictor**: Second-order polynomial extrapolation for consecutive vertex coordinates.

---

## 📌 Phase 4: Distribution & CI/CD Packaging
- [ ] **Automated PyPI Release Workflow**: GitHub Actions trigger on git tag to build source distributions (`sdist`) and binary wheels (`bdist_wheel`).
- [ ] **Pre-compiled C/CUDA Extensions**: Package hardware-accelerated NVDEC/CUDA bridge for zero-setup installation.
- [ ] **Cross-Platform Test Matrix**: Continuous verification across Ubuntu, Windows, and macOS runners on Python 3.10–3.13.

---

## 🏷 Version Target Table

| Milestone | Target Version | Key Feature Delivered |
| :--- | :--- | :--- |
| **Phase 1** | `v0.2.0` | Rich CLI, Live Progress & Performance Tables |
| **Phase 2** | `v0.3.0` | Parallel Chunked Processing & High-Throughput Engine |
| **Phase 3** | `v0.4.0` | STEP / STL Parametric Preconditioners |
| **Phase 4** | `v1.0.0` | Stable PyPI Package & Automated Release Pipeline |
