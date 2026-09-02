"""
KolmoX Extended Domains Benchmark:
Confronto tra Zstd puro (Baseline) e Precondizionamento KolmoX + Zstd.
"""

import struct
import numpy as np
import zstandard as zstd
from rich.console import Console
from rich.table import Table

from kolmox.engines.extended_domains import (
    AudioPCMEngine,
    BinaryBCJEngine,
    GCodeEngine,
    PointCloudEngine,
    ScientificFloatEngine,
)

console = Console()
cctx = zstd.ZstdCompressor(level=3)


def bench_domain(name: str, raw_bytes: bytes, preconditioned_bytes: bytes):
    raw_size = len(raw_bytes)
    zstd_baseline = len(cctx.compress(raw_bytes))
    cand_size = len(cctx.compress(preconditioned_bytes))
    # Adaptive Competitive Fallback: KolmoX non archivia mai payload peggiori del baseline Zstd
    kolmox_size = min(cand_size, zstd_baseline)

    ratio_base = raw_size / zstd_baseline
    ratio_kmx = raw_size / kolmox_size
    gain_vs_zstd = ((zstd_baseline - kolmox_size) / zstd_baseline) * 100

    return {
        "domain": name,
        "raw_kb": raw_size / 1024,
        "zstd_kb": zstd_baseline / 1024,
        "kmx_kb": kolmox_size / 1024,
        "ratio_base": ratio_base,
        "ratio_kmx": ratio_kmx,
        "gain": gain_vs_zstd,
    }


# ==========================================
# GENERAZIONE DATASET SINTETICI REALISTICI
# ==========================================

# 1. G-Code: Percorso utensile CNC di 50.000 righe (Multi-blocco)
lines = ["; CNC Milling Path"]
x, y, z, e = 100.0, 100.0, 0.0, 0.0
for i in range(50000):
    x += np.sin(i * 0.05) * 0.5
    y += np.cos(i * 0.05) * 0.5
    z = (i // 500) * 0.2
    e += 0.05
    lines.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F3000 E{e:.3f}")
raw_gcode = "\n".join(lines).encode("utf-8")
tmpl, coords = GCodeEngine.transform(raw_gcode)

raw_size_gcode = len(raw_gcode)
zstd_base_gcode = len(cctx.compress(raw_gcode))
kmx_size_gcode = len(cctx.compress(tmpl)) + len(cctx.compress(coords))

bench_gcode_res = {
    "domain": "CNC G-Code (.gcode)",
    "raw_kb": raw_size_gcode / 1024,
    "zstd_kb": zstd_base_gcode / 1024,
    "kmx_kb": kmx_size_gcode / 1024,
    "ratio_base": raw_size_gcode / zstd_base_gcode,
    "ratio_kmx": raw_size_gcode / kmx_size_gcode,
    "gain": ((zstd_base_gcode - kmx_size_gcode) / zstd_base_gcode) * 100,
}

# 2. Float32 Scientific: Matrice 2D di simulazione termica (250.000 float)
grid = np.linspace(0, 100, 250000, dtype=np.float32) + np.random.normal(
    0, 0.01, 250000
).astype(np.float32)
raw_f32 = grid.tobytes()
pre_f32 = ScientificFloatEngine.transform_f32_byte_plane(raw_f32)

# 3. Audio PCM16: 5 secondi stereo a 44.1kHz (441.000 campioni)
sr = 44100
t = np.linspace(0, 5, sr * 5, endpoint=False)
ch_l = (
    np.sin(2 * np.pi * 440 * t) * 15000 + np.sin(2 * np.pi * 880 * t) * 5000
).astype(np.int16)
ch_r = (ch_l + np.random.normal(0, 300, len(t)).astype(np.int16)).astype(
    np.int16
)
raw_audio = np.column_stack([ch_l, ch_r]).tobytes()
_, pre_audio = AudioPCMEngine.transform_stereo_pcm16(raw_audio)

# 4. Point Cloud LiDAR (XYZ): 40.000 punti scansionati
pts = [
    f"{10.0 + i*0.01:.6f} {20.0 + (i%100)*0.02:.6f} {1.5 + (i//100)*0.005:.6f}\n"
    for i in range(40000)
]
raw_xyz = "".join(pts).encode("utf-8")
_, pre_xyz = PointCloudEngine.transform_xyz_ascii(raw_xyz)

# 5. Eseguibile x86: Blocco con salti/chiamate relative normalizzate
exe_stream = bytearray(b"\x90\x55\x89\xE5" * 10000)
for i in range(0, len(exe_stream) - 10, 15):
    exe_stream[i] = 0xE8
    exe_stream[i + 1 : i + 5] = struct.pack("<I", 0x00401000 + (i * 4))
raw_bcj = bytes(exe_stream)
pre_bcj = BinaryBCJEngine.transform_x86(raw_bcj)

# ==========================================
# ESECUZIONE E TABELLA RISULTATI
# ==========================================
benchmarks = [
    bench_gcode_res,
    bench_domain("Scientific Float32 (.npy)", raw_f32, pre_f32),
    bench_domain("Audio PCM 16-bit (.wav)", raw_audio, pre_audio),
    bench_domain("LiDAR XYZ Point Cloud", raw_xyz, pre_xyz),
    bench_domain("x86 Binary Executable", raw_bcj, pre_bcj),
]

table = Table(
    title="KolmoX v1.1.0 - Extended Domains Compression Benchmark",
    header_style="bold cyan",
)
table.add_column("Domain", style="bold white", width=26)
table.add_column("Raw Size", justify="right")
table.add_column("Zstd (Baseline)", justify="right")
table.add_column("KolmoX + Zstd", justify="right", style="green")
table.add_column("Base Ratio", justify="right")
table.add_column("KMX Ratio", justify="right", style="bold green")
table.add_column("Extra Gain vs Zstd", justify="right", style="bold yellow")

for b in benchmarks:
    gain_str = (
        f"+{b['gain']:.2f}%" if b["gain"] > 0 else f"{b['gain']:.2f}%"
    )
    table.add_row(
        b["domain"],
        f"{b['raw_kb']:.1f} KB",
        f"{b['zstd_kb']:.1f} KB",
        f"{b['kmx_kb']:.1f} KB",
        f"{b['ratio_base']:.2f}x",
        f"{b['ratio_kmx']:.2f}x",
        gain_str,
    )

console.print("\n")
console.print(table)
console.print("\n")