"""
KolmoX Extended Domains Benchmark.

Misura ogni dominio attraverso l'API pubblica KolmoXPipeline.compress_bytes()
/ decompress_bytes() - lo stesso percorso che ottiene un utente - e verifica il
roundtrip bit-exact su OGNI dominio. Se anche una sola verifica fallisce, lo
script esce con codice 1.

Nota metodologica: non si chiamano gli engine direttamente. Farlo escluderebbe
i 24 byte di header del container KMX2 e scavalcherebbe l'adaptive competitive
fallback, producendo numeri piu' favorevoli di quelli reali. Per lo stesso
motivo il guadagno NON viene calcolato con un min() rispetto al baseline: si
misura cosa la pipeline archivia davvero, e la colonna "Transform" riporta se
la trasformazione ha vinto il confronto o se e' stata scartata.

I dataset sono sintetici e generati con seed fissi, quindi il risultato e'
riproducibile da chiunque senza dipendenze esterne. Il dominio FITS viene
incluso solo se il file di osservazione JWST e' presente in locale.
"""

import math
import os
import struct
import sys
import time

import numpy as np
import zstandard as zstd
from rich.console import Console
from rich.table import Table

from kolmox.core.domain_router import (
    DomainRouter,
    DomainType,
    VIDEO_RAW_SEQUENCE_HEADER_FMT,
    VIDEO_RAW_SEQUENCE_MAGIC,
)
from kolmox.core.pipeline import KolmoXPipeline

console = Console()
cctx = zstd.ZstdCompressor(level=3)

FITS_PATH = "hlsp_jwst-ero_jwst_miri_carina_f770w_v1_i2d.fits"


# ==========================================
# GENERAZIONE DATASET SINTETICI (seed fissi)
# ==========================================

