# Changelog

## [1.3.1] - 2026-10-24

**Data-loss fix. Replaces 1.3.0, which has been yanked from PyPI.** 1.3.0 could
return different bytes from the ones it was given, with exit code 0 and no
error. Everyone on 1.3.0 should upgrade, and any container written by 1.3.0
for the point cloud, audio or raster domains should be checked against its
original if the original still exists.

### Fixed — silent data loss

Root cause: `compress_bytes()` kept the domain candidate whenever it was
smaller than the plain-Zstd baseline, and checked nothing else. An engine that
threw data away therefore *won*, because it had thrown data away. Three engines
did:

| Engine | Input that lost data in 1.3.0 | What came back |
| :--- | :--- | :--- |
| `PointCloudEngine` | `.xyz` with 4+ columns, comments, header lines, tab separators, CRLF; **any numeric table with no extension** (routed here by the heuristic) | lines without exactly 3 fields dropped; a 637 KB 4-column file came back as 7 bytes; tabs/CRLF rewritten |
| `AudioPCMEngine` | WAV whose PCM length is not a multiple of 4; RIFF chunks after `data` (`LIST`/`INFO`, `id3 `) | tail and trailing chunks dropped |
| `RasterEngine` | BMP with non-zero row padding | padding rewritten as zeros |

Two independent fixes, either of which alone would have prevented the loss:

1. **Invertibility gate** (`pipeline.py`). A candidate is decompressed through
   the real reader, `decompress_bytes()`, and compared byte for byte with the
   input *before* its size is looked at. Any exception counts as a failure.
   With only this change, all eleven known loss cases fall back to the Zstd
   baseline and return bit-exact.
2. **The engines are fixed at source**, with new sidecar formats marked by a
   magic so that the old ones are still read:
   - `KMXP2` — point cloud: arbitrary column count, space or tab, per-line CR,
     comments/headers/blank lines kept verbatim. The transform is a bijection
     by construction. A whole-buffer fast path handles the common uniform case.
   - `KMXA2` — audio: the WAV header, the PCM tail and everything after the
     `data` chunk are stored. The `data` chunk is now found by walking RIFF
     chunk sizes instead of `find(b"data")`, which could land inside another
     chunk.
   - `KMXR2` — raster: row padding is stored when it is not all zero (zero
     padding still costs nothing).

   With the gate *and* the fixes, the eight point-cloud and two audio cases are
   no longer just safe but compressed again by their domain transform (domain
   id 4 or 3 instead of 0), and a BMP with non-zero padding keeps the raster
   transform whenever the 2D filter pays off (measured on a smooth 201x150
   image: domain 8, bit-exact, same ratio as with zero padding within 1%).

### Changed — point-cloud auto-detection

Without a file extension, a file used to be routed to `POINTCLOUD_XYZ` if its
first lines merely *started* with three floats (`1 2 3 hello` qualified). Now
every sampled line must be entirely numeric, with the same column count (3 to
16) and the same separator; leading `#`/`//` comments and blank lines are
skipped, a comment in the middle of the data disqualifies the file. Files with
`.xyz`/`.pts` are routed as before.

### Added — integrity checking

- Every Zstd frame written by the pipeline carries an **XXH64 content
  checksum** (`write_checksum=True`, 4 bytes per frame). A corrupted or
  tampered payload now raises `ZstdError` instead of decompressing into
  different bytes.
- The original size declared in the KMX2 header is **checked on read**.
- Not covered: the magic, version and domain-id fields of the 24-byte header.
  Covering them needs a header format change and is listed in TODO.md.

### Added — property-based test suite

`tests/test_properties.py`, built on `hypothesis` (now in `requirements.txt`
and in the `dev` extra): roundtrip with auto-detection on structured
near-valid inputs (P1), every transform is a bijection or rejects the input
(P2), roundtrip with every domain forced on arbitrary bytes (P3), never larger
than the baseline (P4), a tampered container never decodes silently (P5), and
containers written by 1.3.0 still decode (P6, fixtures in
`tests/fixtures/legacy_v130/`). Checked against history: the suite fails 7
tests on 1.3.0 and 4 on the gate-only commit, and passes on 1.3.1 — also with
2,000 examples per property. Full suite: 141 passed.

