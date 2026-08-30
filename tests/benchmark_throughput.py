"""
KolmoX Performance & Throughput Benchmark Suite (v1.1.0)
Measures Compression Ratio, Compression Speed (MB/s), and Decompression Speed (MB/s).
"""

import time
import numpy as np
import zstandard as zstd
from kolmox.core.pipeline import KolmoXPipeline
from kolmox.core.domain_router import DomainType


def benchmark_suite():
    pipeline = KolmoXPipeline(compression_level=3)
    zstd_cctx = zstd.ZstdCompressor(level=3)
    zstd_dctx = zstd.ZstdDecompressor()

    datasets = {}

    # 1. G-Code
    gcode_lines = ["G1 X{:.3f} Y{:.3f} Z0.200 F3000 E{:.3f}\n".format(10.0 + i * 0.05, 20.0 + i * 0.02, i * 0.01) for i in range(30000)]
    datasets["CNC G-Code (.gcode)"] = ("part.gcode", "".join(gcode_lines).encode("utf-8"))

    # 2. Scientific Float32
    floats = np.linspace(-100.0, 100.0, 500000, dtype=np.float32)
    datasets["Scientific Float32 (.npy)"] = ("matrix.npy", floats.tobytes())

    # 3. Audio PCM 16-bit
    t = np.linspace(0, 2.0, int(44100 * 2.0), endpoint=False)
    left = (np.sin(2 * np.pi * 440 * t) * 20000).astype(np.int16)
    right = (np.cos(2 * np.pi * 440 * t) * 20000).astype(np.int16)
    datasets["Audio PCM 16-bit (.wav)"] = ("audio.pcm", np.column_stack([left, right]).tobytes())

    # 4. LiDAR XYZ
    pts = ["{:.6f} {:.6f} {:.6f}\n".format(100.0 + i * 0.01, 200.0 + i * 0.02, 10.0 + (i % 50) * 0.005) for i in range(40000)]
    datasets["LiDAR XYZ Point Cloud"] = ("scan.xyz", "".join(pts).encode("utf-8"))

    print(f"{'Domain':<30} | {'Raw Size':<10} | {'Zstd Base':<10} | {'KolmoX':<10} | {'KMX Ratio':<10} | {'Comp MB/s':<10} | {'Decomp MB/s':<10}")
    print("-" * 105)

    for name, (fname, raw) in datasets.items():
        raw_mb = len(raw) / (1024 * 1024)

        # KolmoX Compression Timing
        t0 = time.perf_counter()
        kmx_comp = pipeline.compress_bytes(raw, filename=fname)
        t_comp = time.perf_counter() - t0
        comp_speed = raw_mb / t_comp if t_comp > 0 else 0.0

        # KolmoX Decompression Timing
        t0 = time.perf_counter()
        restored = pipeline.decompress_bytes(kmx_comp)
        t_decomp = time.perf_counter() - t0
        decomp_speed = raw_mb / t_decomp if t_decomp > 0 else 0.0

        assert restored == raw, f"Bit-exact mismatch on {name}!"

        # Zstd Baseline
        zstd_comp = zstd_cctx.compress(raw)
        kmx_ratio = len(raw) / len(kmx_comp)
        zstd_ratio = len(raw) / len(zstd_comp)

        print(f"{name:<30} | {raw_mb*1024:>7.1f} KB | {zstd_ratio:>8.2f}x | {kmx_ratio:>8.2f}x | {kmx_ratio:>8.2f}x | {comp_speed:>8.1f} MB/s | {decomp_speed:>9.1f} MB/s")


if __name__ == "__main__":
    benchmark_suite()