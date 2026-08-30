"""
KolmoX - Unified CLI Auto-Dispatcher with Rich Telemetry
"""

import argparse
import os
import sys
import time
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TransferSpeedColumn
from rich.panel import Panel

from kolmox.core.pipeline import KolmoXPipeline
from kolmox.core.mesh_cad import MeshCADEngine
from kolmox.engines.video_stream import VideoStreamEngine

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
console = Console()


def render_summary_table(action: str, in_path: str, out_path: str, orig_size: int, final_size: int, elapsed: float):
    ratio = orig_size / max(1, final_size)
    space_saved = ((orig_size - final_size) / max(1, orig_size)) * 100
    speed_mb = (orig_size / (1024 * 1024)) / max(0.001, elapsed)

    table = Table(title=f"KolmoX Execution Summary ({action})", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim", width=24)
    table.add_column("Value", style="bold green")

    table.add_row("Input File", os.path.basename(in_path))
    table.add_row("Output File", os.path.basename(out_path))
    table.add_row("Original Size", f"{orig_size:,} bytes ({orig_size / (1024*1024):.2f} MB)")
    table.add_row("Processed Size", f"{final_size:,} bytes ({final_size / (1024*1024):.2f} MB)")
    table.add_row("Compression Ratio", f"{ratio:.2f}x")
    table.add_row("Space Saved", f"{space_saved:.2f}%" if space_saved >= 0 else f"{space_saved:.2f}% (overhead)")
    table.add_row("Elapsed Time", f"{elapsed:.3f} s")
    table.add_row("Throughput", f"{speed_mb:.2f} MB/s")

    console.print(table)


def auto_compress(input_path: str, output_path: str, level: int, quiet: bool = False):
    start_time = time.perf_counter()
    _, ext = os.path.splitext(input_path.lower())

    if ext in VIDEO_EXTS:
        if not quiet:
            console.print(f"[bold yellow][Auto-Dispatch][/bold yellow] Detected video format ([cyan]{ext}[/cyan]). Routing to Hardware Video Stream Engine...")
        VideoStreamEngine.compress_video_stream(input_path, output_path)
        return

    with open(input_path, "rb") as f:
        raw_data = f.read()
    orig_len = len(raw_data)

    if ext == ".obj" or MeshCADEngine.is_obj_mesh(raw_data):
        if not quiet:
            console.print("[bold yellow][Auto-Dispatch][/bold yellow] Detected 3D Mesh / CAD geometry. Routing to MeshCAD Engine...")
        template, geom = MeshCADEngine.transpose_mesh(raw_data)
        intermediate = b"KCAD" + len(template).to_bytes(4, "big") + template + geom
        pipeline = KolmoXPipeline(compression_level=level)
        compressed = pipeline.compress_bytes(intermediate)
        with open(output_path, "wb") as out:
            out.write(compressed)
        elapsed = time.perf_counter() - start_time
        if not quiet:
            render_summary_table("3D Mesh CAD", input_path, output_path, orig_len, len(compressed), elapsed)
        return

    if not quiet:
        console.print("[bold yellow][Auto-Dispatch][/bold yellow] Routing to Multi-Domain Structural Pipeline...")
    pipeline = KolmoXPipeline(compression_level=level)
    compressed = pipeline.compress_bytes(raw_data)
    with open(output_path, "wb") as out:
        out.write(compressed)
    elapsed = time.perf_counter() - start_time
    if not quiet:
        render_summary_table("Generic/Tabular", input_path, output_path, orig_len, len(compressed), elapsed)


def auto_decompress(input_path: str, output_path: str, quiet: bool = False):
    start_time = time.perf_counter()
    _, ext = os.path.splitext(input_path.lower())

    if ext == ".kmxv":
        if not quiet:
            console.print("[bold yellow][Auto-Dispatch][/bold yellow] Detected KolmoX Video Container. Routing to Video Decoder...")
        VideoStreamEngine.decompress_video_stream(input_path, output_path)
        return

    with open(input_path, "rb") as f:
        compressed = f.read()

    pipeline = KolmoXPipeline()
    decompressed = pipeline.decompress_bytes(compressed)

    if decompressed.startswith(b"KCAD"):
        if not quiet:
            console.print("[bold yellow][Auto-Dispatch][/bold yellow] Detected KCAD payload. Reconstructing 3D Mesh...")
        template_len = int.from_bytes(decompressed[4:8], "big")
        template = decompressed[8:8 + template_len]
        geom = decompressed[8 + template_len:]
        restored = MeshCADEngine.untranspose_mesh(template, geom)
        with open(output_path, "wb") as out:
            out.write(restored)
        elapsed = time.perf_counter() - start_time
        if not quiet:
            render_summary_table("CAD Decompress", input_path, output_path, len(compressed), len(restored), elapsed)
        return

    with open(output_path, "wb") as out:
        out.write(decompressed)
    elapsed = time.perf_counter() - start_time
    if not quiet:
        render_summary_table("Generic Decompress", input_path, output_path, len(compressed), len(decompressed), elapsed)


def main():
    parser = argparse.ArgumentParser(
        prog="kolmox",
        description="KolmoX - High-Performance Bit-Exact Compression Framework"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Unified Compress
    c_parser = subparsers.add_parser("compress", help="Auto-detect and compress any file or video")
    c_parser.add_argument("input", help="Input file path")
    c_parser.add_argument("output", help="Output file path")
    c_parser.add_argument("-l", "--level", type=int, default=19, help="Compression level (1-22)")
    c_parser.add_argument("-q", "--quiet", action="store_true", help="Suppress telemetry output")

    # Unified Decompress
    d_parser = subparsers.add_parser("decompress", help="Auto-detect and decompress any KolmoX container")
    d_parser.add_argument("input", help="Input KolmoX file path")
    d_parser.add_argument("output", help="Output restored file path")
    d_parser.add_argument("-q", "--quiet", action="store_true", help="Suppress telemetry output")

    # Explicit Video Commands
    vc_parser = subparsers.add_parser("compress-video", help="Compress video stream with NVDEC/CUDA")
    vc_parser.add_argument("input", help="Input video path")
    vc_parser.add_argument("output", help="Output .kmxv container path")
    vc_parser.add_argument("--max-frames", type=int, default=None, help="Limit number of frames")

    vd_parser = subparsers.add_parser("decompress-video", help="Decompress .kmxv container")
    vd_parser.add_argument("input", help="Input .kmxv path")
    vd_parser.add_argument("output", help="Output raw video path")

    args = parser.parse_args()

    if args.command == "compress":
        auto_compress(args.input, args.output, args.level, quiet=args.quiet)
    elif args.command == "decompress":
        auto_decompress(args.input, args.output, quiet=args.quiet)
    elif args.command == "compress-video":
        VideoStreamEngine.compress_video_stream(args.input, args.output, max_frames=args.max_frames)
    elif args.command == "decompress-video":
        VideoStreamEngine.decompress_video_stream(args.input, args.output)


if __name__ == "__main__":
    main()
