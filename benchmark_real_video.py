"""
KolmoX - Real World Video Benchmark Tool
Extracts uncompressed RAW RGB frames from an input video, compresses with KolmoX,
and validates 100% bit-exact reconstruction and real-world compression ratios.
"""
import sys
import os
import time
import cv2
from rich.console import Console
from rich.table import Table

from kolmox.core.pipeline import KolmoXPipeline

console = Console()


def benchmark_video(video_path: str, max_frames: int = 60):
    if not os.path.exists(video_path):
        console.print(f"[bold red]Errore: File non trovato: {video_path}[/bold red]")
        return

    console.print(f"[cyan]Apertura video:[/] {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        console.print("[bold red]Impossibile aprire il video con OpenCV.[/bold red]")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    console.print(f"[dim]Risoluzione: {width}x{height} | FPS: {fps:.2f} | Frame totali: {total_frames}[/dim]")
    console.print(f"[yellow]Estrazione di {max_frames} frame RAW RGB...[/yellow]")

    frames = []
    for _ in range(max_frames):
        ret, bgr_frame = cap.read()
        if not ret:
            break
        # OpenCV usa BGR, convertiamo in standard RGB
        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        frames.append(rgb_frame.tobytes())

    cap.release()

    n_extracted = len(frames)
    if n_extracted == 0:
        console.print("[bold red]Nessun frame estratto.[/bold red]")
        return

    raw_total_bytes = sum(len(f) for f in frames)
    console.print(f"[dim]Frame estratti: {n_extracted} | Dimensione RAW totale: {raw_total_bytes / (1024*1024):.2f} MB[/dim]\n")

    # Inizializza pipeline
    pipeline = KolmoXPipeline(compression_level=7, threads=-1)
    # 1. Compressione
    console.print("[bold cyan]Compressione con KolmoX VideoEngine in corso...[/bold cyan]")
    t0 = time.perf_counter()
    compressed_payload = pipeline.compress_video_frames(frames, width=width, height=height, channels=3)
    t_comp = time.perf_counter() - t0

    comp_bytes = len(compressed_payload)
    ratio = raw_total_bytes / comp_bytes if comp_bytes > 0 else 1.0
    comp_speed_mb = (raw_total_bytes / (1024 * 1024)) / t_comp

    # 2. Decompressione
    console.print("[bold cyan]Decompressione e verifica bit-exact in corso...[/bold cyan]")
    t1 = time.perf_counter()
    restored_frames = pipeline.decompress_video_frames(compressed_payload)
    t_decomp = time.perf_counter() - t1

    decomp_speed_mb = (raw_total_bytes / (1024 * 1024)) / t_decomp

    # 3. Verifica Bit-Exact
    bit_exact = (len(restored_frames) == n_extracted) and all(
        orig == rest for orig, rest in zip(frames, restored_frames)
    )

    # Tabella Risultati
    table = Table(title=f"Benchmark Risultati Reali KolmoX: {os.path.basename(video_path)}")
    table.add_column("Metrica", style="cyan")
    table.add_column("Valore", justify="right")

    table.add_row("Frame Elaborati", f"{n_extracted} frame ({width}x{height})")
    table.add_row("Dimensione RAW (RGB)", f"{raw_total_bytes / (1024*1024):.2f} MB ({raw_total_bytes:,} B)")
    table.add_row("Dimensione Compressa", f"{comp_bytes / (1024*1024):.2f} MB ({comp_bytes:,} B)")
    table.add_row("Compression Ratio (vs RAW)", f"[bold green]{ratio:.2f}x[/bold green]")
    table.add_row("Tempo Compressione", f"{t_comp:.2f} s ({comp_speed_mb:.2f} MB/s)")
    table.add_row("Tempo Decompressione", f"{t_decomp:.2f} s ({decomp_speed_mb:.2f} MB/s)")
    table.add_row(
        "Integrità Bit-Exact (100%)",
        "[bold green]PASS (100% Perfetto)[/bold green]" if bit_exact else "[bold red]FAIL[/bold red]"
    )

    console.print(table)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python benchmark_real_video.py <percorso_video.mp4> [numero_frame_opzionale]")
    else:
        num_f = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        benchmark_video(sys.argv[1], max_frames=num_f)