"""
KolmoX CLI (v1.1.0)
Command-line interface for compression, decompression, and domain dispatch.
"""

import argparse
import sys
from pathlib import Path

from kolmox.core.chunked import ChunkedPipelineEngine
from kolmox.core.pipeline import KMX2_MAGIC, KolmoXPipeline


def auto_compress(
    input_path: str,
    output_path: str,
    chunked: bool = False,
    workers: int = 4,
    quiet: bool = False,
):
    in_p = Path(input_path)
    out_p = Path(output_path)

    raw_data = in_p.read_bytes()

    if chunked or len(raw_data) > 32 * 1024 * 1024:
        ChunkedPipelineEngine.compress_large_file(
            input_path, output_path, max_workers=workers
        )
    else:
        pipeline = KolmoXPipeline()
        compressed = pipeline.compress_bytes(raw_data, filename=in_p.name)
        out_p.write_bytes(compressed)

    if not quiet:
        print(f"Compressed {input_path} -> {output_path}")


def auto_decompress(
    input_path: str, output_path: str, workers: int = 4, quiet: bool = False
):
    in_p = Path(input_path)
    out_p = Path(output_path)

    data = in_p.read_bytes()

    # Riconoscimento formato KMX2 / KolmoXPipeline standard
    if data.startswith(KMX2_MAGIC) or data.startswith(b"KMX1"):
        pipeline = KolmoXPipeline()
        restored = pipeline.decompress_bytes(data)
        out_p.write_bytes(restored)
    else:
        # Fallback su chunked container multi-thread
        ChunkedPipelineEngine.decompress_large_file(
            input_path, output_path, max_workers=workers
        )

    if not quiet:
        print(f"Decompressed {input_path} -> {output_path}")


def main():
    parser = argparse.ArgumentParser(
        prog="kolmox", description="KolmoX Advanced Compression CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Compress
    p_comp = subparsers.add_parser("compress", help="Compress a file")
    p_comp.add_argument("input", type=str, help="Input file path")
    p_comp.add_argument("output", type=str, help="Output .kmx file path")
    p_comp.add_argument(
        "--chunked", action="store_true", help="Force chunked multi-threaded mode"
    )
    p_comp.add_argument(
        "-w", "--workers", type=int, default=4, help="Worker threads"
    )
    p_comp.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress output"
    )

    # Decompress
    p_decomp = subparsers.add_parser("decompress", help="Decompress a file")
    p_decomp.add_argument("input", type=str, help="Input .kmx file path")
    p_decomp.add_argument("output", type=str, help="Output restored file path")
    p_decomp.add_argument(
        "-w", "--workers", type=int, default=4, help="Worker threads"
    )
    p_decomp.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress output"
    )

    args = parser.parse_args()

    if args.command == "compress":
        auto_compress(
            args.input,
            args.output,
            chunked=args.chunked,
            workers=args.workers,
            quiet=args.quiet,
        )
    elif args.command == "decompress":
        auto_decompress(
            args.input, args.output, workers=args.workers, quiet=args.quiet
        )


if __name__ == "__main__":
    main()