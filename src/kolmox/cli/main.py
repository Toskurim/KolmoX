"""
KolmoX CLI - High-Performance Compression Toolkit
"""
import sys
import os
import time
import click
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table

from kolmox.core.pipeline import KolmoXPipeline
from kolmox.core.hardware import HardwareProfile
from kolmox.engines.video_stream import VideoStreamEngine

console = Console()


@click.group()
def cli():
    """KolmoX: Deterministic Multi-Modal Lossless Compression Engine."""
    pass


@cli.command()
def profile():
    """Display host machine hardware topology and detected acceleration capabilities."""
    hw = HardwareProfile.detect()

    table = Table(title="KolmoX Hardware Topology & Execution Profile")
    table.add_column("Parametro", style="cyan")
    table.add_column("Rilevamento", justify="right")

    table.add_row("Piattaforma OS", f"{hw.platform_name.upper()} ({hw.machine_arch})")
    table.add_row("Architettura Apple Silicon", "SI (Unified Memory)" if hw.is_apple_silicon else "NO (x86/Standard)")
    table.add_row("Thread Logici CPU", f"{hw.logical_cores} Threads")
    table.add_row("RAM Totale / Disponibile", f"{hw.total_ram_gb:.1f} GB / {hw.available_ram_gb:.1f} GB")
    table.add_row("Thread Worker Consigliati", f"{hw.recommended_workers} Threads")
    table.add_row("Dimensione Chunk Auto-Tuned", f"{hw.recommended_chunk_frames} frame/chunk")

    console.print("\n")
    console.print(table)


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.option("--level", "-l", default=7, help="Compression level (1-19). Default 7.")
@click.option("--threads", "-t", default=-1, help="Threads for parallel execution (-1 for all).")
def compress(input_path: str, output_path: str, level: int, threads: int):
    """Compress a generic heterogeneous file into a KolmoX container."""
    with open(input_path, "rb") as f:
        data = f.read()

    pipeline = KolmoXPipeline(compression_level=level, threads=threads)
    t0 = time.perf_counter()
    compressed = pipeline.compress(data)
    elapsed = time.perf_counter() - t0

    with open(output_path, "wb") as f:
        f.write(compressed)

    ratio = len(data) / len(compressed) if compressed else 1.0
    console.print(f"[bold green]Compression completed in {elapsed:.3f}s[/bold green]")
    console.print(f"Original: {len(data):,} B | Compressed: {len(compressed):,} B | Ratio: [bold cyan]{ratio:.2f}x[/bold cyan]")


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
def decompress(input_path: str, output_path: str):
    """Decompress a KolmoX container back to original bit-exact payload."""
    with open(input_path, "rb") as f:
        compressed = f.read()

    pipeline = KolmoXPipeline()
    t0 = time.perf_counter()
    decompressed = pipeline.decompress(compressed)
    elapsed = time.perf_counter() - t0

    with open(output_path, "wb") as f:
        f.write(decompressed)

    console.print(f"[bold green]Decompression completed in {elapsed:.3f}s[/bold green]")
    console.print(f"Restored: {len(decompressed):,} B")


@cli.command()
@click.argument("input_video", type=click.Path(exists=True))
@click.argument("output_kmxv", type=click.Path())
@click.option("--chunk-frames", "-c", default=0, help="Frames per chunk (0 for hardware auto-tune).")
@click.option("--level", "-l", default=7, help="Zstd compression level.")
@click.option("--max-frames", "-m", default=0, help="Limit frames to process (0 for full stream).")
def compress_video(input_video: str, output_kmxv: str, chunk_frames: int, level: int, max_frames: int):
    """Hardware-tuned lossless streaming compression for video."""
    hw = HardwareProfile.detect()
    effective_chunk = chunk_frames if chunk_frames > 0 else hw.recommended_chunk_frames

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("• {task.completed}/{task.total} frame"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[green]Compressing Video Stream...", total=100)

        def update_progress(advance_frames, total_frames):
            progress.update(task, total=total_frames, advance=advance_frames)

        res = VideoStreamEngine.compress_file_stream(
            input_video,
            output_kmxv,
            chunk_frames=effective_chunk,
            compression_level=level,
            threads=hw.recommended_workers,
            max_frames=max_frames,
            progress_cb=update_progress
        )

    table = Table(title="KolmoX Video Stream Compression Summary")
    table.add_column("Property", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Resolution", f"{res['width']}x{res['height']} @ {res['fps']} FPS")
    table.add_row("Total Frames", f"{res['total_frames']:,}")
    table.add_row("RAW Data Equivalent", f"{res['raw_bytes'] / (1024**3):.2f} GB")
    table.add_row("Compressed Payload", f"{res['compressed_bytes'] / (1024**3):.2f} GB")
    table.add_row("Lossless Compression Ratio", f"[bold green]{res['ratio']:.2f}x[/bold green]")
    console.print(table)


if __name__ == "__main__":
    cli()