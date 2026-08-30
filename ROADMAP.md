# KolmoX Engineering Roadmap

This document outlines the strategic milestones and technical roadmap for advancing **KolmoX**, a high-performance bit-exact compression framework.

---

## 🞷 Milestone Overview

```
Phase 1: Rich CLI & Telemetry [COMPLETED]
   │
   ▼
Phase 2: Multi-Threaded Chunked Pipeline [COMPLETED]
   │
   ▼
Phase 3: Extended CAD Formats (STEP / STL / OBJ) [COMPLETED]
   │
   ▼
Phase 4: PyPI Packaging & Automated CD Release [COMPLETED]
```

---

## 📌 Phase 1: Modern CLI Interface & Live Telemetry (`v0.2.0`)
- [x] **Rich Terminal Integration**: Structured output via `rich` console.
- [x] **Post-Compression Summary Cards**: Real-time throughput (MB/s), duration, and compression ratios.
- [x] **Quiet/Scriptable Mode**: Headless support with `-q` / `--quiet` flag.

---

## 📌 Phase 2: Parallel Chunked Processing (`v0.3.0`)
- [x] **Dynamic Chunking Engine**: Multi-core streaming with `ProcessPoolExecutor`.
- [x] **Header Manifest V2**: `KMX2` format with per-block CRC32 integrity validation.
- [x] **High-Throughput Concurrency**: Memory-bounded chunked execution.

---

## 📌 Phase 3: Parametric CAD & Mesh Expansion (`v0.4.0`)
- [x] **STL Geometry Support**: Fast binary STL facet transposition (normal & triangle stripping).
- [x] **STEP / STP Preconditioning**: Structural parser for ISO 10303-21 STEP entities with float tokenization.
- [x] **Auto-Routing CLI**: Automatic geometry dispatcher across `.obj`, `.stl`, and `.step` / `.stp`.

---

## 📌 Phase 4: Distribution & CI/CD Packaging (`v1.0.0`)
- [x] **PEP 517 / PEP 621 Standard**: Standardized `pyproject.toml` with console entrypoint `kolmox`.
- [x] **Automated Release Workflow**: GitHub Actions release pipeline triggered on version tags.
- [x] **Full Regression Coverage**: 16 unit tests passing across all supported engines.

---

## 🏷 Version History

| Milestone | Target Version | Status | Key Feature Delivered |
| :--- | :--- | :--- | :--- |
| **Phase 1** | `v0.2.0` | **Released** | Rich CLI, Live Progress & Performance Tables |
| **Phase 2** | `v0.3.0` | **Released** | Parallel Chunked Processing & High-Throughput Engine |
| **Phase 3** | `v0.4.0` | **Released** | STEP / STL Parametric Preconditioners |
| **Phase 4** | `v1.0.0` | **Released** | Stable PyPI Package & Automated Release Pipeline |
