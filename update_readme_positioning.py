with open("README.md", "r", encoding="utf-8") as f:
    readme = f.read()

intro_text = """# KolmoX

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

"""

marker = "## Why KolmoX Matters"
header_idx = readme.find(marker)
if header_idx != -1:
    readme = intro_text + readme[header_idx:]
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)
    print("README.md aggiornato con successo!")
else:
    print("Marker non trovato.")