### Performance

The gate is not free. A/B in one process, only the verification neutralised,
compression time:

| dataset | MB | level 3 | level 9 | level 19 |
| :--- | ---: | ---: | ---: | ---: |
| linuxcnc_3d_chips.ngc | 0.2 | +47.2% | +30.0% | +3.6% |
| AirQualityUCI.csv | 0.7 | +46.0% | +26.0% | +17.2% |
| energydata_complete.csv | 11.4 | +57.1% | +19.8% | +3.0% |
| jwst..miri_f770w.fits | 35.0 | +22.4% | +2.2% | -2.0% |
| synthetic pointcloud.xyz | 3.8 | +73.4% | +38.9% | -0.4% |
| zenodo_ambulacral.stl | 0.7 | +6.8% | +0.0% | -0.5% |

Level 3 is the default, so this is what most callers pay. The weight is in the
inverse transform, not in Zstd decompression (e.g. 52.0 ms of postcondition vs
9.7 ms of Zstd on `energydata_complete.csv`), so verifying the uncompressed
payloads instead would recover only 15-25% and would stop covering the
container framing: deliberately not done. Decompression is unaffected. The
checksum costs 0-6% on decompression in repeated runs.

Partly offsetting it: the raster unfilter loop now runs on Python
bytearrays instead of NumPy scalars, about **3.4x faster** (same output).

Compression ratios: unchanged within 0.1 points on every benchmark row
(4 bytes of checksum per frame).

### Compatibility

- **Reading:** 1.3.1 reads every container written by earlier releases,
  including the old point-cloud, audio and raster sidecars (P6).
- **Writing:** containers written by 1.3.1 in domains 3, 4 and 8 use the new
  sidecars and **must not be read with 1.3.0 or earlier**: those readers do not
  know the markers and can return wrong bytes. Other domains are unaffected,
  and the added Zstd checksums are understood by every Zstd reader.

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

### Added — `--strong-baselines`

`benchmarks/benchmark_extended.py --strong-baselines` re-runs every domain at
Zstd level 19 and adds a Gzip-9 reference. Without the flag behaviour is
unchanged, so previously published figures are unaffected.

The level is applied to **both sides**: KolmoX's internal compressor and its
adaptive fallback run at 19 against a Zstd-19 baseline. Measuring KolmoX at
level 3 against Zstd-19 would only show that level 19 compresses better and
would say nothing about the preconditioning itself.

Result: **the structural advantage holds everywhere. No domain drops to zero or
turns negative**, and the transform is still selected wherever it was at level
3. Three domains improve (CAD mesh +5.09 points, FITS +4.32, video +3.48);
eight shrink. The largest loss is LiDAR, +58.79% → +23.37%, consistent with
that dataset being a deterministic ramp Zstd-19 finds unaided - independent
corroboration of the caveat already attached to that row.

Both the README and the whitepaper now carry the level-19 gain **alongside**
the level-3 column rather than replacing it, since a single column would hide
the three domains that improve.

