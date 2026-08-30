"""
KolmoX - Command Line Interface
"""
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

from kolmox.core.hardware import HardwareProfile
from kolmox.engines.video_stream import VideoStreamEngine
from kolmox.core.pipeline import KolmoXPipeline

console = Console()


@click.group()
def cli():
    """KolmoX - High-Performance Compression Toolkit"""
    pass


@cli.command("profile")
def profile_cmd():
    """Show hardware profile and acceleration capabilities."""
    hw = HardwareProfile.detect()
    table = Table(title="KolmoX Hardware Topology & Execution Profile")
    table.add_column("Parametro", style="cyan")
    table.add_column("Rilevamento", style="bold green")

    table.add_row("Piattaforma OS", f"{hw.platform_name.upper()} ({hw.machine_arch})")
    table.add_row("Architettura Apple Silicon", "SI" if hw.is_apple_silicon else "NO (x86/Standard)")
    table.add_row("Accelerazione Decoder GPU", hw.hwaccel_backend.upper() if hw.hwaccel_backend else "Non rilevato (CPU Fallback)")
    table.add_row("Thread Logici CPU", f"{hw.logical_cores} Threads")
    table.add_row("RAM Totale / Disponibile", f"{hw.total_ram_gb} GB / {hw.available_ram_gb} GB")
    table.add_row("Thread Worker Consigliati", f"{hw.recommended_workers} Threads")
    table.add_row("Dimensione Chunk Auto-Tuned", f"{hw.recommended_chunk_frames} frame/chunk")

    console.print(table)


@cli.command("compress-video")
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.option("--chunk-frames", default=120, help="Frames per delta-chunk")
@click.option("--level", default=7, help="Zstandard compression level (1-22)")
@click.option("--threads", default=-1, help="Number of worker threads (-1 for auto)")
@click.option("--max-frames", default=0, help="Max frames to process (0 for all)")
def compress_video(input_path, output_path, chunk_frames, level, threads, max_frames):
    """Compress a video file stream into bit-exact lossless KolmoX Stream format."""
    with Progress(
        TextColumn("[bold green]Compressing Video Stream..."),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("• {task.completed}/{task.total} frame"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = None

        def on_progress(done, total):
            nonlocal task
            if task is None:
                task = progress.add_task("compress", total=total)
            progress.update(task, advance=done)

        res = VideoStreamEngine.compress_file_stream(
            input_video_path=input_path,
            output_kmxv_path=output_path,
            chunk_frames=chunk_frames,
            compression_level=level,
            threads=threads,
            max_frames=max_frames,
            progress_cb=on_progress
        )

    table = Table(title="KolmoX Video Stream Compression Summary")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="bold yellow")

    table.add_row("Resolution", f"{res['width']}x{res['height']} @ {res['fps']} FPS")
    table.add_row("Total Frames", f"{res['total_frames']:,}")
    table.add_row("Decoder Backend", res['hwaccel'])
    table.add_row("RAW Data Equivalent", f"{res['raw_bytes'] / (1024**3):.2f} GB")
    table.add_row("Compressed Payload", f"{res['compressed_bytes'] / (1024**3):.2f} GB")
    table.add_row("Lossless Compression Ratio", f"{res['ratio']:.2f}x")

    console.print(table)


@cli.command("decompress-video")
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
def decompress_video(input_path, output_path):
    """Decompress a KolmoX Video Stream back to raw RGB24 frame stream."""
    with Progress(
        TextColumn("[bold cyan]Decompressing Video Stream..."),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("• {task.completed}/{task.total} frame"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = None

        def on_progress(done, total):
            nonlocal task
            if task is None:
                task = progress.add_task("decompress", total=total)
            progress.update(task, advance=done)

        res = VideoStreamEngine.decompress_to_raw_stream(
            input_kmxv_path=input_path,
            output_raw_path=output_path,
            progress_cb=on_progress
        )

    table = Table(title="KolmoX Video Stream Decompression Summary")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="bold green")

    table.add_row("Resolution", f"{res['width']}x{res['height']} @ {res['fps']} FPS")
    table.add_row("Restored Frames", f"{res['total_frames']:,}")
    table.add_row("Output Path", output_path)

    console.print(table)


@cli.command("compress")
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.option("--level", default=7, help="Zstd compression level")
def compress_file(input_path, output_path, level):
    """Compress a standard binary file using the KolmoX pipeline."""
    pipeline = KolmoXPipeline(compression_level=level)
    with open(input_path, "rb") as f:
        data = f.read()
    compressed = pipeline.compress_bytes(data)
    with open(output_path, "wb") as f:
        f.write(compressed)
    console.print(f"[bold green]Compressed {len(data)} -> {len(compressed)} bytes ({len(data)/len(compressed):.2f}x)[/]")


@cli.command("decompress")
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
def decompress_file(input_path, output_path):
    """Decompress a standard KolmoX binary file."""
    pipeline = KolmoXPipeline()
    with open(input_path, "rb") as f:
        data = f.read()
    decompressed = pipeline.decompress_bytes(data)
    with open(output_path, "wb") as f:
        f.write(decompressed)
    console.print(f"[bold green]Decompressed {len(data)} -> {len(decompressed)} bytes[/]")


if __name__ == "__main__":
    cli()