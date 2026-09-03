# Changelog

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
