import os
import math
import time
import gzip
import zstandard as zstd
from rich.console import Console
from rich.table import Table
from kolmox.core.pipeline import KolmoXPipeline

console = Console()


def create_realistic_cad_mesh(num_vertices=25000) -> bytes:
    lines = ["# KolmoX Industrial CAD Surface Export\n"]
    for i in range(num_vertices):
        u = (i % 500) * 0.02
        v = (i // 500) * 0.02
        x = u * 10.0
        y = v * 10.0
        z = math.sin(u) * math.cos(v) * 2.5
        lines.append(f"v {x:.4f} {y:.4f} {z:.4f}\n")
    return "".join(lines).encode("utf-8")


def create_industrial_telemetry_csv(num_rows=20000) -> bytes:
    lines = ["timestamp_ms,spindle_rpm,feed_rate,torque_nm,vibration_hz\n"]
    base_ts = 1772300000000
    for i in range(num_rows):
        ts = base_ts + i * 10
        rpm = 12000 + int(500 * math.sin(i * 0.05))
        feed = 1500.0 + (i % 100) * 2.0
        torque = 35.2 + math.cos(i * 0.1) * 3.1
        vib = 0.02 + ((i * 7) % 50) * 0.001
        lines.append(f"{ts},{rpm},{feed:.1f},{torque:.2f},{vib:.3f}\n")
    return "".join(lines).encode("utf-8")


def create_binary_sensor_registers(num_packets=10000) -> bytes:
    buf = bytearray()
    for i in range(num_packets):
        seq = i & 0xFFFF
        temp = int(2500 + 300 * math.sin(i * 0.02))
        pressure = 101325 + (i % 256)
        status_flags = 0x01 if (i % 50 == 0) else 0x00
        buf.extend(seq.to_bytes(2, "big"))
        buf.extend(temp.to_bytes(2, "big"))
        buf.extend(pressure.to_bytes(4, "big"))
        buf.append(status_flags)
        buf.extend(bytes([(i + j) % 256 for j in range(7)]))
    return bytes(buf)


def benchmark_payload(title: str, raw_data: bytes):
    table = Table(title=f"Real-World Benchmark: {title}")
    table.add_column("Codec", style="cyan", justify="left")
    table.add_column("Original Size", justify="right")
    table.add_column("Compressed Size", justify="right")
    table.add_column("Compression Ratio", justify="right", style="green")
    table.add_column("Decompress Time", justify="right")

    # 1. Gzip Level 9
    t0 = time.perf_counter()
    gz_data = gzip.compress(raw_data, compresslevel=9)
    t0 = time.perf_counter()
    gzip.decompress(gz_data)
    t_gz_dec = time.perf_counter() - t0
    table.add_row("Gzip (Lvl 9)", f"{len(raw_data):,}", f"{len(gz_data):,}", f"{len(raw_data)/len(gz_data):.2f}x", f"{t_gz_dec*1000:.2f} ms")

    # 2. Zstandard Level 19
    cctx = zstd.ZstdCompressor(level=19)
    dctx = zstd.ZstdDecompressor()
    zstd_data = cctx.compress(raw_data)
    t0 = time.perf_counter()
    dctx.decompress(zstd_data)
    t_zstd_dec = time.perf_counter() - t0
    table.add_row("Zstandard (Lvl 19)", f"{len(raw_data):,}", f"{len(zstd_data):,}", f"{len(raw_data)/len(zstd_data):.2f}x", f"{t_zstd_dec*1000:.2f} ms")

    # 3. KolmoX
    pipeline = KolmoXPipeline(chunk_size=65536)
    kmx_data = pipeline.compress(raw_data)
    t0 = time.perf_counter()
    restored = pipeline.decompress(kmx_data)
    t_kmx_dec = time.perf_counter() - t0

    assert restored == raw_data, "Bit-exact integrity check failed!"
    table.add_row("KolmoX", f"{len(raw_data):,}", f"{len(kmx_data):,}", f"{len(raw_data)/len(kmx_data):.2f}x", f"{t_kmx_dec*1000:.2f} ms")

    console.print(table)
    console.print("")


def run_all():
    cad_data = create_realistic_cad_mesh(30000)
    benchmark_payload("Parametric 3D CAD Mesh (.obj)", cad_data)

    csv_data = create_industrial_telemetry_csv(25000)
    benchmark_payload("Industrial Machine Telemetry Log (.csv)", csv_data)

    bin_data = create_binary_sensor_registers(15000)
    benchmark_payload("Structured Binary Register Packets (.bin)", bin_data)


if __name__ == "__main__":
    run_all()