Two limits are stated explicitly in the notes: the Gzip-9 column conflates the
preconditioning with Zstd-vs-Gzip (the pipeline's backend is not configurable)
and so is a reference rather than a measurement; and level 19 costs about two
orders of magnitude in compression speed, with KolmoX slower than Zstd-19
because the adaptive fallback compresses twice.

The whitepaper PDF generator now derives table column widths from the actual
column count instead of a hardcoded six, which the seventh column would have
broken.

### Added — Evidence Tier 2 is now reproducible

`benchmarks/download_datasets.py` and `benchmarks/benchmark_real.py` make the
real-data claims reproducible by any third party, which until now they were not.
Roughly **52 MB** of download across six datasets from public archives, each
declaring URL, license, expected size and SHA-256. The checksum is verified
after download; a mismatch discards the file and exits non-zero rather than
proceeding. Resume-on-interrupt works only where the server supports HTTP Range
(MAST and GitHub do, Zenodo does not) and the manifest records this per entry;
skip-if-already-valid works everywhere because it operates on the complete file.

Results are published in a **separate** table from the synthetic one, since the
underlying data differs and merging them would obscure both:

| Dataset | Baseline | KolmoX | Gain | Outcome |
| :--- | ---: | ---: | ---: | :--- |
| Astrophysics FITS (JWST SMACS 0723) | 1.76x | 2.07x | +14.83% | transform used |
| Industrial Telemetry (clean CSV) | 6.02x | 8.01x | +24.85% | transform used |
| Industrial Telemetry (semicolon CSV) | 3.04x | 3.44x | +11.51% | transform used |
| CNC G-Code (LinuxCNC) | 4.79x | 4.78x | -0.06% | fallback |
| CAD Mesh (binary STL, WVS) | 1.86x | 1.86x | -0.00% | fallback |
| CAD Mesh (binary STL, Ambulacral) | 2.57x | 2.56x | -0.01% | fallback |

The pattern: where the parser recognises the real data the gain holds (FITS
+14.83% against +16.31% synthetic); where it does not, the gain collapses to
zero and the adaptive fallback correctly stores plain Zstd. Both collapses are
narrow parsing defects, now diagnosed with measured numbers in `TODO.md`:

- **G-Code**: `GCodeEngine` matches lines beginning with `G1 `, but real files
  prefix RS-274/NGC line numbers (`N101 G1 X...`). The transform extracts
  nothing - a 200,509-byte template and 7 bytes of coordinates. The synthetic
  dataset scored +64.10% because its generator emitted no line numbers. This is
  the largest synthetic-to-real gap in the project.
- **CSV**: the columnar demux assumes commas; this file is semicolon-delimited
  with commas as decimal separators. Measured with the correct delimiter the
  same file yields **+26.30%** instead of +11.51%.

Two domains are declared as gaps rather than filled with data of uncertain
provenance: **LiDAR** (no source combining a suitable license with a format that
does not require `laspy`/PDAL) and **Audio** (no direct WAV source at a
proportionate size; the smallest real option costs 157 MB of transfer).

### Changed — the STL/STEP entry in TODO.md was wrong

It read "the router does not handle STL, wire up `MeshCADEngine`". Measurement
contradicts that. Both structural remedies were tested on real binary STL and
both are far worse than doing nothing: transposing at the 50-byte record stride
costs **-32.21%**, float-aware byte-plane slicing costs **-31.60%**. Adjacent
triangles in an STL share vertices, so the raw stream carries local redundancy
that LZ77 exploits and any transposition destroys. On this data the adaptive
fallback is already selecting correctly. The entry now records both failed
attempts with their numbers so nobody repeats them. STEP remains genuinely
unrouted and unmeasured.

### Added — G-code dialects: attached line numbers and modal commands

`GCodeEngine` matched only lines beginning with `G1 ` or `G0 `. Two constructs
that are standard RS-274/NGC, and dominant in the real file benchmarked here,
were invisible to it:

- **Line numbers with no separating space** (`N430X10.5` rather than
  `N430 G1 X10.5`): 4,690 of 4,691 lines in the real file. The line number is
  now extracted into a column of its own, because it changes on every line and
  would otherwise keep the template unique per line and incompressible.
- **Modal commands**, where the G-word is declared once and subsequent lines
  carry only axis words: 4,681 of 4,691 lines.

| | before | after |
| :--- | ---: | ---: |
| G-code, real (LinuxCNC) | -0.06%, transform discarded | **+21.93%**, transform used |
| G-code, synthetic | +64.10% | +64.07% |

The 0.03 regression on the synthetic dataset is the 21-byte header of the new
coordinate format.

**The real-file gain comes from line numbers, not coordinates.** The engine
extracts `X=0, Y=0, Z=0, N=4691` on that file: the coordinates are parametric
expressions (`Y[#<yscale>*53.293]`) and remain untouched by design, since
parsing them would mean modelling one dialect's expression syntax. The figure
should not be read as "G-code preconditioning transfers to real files", and
both the README and the whitepaper say so at the row. Measurable headroom
remains; `TODO.md` records it, along with the fact that the diagnosis published
yesterday for this defect was itself wrong - it had been inferred from the first
few lines of the file rather than from all 4,704.

### Added — CSV field delimiter is detected, not assumed

`ColumnarTextEngine` split on a hardcoded comma. A European-locale CSV uses the
semicolon for fields and the comma for decimals, so the demux was splitting the
decimals apart and producing ragged rows.

| Dataset | before | after |
| :--- | ---: | ---: |
| Real CSV, semicolon-delimited (UCI air quality) | +11.51% | **+26.29%** |
| Real CSV, comma-delimited (UCI appliances) | +24.85% | +24.85% |
| Synthetic CSV | +44.24% | +44.24% |

The 14.78 points recovered are exactly what the diagnosis had predicted.
Nothing else moves: detection selects the comma for the other two datasets, so
their code path is byte-identical to before.

The heuristic picks the candidate producing the **fewest distinct field-count
shapes** across a sample of lines, which is the signal that proved reliable on
real data - the semicolon yields 2 shapes on that file where the comma yields 5.

**One constraint in that heuristic looks arbitrary and is not: the most frequent
field count must be at least 2.** Without it, a delimiter that does not occur in
the file at all produces exactly one shape - the best possible score - and would
therefore win on every input. Tab and pipe would have beaten the correct answer
on every file. Their measured results (-0.03% and -0.01%) were the signature of
"no transformation happened", not of a good delimiter.

Detection operates entirely on bytes and never decodes. The heuristic was
salvaged from `TextColumnarEngine.is_tabular_text`, retired two releases ago,
and only the detection logic was taken: that module decoded with
`errors="replace"`, which destroys non-UTF-8 bytes irreversibly.

**No sub-format version bump was needed.** The delimiter was already stored in
the primary header, at byte 1, and `inverse` reads it back rather than assuming
it. Containers written before this change carry a comma and still decode as a
comma; containers written now carry whatever was detected. Two tests pin that
property, since the fix leans on it.

### Fixed — latent corruption in the G-code coordinate format

Independent of the dialect work above, and **present in released versions**:
the coordinate sidecar separated its sections with a `---` line, which is
ambiguous when a section is empty. Consecutive separators overlap, so

```
b"---\n---\n---\n10".split(b"\n---\n")  ->  2 sections, not 4
```

A G-code file with no X values would therefore have mis-parsed on
decompression under the previous code as well; the defect was not introduced by
this change, only exposed by it. Sections are now length-prefixed behind a
`KMXG2` marker, so empty ones are unambiguous. Sidecars written in the old
format still decode, covered by
`test_legacy_three_section_coords_still_decode`.

### Fixed

- The two long-standing failing tests now pass by opting in explicitly. The
  suite is **117/117 green**: 56 before this release, plus 24 covering nine
  G-code dialects (the N-word column, modal lines, parametric expressions left
  in place, `G10`/`G17` not being mistaken for moves, legacy sidecars) and 37
  covering delimiter detection (each candidate, the European `;`-with-`,`
  case, absent delimiters, non-UTF-8 bytes, CRLF, trailing empty columns,
  ragged rows, and backward compatibility of stored delimiters).
- `generate_whitepaper_pdf.py` gained an eight-column width profile, and the
  new footnote markers use ASCII `(a)`-`(d)` rather than superscript digits:
  U+2075 and up fall outside WinAnsiEncoding and render as black boxes in the
  PDF while looking correct on GitHub. Verified zero unrenderable glyphs.

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
