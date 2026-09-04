# Changelog

## [1.3.0] - 2026-09-04

### Changed — video payload format

`VideoEngine` now writes an **arithmetic delta mod 256** between consecutive
frames instead of an XOR. XOR is a poor fit for continuous data: two adjacent
values straddling a high bit produce a large residual (`127 ^ 128 = 255`) where
subtraction produces `1`.

Measured on 60 frames of real 5120x1440 gameplay footage, through the public
pipeline API with a bit-exact roundtrip assertion:

| | ratio | vs plain Zstd |
| :--- | ---: | ---: |
| KMXV1 XOR (previous) | 2.28x | +25.14% |
| **KMXV2 arithmetic (current)** | **2.79x** | **+38.87%** |

The output is 18.34% smaller. The synthetic video row went from +43.45% to
+56.74%.

**Backward compatibility is preserved.** The 5-byte magic doubles as the format
version: `KMXV2` is written from this release on, and `KMXV1` payloads produced
by earlier releases still decode bit-exact. This is covered by
`tests/test_video_format_versions.py`, which asserts explicitly that a legacy
container round-trips through the public pipeline unchanged.

Containers written by 1.3.0 are **not** readable by kolmox <= 1.2.1, which only
recognises `KMXV1`.

### Security

- `compress_with_script()` and `decompress_container()` now execute synthesized
  scripts with `__builtins__` restricted to a small arithmetic subset, instead
  of the full default builtins. Measured before the change: an empty globals
  dict still granted 158 builtins including `open`, `eval` and a working
  `import os`. **This is hardening, not a sandbox** — escapes from a
  restricted-builtins `exec()` are well documented. The real control remains
  the `allow_code_execution` gate.
