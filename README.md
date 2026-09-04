# KolmoX

[![PyPI version](https://img.shields.io/pypi/v/kolmox.svg)](https://pypi.org/project/kolmox/) [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)

> **Architectural Positioning**: KolmoX is **not** a general-purpose replacement for Zstandard, Snappy, or Deflate. 
> Exactly as the PNG Delta Filter or the FLAC Mid/Side Decorrelator operate ahead of Deflate, KolmoX is a **domain-specific structural preconditioner**. It linearizes physical coordinates, IEEE-754 mantissas, and multi-dimensional matrices *before* entropy coding, eliminating topological correlations that sliding-window (LZ77) engines cannot detect.
>
> For production workloads, use the dedicated engine classes directly (`FitsEngine`, `ScientificFloatEngine`, `GCodeEngine`, etc.). An **Adaptive Competitive Fallback** ensures KolmoX output is mathematically guaranteed never to exceed plain Zstandard.

---

### Evidence Tiers

* **✅ Tier 1 (Reproducible In-Script)**: Synthetic-but-realistic datasets generated programmatically via `python benchmarks/benchmark_extended.py`. Fully reproducible by any third party with zero external dependencies.
* **✅ Tier 2 (Reproducible from Public Archives)**: Real datasets from public archives with declared licenses - NASA/STScI JWST FITS, UCI industrial telemetry, LinuxCNC toolpaths, Zenodo CC0 meshes. Reproducible with `python benchmarks/download_datasets.py && python benchmarks/benchmark_real.py`, roughly 52 MB of download. Every entry declares its URL, license, size and SHA-256 checksum; the checksum is verified after download and a mismatch aborts rather than proceeding. Results, including the domains where the gain collapses, are in the [Real-World Data Benchmark](#real-world-data-benchmark) table below.

---

## Why KolmoX Matters: Today and in the Multi-Petabyte Future

We live in an era where data generation has outpaced network bandwidth and storage interconnect speeds.

* **The Scientific & AI Bottleneck**: Modern AI pipelines, LLM checkpointing, physics engines, and space telescopes (JWST, Roman) generate billions of IEEE-754 floating-point numbers. Standard compressors choke on shot noise and mantissa entropy. KolmoX delivers up to +54.67% on binary registers, +31.86% on dense vectors, and +16.31% net savings over Zstd on raw JWST FITS datasets without altering a single bit.
* **Smart Manufacturing & Industry 4.0**: Robotics, CNC machining, 3D additive manufacturing, and autonomous vehicle LiDAR streams churn out terabytes of continuous telemetry daily. Squeezing columnar telemetry by up to +44.24% drastically cuts cloud egress bills and edge-to-cloud transmission latency.
* **Lossless is Non-Negotiable**: In medical imaging, astrophysics, engineering CAD, industrial telemetry, and legal compliance, lossy compression artifacts are unacceptable. KolmoX proves that "lossless" doesn't have to mean "poor compression ratios".

## Benchmark Results by Domain

One row per supported domain, measured at Zstd levels 3 and 19. Most datasets
are synthetic (marked †); see [Real-World Data Benchmark](#real-world-data-benchmark)
below for results on downloadable public datasets.

All tests certify exact mathematical data restoration (zero precision loss, bit-exact roundtrip):

| Data Domain | Pipeline / Transform | Baseline (Zstd L3) | KolmoX (KMX2) | Gain vs Zstd-3 | Gain vs Zstd-19 ‡ | Throughput (Comp / Decomp) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CNC G-Code (.gcode)** † | Columnar Axis Separation | 5.69x | **15.84x** | **+64.10%** | +57.33% | ~24 MB/s / ~35 MB/s |
| **Parametric 3D CAD Mesh (.obj)** † | Prefix-Grouped Vertex Plane Slicing | 6.00x | **16.27x** | **+63.12%** | **+68.21%** | ~40 MB/s / ~80 MB/s |
| **Audio PCM 16-bit (.wav)** † | Stereo Mid/Side Decorrelation | 1.02x | **2.59x** | **+60.48%** | +38.78% | ~172 MB/s / ~284 MB/s |
| **LiDAR XYZ Point Cloud** † ¹ | Columnar Coordinate Slicing | 27.11x | **65.79x** | **+58.79%** | +23.37% | ~80 MB/s / ~106 MB/s |
| **Temporal Video Sequence (.kmxvraw)** † | Frame Arithmetic Delta (SIMD) | 1.00x | **2.31x** | **+56.74%** | **+60.22%** | ~148 MB/s / ~168 MB/s |
| **Binary Register Packets (.bin)** † | Stride Autocorr + Demux | 1.86x | **4.10x** | **+54.67%** | +44.38% | ~158 MB/s / ~1094 MB/s |
| **Industrial Telemetry (.csv)** † | Shape-Grouped Columnar Demux | 4.59x | **8.23x** | **+44.24%** | +35.59% | ~47 MB/s / ~98 MB/s |
| **2D Natural Sensor Raster (.bmp)** † | 2D Spatial Delta | 1.07x | **1.80x** | **+40.38%** | +33.59% | ~37 MB/s / ~2.4 MB/s |
| **Temporal Video (real gameplay)** ³ | Frame Arithmetic Delta (SIMD) | 1.70x | **2.79x** | **+38.87%** | not measured | ~87 MB/s / ~59 MB/s |
| **Dense Float32 Buffer (250k values)** † | IEEE-754 Byte-Plane Slicing | 1.29x | **1.89x** | **+31.86%** | +20.47% | ~236 MB/s / ~642 MB/s |
| **Astrophysics FITS (JWST) — real data** | IEEE-754 Byte-Plane Slicing (auto-routed) | 1.47x | **1.76x** | **+16.31%** | **+20.64%** | ~213 MB/s / ~714 MB/s |
| **x86 Binary Executable (.exe)** † ² | Adaptive Fallback (BCJ/Zstd) | 7.59x | **7.56x** | **-0.46%** | -0.46% | ~13 MB/s / ~879 MB/s |

> *Methodology: every row above was measured on 2026-09-03 by running the data through the public `KolmoXPipeline.compress_bytes()` / `decompress_bytes()` API - the same path a user gets - with a bit-exact roundtrip assertion on each. Figures produced by calling engine classes directly, outside the pipeline, are not reported here: they omit the 24-byte KMX2 container header and bypass the adaptive competitive fallback. Every † row is reproducible with `python benchmarks/benchmark_extended.py`, which regenerates each dataset from a fixed seed and re-asserts every roundtrip. Compression ratios are deterministic; the throughput columns are single-run samples and vary by roughly ±15% between runs.*
>
> † *Synthetic dataset, generated programmatically. Only the Astrophysics FITS row uses a real-world production capture (a 117 MB NASA/STScI JWST MIRI observation of the Carina Nebula, compressed whole-file through the automatic domain router). Extracting just the pixel plane with astropy and compressing that instead yields 1.26x → 1.61x (+21.41%).*
>
> ¹ *The LiDAR dataset is a deterministic arithmetic ramp, which is why even the plain Zstd baseline reaches 27.11x. It demonstrates the transform works, but it is **not** representative of real scanner output - treat this row as a mechanism check, not a performance claim.*
>
> ² *A 40 KB synthetic instruction stream; at that size the throughput timings are dominated by measurement noise.*
>
> ‡ *`python benchmarks/benchmark_extended.py --strong-baselines`. **This comparison is like-for-like**: level 19 is applied to both sides, so KolmoX's own internal compressor and its adaptive fallback both run at 19 against a Zstd-19 baseline. That is what makes the number meaningful - measuring KolmoX at level 3 against Zstd-19 would only show that level 19 compresses better, and would say nothing about whether the structural preconditioning is worth anything. The real-gameplay row is measured from a private 451 MB capture outside the reproducible script, and was not re-run at level 19.*
>
> *The flag also prints a Gzip-9 column. **That one is a reference point, not a measurement of structural value**: the pipeline uses Zstd internally and its backend is not configurable, so comparing against Gzip conflates two separate effects - the preconditioning and Zstd-vs-Gzip. Only the Zstd-19 column isolates the first.*
>
> *Level 19 costs roughly two orders of magnitude in compression speed (Zstd-3 reaches 179-2802 MB/s here, Zstd-19 only 3-13 MB/s). KolmoX at 19 is slower still, 1.4-10.1 MB/s, because the adaptive fallback compresses twice - once for the baseline it must beat, once for the candidate. At level 3 that doubling is negligible; at level 19 it doubles the most expensive operation in the pipeline.*
>
> **How to read the two gain columns.** *The preconditioning keeps its value against a far more aggressive entropy coder - no domain drops to zero or turns negative, and the transform is still selected everywhere it was at level 3. But how much value depends heavily on the domain, from +68.21% on the CAD mesh to +23.37% on LiDAR. Three domains actually improve at level 19, which a single column would have hidden. And the row that loses the most, LiDAR, is precisely the one whose dataset was artificially favourable to begin with: a deterministic arithmetic ramp that Zstd-19 finds on its own. That is an independent confirmation of the caveat in note ¹, not a coincidence.*
>
> ³ *Real data, and the honest counterpart to the synthetic video row above: 60 consecutive frames of 5120x1440 gameplay footage at full resolution, no downscaling. The gain is lower than the synthetic row's because the content is adversarial for a temporal transform - 61% of bytes change between consecutive frames, up to 89% in the busiest pairs. The transform still wins the competitive check, so it is kept rather than discarded. Read the two video rows together: the synthetic figure is what low-motion content gives, not what video gives in general.*
>
> *Both video rows improved when the engine switched from an XOR delta to an arithmetic delta mod 256. XOR is a poor fit for continuous data - two adjacent values straddling a high bit produce a large residual (127 ^ 128 = 255) where subtraction gives 1. On this same real footage the change took the gain from +25.14% to +38.87% (output 18.34% smaller). The payload format is versioned by its magic: new containers are written as `KMXV2`, and `KMXV1` containers produced by earlier releases still decode bit-exact - covered by `tests/test_video_format_versions.py`.*
>
> *Domain gains depend on the data actually having the structure the transform exploits. On a high-entropy input - a random-walk mesh with 6 decimals of noise per coordinate, or the x86 stream above - the transform yields nothing, the adaptive competitive fallback discards it, and the stored result is the plain Zstd baseline plus the 24-byte KMX2 header. The raster decompression figure (~2.4 MB/s) reflects a pure-Python pixel loop whose sequential dependency has not yet been ported to the C extension; it is the current honest number, not a target.*

## Real-World Data Benchmark

The table above runs on synthetic datasets. This one runs on public archives
with declared licenses, downloadable by anyone:

```bash
python benchmarks/download_datasets.py   # ~52 MB
python benchmarks/benchmark_real.py
```

**How to read this table.** Where the parser recognises the real data, the gain
holds: FITS keeps +14.83% against +16.31% on the synthetic equivalent, and a
clean CSV keeps +24.85%. Where it does not, the gain collapses and the adaptive
fallback correctly stores plain Zstd instead.

Two domains collapsed when this benchmark was first run, and **both turned out
to be dialect-recognition defects rather than limits of the approach**. Neither
was fixed by improving a transform: in both cases the same transform simply
started seeing the file's real shape. G-code went from -0.06% to +21.93% once
attached line numbers and modal commands were handled, and the semicolon CSV
went from +11.51% to +26.29% once the delimiter was detected instead of assumed.
Read the footnotes before quoting either number - the G-code one in particular
improves for a reason that does not generalise as far as the figure suggests.

We publish the failures next to the successes because the gap between them is
the useful part, and because it is what told us where to look.

| Dataset | Source | License | Size | Baseline (Zstd L3) | KolmoX | Gain | Outcome |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| **Astrophysics FITS** (JWST SMACS 0723, MIRI f770w) | MAST / STScI | Public domain | 35.0 MB | 1.76x | **2.07x** | **+14.83%** | transform used |
| **Industrial Telemetry** (appliances energy, clean CSV) | UCI ML Repository | CC BY 4.0 | 11.4 MB | 6.02x | **8.01x** | **+24.85%** | transform used |
| **Industrial Telemetry** (air quality, semicolon CSV) | UCI ML Repository | CC BY 4.0 | 0.8 MB | 3.04x | **4.13x** | **+26.29%** | transform used (a) |
| **CNC G-Code** (LinuxCNC `3D_Chips.ngc`) | LinuxCNC | GPL-2.0 (b) | 0.2 MB | 4.79x | **6.13x** | **+21.93%** | transform used, but read (c) |
| **CAD Mesh** (binary STL, WVS) | Zenodo 5034614 | CC0 | 3.1 MB | 1.86x | 1.86x | **-0.00%** | **fallback** (d) |
| **CAD Mesh** (binary STL, Ambulacral) | Zenodo 5034614 | CC0 | 0.7 MB | 2.57x | 2.56x | **-0.01%** | **fallback** (d) |

> *Every row was measured through the same public API and bit-exact roundtrip assertion as the synthetic table. "fallback" means the domain transform lost against a plain Zstd encoding of the same input, so the pipeline stored the baseline: the residual cost is the 24-byte KMX2 header.*
>
> (a) *This file uses semicolons as the field delimiter and commas as the decimal separator, as European locales do. The demux used to assume commas, so it split the decimals and produced ragged rows: this row read **+11.51%**. The delimiter is now detected from the data rather than assumed, and the row reads **+26.29%** - the 14.78 points the diagnosis predicted, recovered in full. **The improvement is not a better transform; it is the same transform finally seeing the file's real dialect.** Together with the G-code row this closes both of the collapses that the real-world benchmark exposed. The clean CSV and the synthetic dataset are unchanged, since detection selects the comma for them and the path is byte-identical to before.*
>
> (b) *Downloaded for local benchmarking only. The file carries an internal copyright notice and is not redistributed with this repository.*
>
> (c) **The gain comes from line numbers, not coordinates - do not read this row as "G-code preconditioning works on real files".** *On this file the engine extracts `X=0, Y=0, Z=0, N=4691`: zero coordinates. The 4,691 extracted values are RS-274/NGC line numbers, which are metadata; collapsing them out of the template is what produces the +21.93%. The coordinates - the actual payload, 4,684 values - stay untouched, because this file expresses them as parametric expressions (`Y[#<yscale>*53.293]`) rather than literals, and the engine deliberately does not parse that dialect's expression syntax. Measurable headroom therefore remains on this file. Before the fix this row read -0.06% with the transform discarded: the engine matched only lines beginning with `G1 `, whereas 4,690 of 4,691 lines here prefix the line number with no separating space and omit the G-word entirely (modal G-code). Both of those are now handled. See [TODO.md](TODO.md), where the earlier, incorrect diagnosis is also recorded.*
>
> (d) *Confirmed by measurement, and the two obvious fixes were tested and rejected: transposing at the 50-byte record stride costs -32.21%, and float-aware byte-plane slicing costs -31.60%. Adjacent triangles in an STL share vertices, so the raw stream carries local redundancy that LZ77 exploits and any transposition destroys. On this data the fallback is already making the right choice.*

**Declared gaps.** Two domains in the synthetic table have no real-world
counterpart here, and we would rather state that than fill it with data of
uncertain provenance. **LiDAR**: no source found with both a suitable license
and a usable format - USGS 3DEP is unreachable, and the one live alternative is
LAZ, which would require `laspy` or PDAL and break the Tier 1 promise of zero
external dependencies. **Audio**: no source with direct WAV files at a
reasonable size - the smallest real option costs 157 MB of network transfer for
a single usable file.

## Project Status

KolmoX is young and under active development. More domains, wider coverage of
real-world dialects, and performance work are all in progress.

**Known limitations are stated rather than omitted**, and each is tracked in
[TODO.md](TODO.md) with the measurements behind it:

- **LiDAR and Audio have no real-world benchmark.** No public source was found
  that combines a suitable license with a format usable without extra
  dependencies. Both appear in the synthetic table only, and the gap is declared
  in the real-world one.
- **Raster decoding runs at roughly 2.4 MB/s.** The unfilter step has an
  inherent sequential dependency - each pixel needs its already-reconstructed
  neighbour - so it cannot be vectorised in NumPy and has not yet been ported to
  the C extension. Encoding is vectorised and runs at about 95 MB/s.
- **G-code parametric expressions are not extracted.** Where a file writes
  `Y[#<yscale>*53.293]` instead of a literal, the coordinate stays inside the
  template. Deciding whether to handle that dialect is waiting on a second real
  G-code file from a different origin, so that the choice is not made from a
  single example.
- **STEP files are not routed.** `MeshCADEngine` can parse them, but
  `detect_domain()` does not recognise the format.
- **Binary STL gains nothing**, and measurement suggests that is correct rather
  than fixable: two structural transforms were tried and both were substantially
  worse than plain Zstd. The adaptive fallback handles it.

Every published figure is produced by running the code, never written by hand.
The synthetic table is reproducible with `python benchmarks/benchmark_extended.py`
and the real-world table with `python benchmarks/download_datasets.py &&
python benchmarks/benchmark_real.py`, about 52 MB of download. Both assert a
bit-exact roundtrip on every domain and exit non-zero if any fails. Where a
transform loses to plain Zstd, that is published too.

## Code Synthesis: Unsafe by Design, Opt-In Only

KolmoX carries a legacy compression path that stores a small Python generator
program alongside a residual, and re-runs that program to reconstruct the data:
`compress_with_script()` and the `KMX1` containers read by
`decompress_container()`.

**This path executes arbitrary Python.** It is disabled by default and must be
switched on explicitly:

```python
pipeline = KolmoXPipeline(allow_code_execution=True)   # never on untrusted input
```

Opening a third-party `KMX1` container with that flag enabled is equivalent to
running code its author chose. Treat such files exactly as you would treat a
pickle or an executable from the same source.

The interpreter's `__builtins__` are restricted to a small arithmetic subset
before the script runs. **This is hardening, not a sandbox** — escapes from a
restricted-builtins `exec()` are well documented, typically by walking an
object's class hierarchy to reach broader machinery. It raises the bar against
accidents; it does not make hostile input safe. The real control is the
`allow_code_execution` gate, which is fail-closed by default.

Every other domain in the table above is pure data transformation and executes
nothing.

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