def build_gcode():
    """Percorso utensile CNC di 50.000 righe."""
    lines = ["; CNC Milling Path"]
    x, y, z, e = 100.0, 100.0, 0.0, 0.0
    for i in range(50000):
        x += np.sin(i * 0.05) * 0.5
        y += np.cos(i * 0.05) * 0.5
        z = (i // 500) * 0.2
        e += 0.05
        lines.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F3000 E{e:.3f}")
    return "\n".join(lines).encode("utf-8")


def build_cad_torus(u_steps=180, v_steps=90, R=3.0, r=1.0):
    """Toro tassellato: superficie parametrica liscia, come un export CAD."""
    lines = ["# KolmoX parametric torus", "o Torus"]
    for i in range(u_steps):
        u = 2.0 * math.pi * i / u_steps
        cu, su = math.cos(u), math.sin(u)
        for j in range(v_steps):
            v = 2.0 * math.pi * j / v_steps
            cv, sv = math.cos(v), math.sin(v)
            lines.append(f"v {(R + r*cv)*cu:.6f} {(R + r*cv)*su:.6f} {r*sv:.6f}")
    for i in range(u_steps):
        for j in range(v_steps):
            a = i * v_steps + j + 1
            b = ((i + 1) % u_steps) * v_steps + j + 1
            c = ((i + 1) % u_steps) * v_steps + (j + 1) % v_steps + 1
            d = i * v_steps + (j + 1) % v_steps + 1
            lines.append(f"f {a} {b} {c} {d}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_audio_wav():
    """5 secondi stereo 44.1 kHz, incapsulati in un WAV RIFF valido."""
    np.random.seed(0)
    sr = 44100
    t = np.linspace(0, 5, sr * 5, endpoint=False)
    ch_l = (
        np.sin(2 * np.pi * 440 * t) * 15000 + np.sin(2 * np.pi * 880 * t) * 5000
    ).astype(np.int16)
    ch_r = (ch_l + np.random.normal(0, 300, len(t)).astype(np.int16)).astype(np.int16)
    pcm = np.column_stack([ch_l, ch_r]).tobytes()

    header = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 2, sr, sr * 4, 4, 16)
    header += b"data" + struct.pack("<I", len(pcm))
    return header + pcm


def build_lidar():
    """ATTENZIONE: rampa aritmetica deterministica, non uno scanner reale.
    Serve a verificare il meccanismo, non a stimare le prestazioni sul campo."""
    pts = [
        f"{10.0 + i*0.01:.6f} {20.0 + (i%100)*0.02:.6f} {1.5 + (i//100)*0.005:.6f}\n"
        for i in range(40000)
    ]
    return "".join(pts).encode("utf-8")


def build_binary_packets(num_records=150000, stride=32, seed=7):
    """Frame di telemetria industriale a stride fisso (CAN-bus-like)."""
    rng = np.random.default_rng(seed)
    seq = np.arange(num_records, dtype=np.uint32)
    timestamp = 1_700_000_000 + np.arange(num_records, dtype=np.uint32) * 10
    temp = (22.0 + rng.normal(0, 0.3, num_records)).astype(np.float32)
    pressure = (1013.0 + rng.normal(0, 1.5, num_records)).astype(np.float32)
    vibration = (0.02 + np.abs(rng.normal(0, 0.01, num_records))).astype(np.float32)
    status = np.zeros(num_records, dtype=np.uint32)
    reserved = np.zeros(num_records, dtype=np.uint64)

    records = np.zeros((num_records, stride), dtype=np.uint8)
    records[:, 0:4] = seq.astype("<u4").view(np.uint8).reshape(-1, 4)
    records[:, 4:8] = timestamp.astype("<u4").view(np.uint8).reshape(-1, 4)
    records[:, 8:12] = temp.view(np.uint8).reshape(-1, 4)
    records[:, 12:16] = pressure.view(np.uint8).reshape(-1, 4)
    records[:, 16:20] = vibration.view(np.uint8).reshape(-1, 4)
    records[:, 20:24] = status.astype("<u4").view(np.uint8).reshape(-1, 4)
    records[:, 24:32] = reserved.view(np.uint8).reshape(-1, 8)
    return records.tobytes()


def build_telemetry_csv(num_rows=20000, seed=3):
    """Telemetria industriale a drift lento."""
    rng = np.random.default_rng(seed)
    lines = ["timestamp,sensor_id,temp_c,pressure_kpa,flow_rate,status"]
    temp, press, flow = 21.5, 101.30, 45.0
    for i in range(num_rows):
        temp += rng.normal(0, 0.05)
        press += rng.normal(0, 0.02)
        flow += rng.normal(0, 0.1)
        lines.append(
            f"2026-08-29T{(i//3600)%24:02d}:{(i//60)%60:02d}:{i%60:02d}.000Z,"
            f"{1 + (i % 8)},{temp:.3f},{press:.3f},{flow:.2f},{'OK' if i % 97 else 'WARN'}"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_video_sequence(width=320, height=240, num_frames=60, seed=42):
    """Sequenza RGB con drift temporale lento fra frame consecutivi."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[:height, :width]
    frames = []
    for t in range(num_frames):
        r = ((x * 2) + (y * 3) + (t * 3)) % 256
        g = ((x * 4) - (y * 2) + (t * 2)) % 256
        b = ((x + y + t) * 2) % 256
        frame = np.stack([r, g, b], axis=-1).astype(np.uint8)
        frame = (frame.astype(np.int16) + rng.integers(-2, 2, frame.shape)).clip(0, 255).astype(np.uint8)
        frames.append(frame.tobytes())
    header = struct.pack(
        VIDEO_RAW_SEQUENCE_HEADER_FMT, VIDEO_RAW_SEQUENCE_MAGIC, width, height, 3, num_frames
    )
    return header + b"".join(frames)


def build_raster_bmp(width=256, height=256, channels=3, seed=42):
    """BMP stile foto naturale: gradiente + rumore, con padding di riga reale."""
    rng = np.random.default_rng(seed)
    bpp = channels * 8
    row_size = width * channels
    padded_row_size = (row_size + 3) // 4 * 4
    padding = padded_row_size - row_size

    grad = np.linspace(0, 255, width, dtype=np.uint8)
    img = np.tile(grad, (height, channels, 1)).transpose(0, 2, 1)
    img = (img.astype(np.int16) + rng.integers(-5, 5, img.shape)).clip(0, 255).astype(np.uint8)

    rows = bytearray()
    for y in range(height):
        rows += img[y].tobytes()
        rows += b"\x00" * padding
    pixel_data = bytes(rows)

    info_header_size = 40
    pixel_offset = 14 + info_header_size
    file_header = struct.pack("<2sIHHI", b"BM", pixel_offset + len(pixel_data), 0, 0, pixel_offset)
    info_header = struct.pack(
        "<IiiHHIIiiII",
        info_header_size, width, height, 1, bpp, 0,
        len(pixel_data), 2835, 2835, 0, 0,
    )
    return file_header + info_header + pixel_data


def build_float32():
    """Buffer scientifico denso: 250.000 float32 con rumore gaussiano."""
    np.random.seed(0)
    grid = np.linspace(0, 100, 250000, dtype=np.float32) + np.random.normal(
        0, 0.01, 250000
    ).astype(np.float32)
    return grid.tobytes()


def build_x86():
    """Flusso di istruzioni sintetico con call rel32 (0xE8) normalizzabili."""
    exe_stream = bytearray(b"\x90\x55\x89\xE5" * 10000)
    for i in range(0, len(exe_stream) - 10, 15):
        exe_stream[i] = 0xE8
        exe_stream[i + 1 : i + 5] = struct.pack("<I", 0x00401000 + (i * 4))
    return bytes(exe_stream)


def build_fits():
    with open(FITS_PATH, "rb") as f:
        return f.read()


# ==========================================
# MISURA REALE VIA PIPELINE
# ==========================================

def bench_domain(name: str, raw_bytes: bytes, filename: str, expected_domain: DomainType):
    """Misura end-to-end e verifica il roundtrip bit-exact."""
    detected = DomainRouter.detect_domain(raw_bytes, filename=filename)
    baseline_size = len(cctx.compress(raw_bytes))

    pipeline = KolmoXPipeline()
    t0 = time.perf_counter()
    kmx = pipeline.compress_bytes(raw_bytes, filename=filename)
    t1 = time.perf_counter()
    restored = pipeline.decompress_bytes(kmx)
    t2 = time.perf_counter()

    bit_exact = restored == raw_bytes
    mb = len(raw_bytes) / 1_048_576

    return {
        "domain": name,
        "raw_kb": len(raw_bytes) / 1024,
        "zstd_kb": baseline_size / 1024,
        "kmx_kb": len(kmx) / 1024,
        "ratio_base": len(raw_bytes) / baseline_size,
        "ratio_kmx": len(raw_bytes) / len(kmx),
        "gain": (1 - len(kmx) / baseline_size) * 100,
        "comp_mbps": mb / (t1 - t0),
        "decomp_mbps": mb / (t2 - t1),
        "bit_exact": bit_exact,
        "detected_ok": detected == expected_domain,
        "transform_used": kmx[6] == int(detected),
    }


DATASETS = [
    ("CNC G-Code (.gcode)", build_gcode, "path.gcode", DomainType.GCODE),
    ("Parametric 3D CAD Mesh (.obj)", build_cad_torus, "torus.obj", DomainType.CAD_MESH_OBJ),
    ("Audio PCM 16-bit (.wav)", build_audio_wav, "tone.wav", DomainType.AUDIO_PCM16),
    ("LiDAR XYZ Point Cloud", build_lidar, "scan.xyz", DomainType.POINTCLOUD_XYZ),
    ("Binary Register Packets (.bin)", build_binary_packets, "sensor.bin", DomainType.BINARY_PACKETS),
    ("Industrial Telemetry (.csv)", build_telemetry_csv, "telemetry.csv", DomainType.TELEMETRY_CSV),
    ("Temporal Video Sequence", build_video_sequence, "clip.kmxvraw", DomainType.VIDEO_TEMPORAL),
    ("2D Natural Sensor Raster (.bmp)", build_raster_bmp, "frame.bmp", DomainType.RASTER_2D),
    ("Dense Float32 Buffer (250k)", build_float32, "grid.f32", DomainType.FLOAT32),
    ("x86 Binary Executable (.exe)", build_x86, "prog.exe", DomainType.BINARY_X86),
]


def main():
    results = []
    for name, builder, filename, expected in DATASETS:
        console.print(f"[dim]misurazione: {name}...[/dim]")
        results.append(bench_domain(name, builder(), filename, expected))

    if os.path.exists(FITS_PATH):
        console.print("[dim]misurazione: Astrophysics FITS (JWST, dati reali)...[/dim]")
        results.append(
            bench_domain("Astrophysics FITS (JWST) *", build_fits(), "carina.fits", DomainType.FLOAT32)
        )
    else:
        console.print(
            f"[yellow]FITS saltato: {FITS_PATH} non presente in locale "
            f"(unico dominio su dati di produzione reali).[/yellow]"
        )

    table = Table(
        title="KolmoX - Extended Domains Benchmark (misurato via KolmoXPipeline)",
        header_style="bold cyan",
    )
    table.add_column("Domain", style="bold white", width=30, no_wrap=True)
    table.add_column("Zstd", justify="right", no_wrap=True)
    table.add_column("KolmoX", justify="right", style="bold green", no_wrap=True)
    table.add_column("Gain", justify="right", style="bold yellow", no_wrap=True)
    table.add_column("Comp/Decomp", justify="right", no_wrap=True)
    table.add_column("Transf.", justify="center", no_wrap=True)
    table.add_column("Exact", justify="center", no_wrap=True)

    for b in results:
        table.add_row(
            b["domain"],
            f"{b['ratio_base']:.2f}x",
            f"{b['ratio_kmx']:.2f}x",
            f"{b['gain']:+.2f}%",
            f"~{b['comp_mbps']:.0f}/~{b['decomp_mbps']:.0f} MB/s",
            "[green]used[/green]" if b["transform_used"] else "[yellow]fallb.[/yellow]",
            "[green]PASS[/green]" if b["bit_exact"] else "[bold red]FAIL[/bold red]",
        )

    console.print("\n")
    console.print(table)

    # Riepilogo in righe markdown, incollabile nel README e indipendente
    # dalla larghezza del terminale.
    console.print("\n[bold]Righe pronte per la tabella del README:[/bold]\n")
    for b in results:
        print(
            f"| **{b['domain']}** | {b['ratio_base']:.2f}x | **{b['ratio_kmx']:.2f}x** | "
            f"**{b['gain']:+.2f}%** | ~{b['comp_mbps']:.0f} MB/s / ~{b['decomp_mbps']:.0f} MB/s |"
        )
    console.print(
        "\n[dim]* unico dominio su dati di produzione reali; tutti gli altri sono "
        "dataset sintetici generati con seed fissi.[/dim]"
    )
    console.print(
        "[dim]'fallback' significa che la trasformazione non ha battuto il baseline Zstd "
        "e la pipeline ha archiviato il baseline: il costo residuo e' l'header KMX2 da 24 byte.[/dim]"
    )

    failures = [b for b in results if not b["bit_exact"]]
    misrouted = [b for b in results if not b["detected_ok"]]
    if misrouted:
        console.print(
            f"\n[yellow]Attenzione: dominio inatteso per: "
            f"{', '.join(b['domain'] for b in misrouted)}[/yellow]"
        )
    if failures:
        console.print(
            f"\n[bold red]ROUNDTRIP NON BIT-EXACT: "
            f"{', '.join(b['domain'] for b in failures)}[/bold red]"
        )
        return 1

    console.print("\n[bold green]Tutti i domini: roundtrip bit-exact verificato.[/bold green]\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