- The gate's fallback is now **fail-closed**: `getattr(self,
  'allow_code_execution', False)`. It had been `True`, so an object missing the
  attribute would have been allowed to execute. This regression had been
  reintroduced three times by patch scripts; it is now pinned by
  `test_script_execution_is_refused_by_default`.
- README documents the synthesis path as unsafe by design, opt-in only, and
  never to be enabled for third-party containers.

### Removed — dead code

Three modules were retired after verifying nothing reachable depended on them:

- `core/chunker.py` — superseded by `core/chunked.py`, which the CLI actually
  uses. It was not importable: it depended on `sandbox/runner.py`.
- `sandbox/runner.py` — left syntactically broken by two quarantined patch
  scripts (an `IndentationError`, plus a guard referencing a `kwargs` the
  signature does not accept). The sandbox it provided was never used by the
  code path that actually executes scripts.
- `core/text_columnar.py` — not bit-exact (it decodes with `errors="replace"`,
  destroying non-UTF-8 bytes irreversibly) and a worse duplicate of
  `engines/columnar_text.py`. Its only remaining consumer,
  `benchmarks/real_world_bench.py`, was retired with it: that benchmark applied
  transforms outside the pipeline, which this project's methodology note
  declares non-reportable.

Before removal, the corruption risk was traced end to end and found
**unreachable**: `chunker.py` already round-trip-verified before accepting the
columnar path, it was not importable, nothing imported it, and the real chunked
CLI path never touched it. Verified bit-exact on 7 edge cases including pure
binary.

### Fixed

- The two long-standing failing tests now pass by opting in explicitly. The
  suite is **56/56 green**.

## [1.2.0] - 2026-09-03

### Benchmark correction notice

**The benchmark table published in v1.1.2 was not reproducible and has been
replaced.** Anyone who evaluated KolmoX on the strength of those figures should
re-read the corrected table before drawing conclusions.

The published numbers had been written into `README.md` and `docs/WHITEPAPER.md`
by text-substitution scripts rather than measured. Several rows described
transforms that no code path could reach: the domains were declared in
`DomainType` but `DomainRouter` never dispatched to them, so the advertised
transform never ran. Others were inflated, or measured by calling engine classes
directly — which omits the 24-byte KMX2 container header and bypasses the
adaptive competitive fallback, both of which make the real figures worse.

All eleven rows have been re-measured through the public
`KolmoXPipeline.compress_bytes()` / `decompress_bytes()` API with a bit-exact
roundtrip assertion on each:

| Domain | Published in v1.1.2 | Measured | Cause |
| :--- | ---: | ---: | :--- |
| Binary Register Packets | +76.54% | **+54.67%** | domain unreachable from the router |
| Industrial Telemetry (.csv) | +52.47% | **+44.24%** | transform did not exist |
| Parametric CAD Mesh (.obj) | +26.45% | **+63.12%** | transform did not exist |
| 2D Natural Sensor Raster | +28.26% | **+40.38%** | engine not wired to the router |
| Astrophysics FITS (JWST) | +22.87% | **+16.31%** | inflated |
| CNC G-Code | +36.78% | **+64.10%** | different dataset |
| LiDAR XYZ Point Cloud | +20.00% | **+58.79%** | different dataset (see note) |
| Dense Float32 Buffer | +18.45% | **+31.86%** | different dataset |
| Audio PCM 16-bit | +6.09% | **+60.48%** | different dataset |
| x86 Binary Executable | 0.00% | **-0.46%** | header hidden by a `min()` in the benchmark |

Ten of the eleven datasets are synthetic and are now disclosed as such per row.
Only the Astrophysics FITS row uses a real-world production capture. The claim
"Zero synthetic interpolation" has been removed: it was false.

Note on LiDAR: the dataset is a deterministic arithmetic ramp, which is why even
plain Zstd reaches 27.11x on it. The row demonstrates that the transform
functions; it is not representative of real scanner output and should not be
read as a performance claim.

### Added

- `ColumnarTextEngine`: groups lines by structural shape and transposes each
  group column-major. Bit-exact by construction (byte-level split and join, no
  decoding), verified on ten edge cases plus an 800-case fuzz run.
- `RasterEngine.transform_bmp()` / `inverse_bmp()`: parses standard uncompressed
  BMP (40-byte `BITMAPINFOHEADER`, 24/32 bpp, BI_RGB) including 4-byte row
  padding. Unsupported variants raise, so the pipeline falls back to plain Zstd.
- `KMXVRAW1`: self-describing container for raw multi-frame video sequences,
  letting `VIDEO_TEMPORAL` accept a single blob.
- `TODO.md`, recording engines that exist and pass tests but are unreachable
  from the router.
- `CHANGELOG.md` and `.gitattributes`.

### Changed

- **Four domains are now actually routed.** `BINARY_PACKETS` (StrideEngine),
  `RASTER_2D` (RasterEngine), `VIDEO_TEMPORAL` (VideoEngine), and
  `TELEMETRY_CSV` / `CAD_MESH_OBJ` (ColumnarTextEngine, replacing a trivial
  header/body split worth 0%).
- `RasterEngine.filter_2d_plane` vectorized in NumPy: ~2.6 MB/s → ~95 MB/s.
  Decoding retains an inherent sequential dependency and stays at ~2.4 MB/s.
- `VideoEngine.decompress_sequence` uses `np.bitwise_xor.accumulate` instead of
  a Python loop.
- `benchmarks/benchmark_extended.py` measures the real pipeline instead of
  simulating the adaptive fallback with `min(candidate, baseline)`, asserts
  bit-exactness on every domain, exits non-zero on failure, and covers all ten
  synthetic domains instead of five.
- The whitepaper's FITS section described `FitsEngine` as the active path; the
  router dispatches to the generic `ScientificFloatEngine`. Corrected.

### Security

- `KolmoXPipeline.__init__` now defaults to `allow_code_execution=False`.
  Deserializing a legacy script container, or calling `compress_with_script()`,
  requires opting in explicitly.

### Compatibility

Containers written by v1.1.2 with `domain_id` 6 (`TELEMETRY_CSV`) or 7
(`CAD_MESH_OBJ`) cannot be read by v1.2.0: those domain ids now denote a
different transform. Decompression raises `ValueError` rather than returning
corrupted bytes.

In practice this is unlikely to affect anyone: v1.1.2's competitive fallback
compared the candidate against a plain Zstd baseline, and the trivial split was
consistently the larger of the two, so v1.1.2 stored `domain_id=0` for these
inputs. Every other domain id is unchanged and reads normally.

### Known issues

See `TODO.md`. The highest-priority item is that `TextColumnarEngine`
(used by `chunker.py`) is not bit-exact: it fails four of six edge cases,
because it decodes with `errors="replace"`, which destroys non-UTF-8 bytes
irreversibly.

## [1.1.2] - 2026-09-01

Initial PyPI release. **The benchmark figures in this release are not
reproducible — see the correction notice under 1.2.0.**
