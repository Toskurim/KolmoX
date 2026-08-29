"""
KolmoX Official Benchmark Suite
"""

import math
import gzip
import time
import zstandard as zstd
from rich.console import Console
from rich.table import Table
from kolmox.core.pipeline import KolmoXPipeline

console = Console()


def evaluate(name: str, raw_data: bytes):
    table = Table(title=f"Benchmark Dataset: {name}")
    table.add_column("Codec", style="cyan", justify="left")
    table.add_column("Original Size", justify="right")
    table.add_column("Compressed Size", justify="right")
    table.add_column("Compression Ratio", justify="right", style="green")
    table.add_column("Decompress Time", justify="right")

    # Gzip Lvl 9
    t0 = time.perf_counter()
    gz_data = gzip.compress(raw_data, compresslevel=9)
    t0 = time.perf_counter()
    gzip.decompress(gz_data)
    t_gz_dec = time.perf_counter() - t0
    table.add_row("Gzip (Lvl 9)", f"{len(raw_data):,}", f"{len(gz_data):,}", f"{len(raw_data)/len(gz_data):.2f}x", f"{t_gz_dec*1000:.2f} ms")

    # Zstandard Lvl 19
    cctx = zstd.ZstdCompressor(level=19)
    dctx = zstd.ZstdDecompressor()
    zstd_data = cctx.compress(raw_data)
    t0 = time.perf_counter()
    dctx.decompress(zstd_data)
    t_zstd_dec = time.perf_counter() - t0
    table.add_row("Zstandard (Lvl 19)", f"{len(raw_data):,}", f"{len(zstd_data):,}", f"{len(raw_data)/len(zstd_data):.2f}x", f"{t_zstd_dec*1000:.2f} ms")

    # KolmoX
    pipeline = KolmoXPipeline(chunk_size=65536)
    kmx_data = pipeline.compress(raw_data)
    t0 = time.perf_counter()
    restored = pipeline.decompress(kmx_data)
    t_kmx_dec = time.perf_counter() - t0

    assert restored == raw_data, "Bit-exact assertion failed!"
    table.add_row("KolmoX", f"{len(raw_data):,}", f"{len(kmx_data):,}", f"{len(raw_data)/len(kmx_data):.2f}x", f"{t_kmx_dec*1000:.2f} ms")

    console.print(table)
    console.print("")


def run_suite():
    # 1. High-rate linear series (1 MB)
    ds1 = bytes([(i * 11 + 7) % 256 for i in range(1_000_000)])
    evaluate("1 MB Industrial Telemetry Progression", ds1)

    # 2. Continuous wave (500 KB)
    ds2_buf = bytearray(500_000)
    for i in range(500_000):
        ds2_buf[i] = max(0, min(255, int(128 + 100 * math.sin(i * 0.1))))
    evaluate("500 KB Sensor Waveform", bytes(ds2_buf))

    # 3. Heterogeneous mixed payload (Modulo + Wave + Constant)
    p1 = bytes([(i * 3) % 256 for i in range(100_000)])
    p2 = bytes(ds2_buf[:100_000])
    p3 = b"KOLMOX_ENTERPRISE_STRUCTURED_STREAM_BLOCK_" * 2500
    evaluate("Mixed Heterogeneous Payload (300 KB)", p1 + p2 + p3)


if __name__ == "__main__":
    run_suite()