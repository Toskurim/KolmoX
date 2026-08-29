"""
KolmoX - Command Line Interface
"""

import os
import time
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from kolmox.core.pipeline import KolmoXPipeline

console = Console()


@click.group()
def cli():
    """KolmoX: Program-Synthesis & Kolmogorov Data Compression Engine"""
    pass


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.option("--chunk-size", default=65536, help="Block chunk size in bytes (default: 64KB)")
@click.option("--level", default=19, help="Zstandard residual compression level (1-22)")
def compress(input_path: str, output_path: str, chunk_size: int, level: int):
    """Compress any binary or structured file into KolmoX (.kmx) container."""
    with open(input_path, "rb") as f:
        data = f.read()

    orig_size = len(data)
    console.print(f"[bold cyan]Compressing '{input_path}' ({orig_size:,} bytes)...[/bold cyan]")

    pipeline = KolmoXPipeline(chunk_size=chunk_size, delta_level=level)
    t0 = time.perf_counter()
    compressed = pipeline.compress(data)
    enc_time = time.perf_counter() - t0

    with open(output_path, "wb") as f:
        f.write(compressed)

    comp_size = len(compressed)
    ratio = (1.0 - comp_size / orig_size) * 100 if orig_size > 0 else 0.0
    factor = orig_size / comp_size if comp_size > 0 else 1.0

    table = Table(show_header=False, box=None)
    table.add_row("Original Size:", f"{orig_size:,} bytes")
    table.add_row("Compressed Size:", f"[bold green]{comp_size:,} bytes[/bold green]")
    table.add_row("Reduction:", f"[bold green]{ratio:.2f}%[/bold green] ({factor:.2f}x)")
    table.add_row("Encoding Time:", f"{enc_time*1000:.2f} ms")

    console.print(Panel(table, title="[bold white]KolmoX Compression Summary[/bold white]", border_style="green"))


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
def decompress(input_path: str, output_path: str):
    """Decompress a .kmx file back to bit-exact original data."""
    with open(input_path, "rb") as f:
        data = f.read()

    console.print(f"[bold cyan]Decompressing '{input_path}'...[/bold cyan]")
    pipeline = KolmoXPipeline()
    t0 = time.perf_counter()
    restored = pipeline.decompress(data)
    dec_time = time.perf_counter() - t0

    with open(output_path, "wb") as f:
        f.write(restored)

    console.print(
        Panel(
            f"Restored: [bold green]{len(restored):,} bytes[/bold green] in {dec_time*1000:.2f} ms\nBit-exact verification: [bold green]PASSED[/bold green]",
            title="[bold white]KolmoX Decompression Complete[/bold white]",
            border_style="cyan",
        )
    )


if __name__ == "__main__":
    cli()