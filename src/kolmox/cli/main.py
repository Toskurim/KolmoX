"""
KolmoX - Command Line Interface with LLM Bridge support
"""
import os
import time
import click
from rich.console import Console
from kolmox.core.pipeline import KolmoXPipeline

console = Console()


@click.group()
def cli():
    """KolmoX: Next-Generation Program-Synthesis Lossless Compressor"""
    pass


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
@click.option("--chunk-size", default=131072, help="Block chunk size in bytes (default: 128KB)")
@click.option("--endpoint", default=None, help="Inference API URL (e.g., http://localhost:1234/v1)")
@click.option("--model", default="local-model", help="Model name on the local server")
def compress(input_path: str, output_path: str, chunk_size: int, endpoint: str, model: str):
    """Compress a file using KolmoX program synthesis."""
    with open(input_path, "rb") as f:
        data = f.read()

    orig_size = len(data)
    console.print(f"[cyan]Compressing {input_path} ({orig_size:,} bytes)...[/cyan]")
    if endpoint:
        console.print(f"[yellow]LLM Synthesis active via endpoint: {endpoint}[/yellow]")

    pipeline = KolmoXPipeline(chunk_size=chunk_size, api_base_url=endpoint)
    if endpoint:
        pipeline.block_comp.synth_engine.model = model

    t0 = time.perf_counter()
    compressed = pipeline.compress(data)
    elapsed = time.perf_counter() - t0

    with open(output_path, "wb") as f:
        f.write(compressed)

    comp_size = len(compressed)
    ratio = orig_size / comp_size if comp_size > 0 else 1.0
    speed_mb = (orig_size / (1024 * 1024)) / elapsed if elapsed > 0 else 0

    console.print(f"[green]Done in {elapsed:.3f}s ({speed_mb:.2f} MB/s) | Size: {comp_size:,} bytes | Ratio: {ratio:.2f}x[/green]")


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path())
def decompress(input_path: str, output_path: str):
    """Decompress a .kmx file back to original data."""
    with open(input_path, "rb") as f:
        kmx_data = f.read()

    console.print(f"[cyan]Decompressing {input_path} ({len(kmx_data):,} bytes)...[/cyan]")

    pipeline = KolmoXPipeline()
    t0 = time.perf_counter()
    restored = pipeline.decompress(kmx_data)
    elapsed = time.perf_counter() - t0

    with open(output_path, "wb") as f:
        f.write(restored)

    speed_mb = (len(restored) / (1024 * 1024)) / elapsed if elapsed > 0 else 0
    console.print(f"[green]Restored {len(restored):,} bytes in {elapsed*1000:.2f} ms ({speed_mb:.2f} MB/s)[/green]")


if __name__ == "__main__":
    cli()