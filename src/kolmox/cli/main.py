"""
KolmoX - Unified CLI Auto-Dispatcher
"""

import argparse
import os
import sys
from kolmox.core.pipeline import KolmoXPipeline
from kolmox.core.mesh_cad import MeshCADEngine
from kolmox.engines.video_stream import VideoStreamEngine

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}


def auto_compress(input_path: str, output_path: str, level: int):
    _, ext = os.path.splitext(input_path.lower())

    if ext in VIDEO_EXTS:
        print(f"[Auto-Dispatch] Detected video format ({ext}). Routing to Hardware Video Stream Engine...")
        VideoStreamEngine.compress_video_stream(input_path, output_path)
        return

    with open(input_path, "rb") as f:
        raw_data = f.read()

    if ext == ".obj" or MeshCADEngine.is_obj_mesh(raw_data):
        print("[Auto-Dispatch] Detected 3D Mesh / CAD geometry. Routing to MeshCAD Engine...")
        template, geom = MeshCADEngine.transpose_mesh(raw_data)
        intermediate = b"KCAD" + len(template).to_bytes(4, "big") + template + geom
        pipeline = KolmoXPipeline(compression_level=level)
        compressed = pipeline.compress_bytes(intermediate)
        with open(output_path, "wb") as out:
            out.write(compressed)
        ratio = len(raw_data) / max(1, len(compressed))
        print(f"[KolmoX] CAD Mesh compressed: {len(raw_data)} -> {len(compressed)} bytes ({ratio:.2f}x)")
        return

    print("[Auto-Dispatch] Routing to Multi-Domain Structural Pipeline...")
    pipeline = KolmoXPipeline(compression_level=level)
    compressed = pipeline.compress_bytes(raw_data)
    with open(output_path, "wb") as out:
        out.write(compressed)
    ratio = len(raw_data) / max(1, len(compressed))
    print(f"[KolmoX] File compressed: {len(raw_data)} -> {len(compressed)} bytes ({ratio:.2f}x)")


def auto_decompress(input_path: str, output_path: str):
    _, ext = os.path.splitext(input_path.lower())
    if ext == ".kmxv":
        print("[Auto-Dispatch] Detected KolmoX Video Container. Routing to Video Decoder...")
        VideoStreamEngine.decompress_video_stream(input_path, output_path)
        return

    with open(input_path, "rb") as f:
        compressed = f.read()

    pipeline = KolmoXPipeline()
    decompressed = pipeline.decompress_bytes(compressed)

    if decompressed.startswith(b"KCAD"):
        print("[Auto-Dispatch] Detected KCAD payload. Reconstructing 3D Mesh...")
        template_len = int.from_bytes(decompressed[4:8], "big")
        template = decompressed[8:8 + template_len]
        geom = decompressed[8 + template_len:]
        restored = MeshCADEngine.untranspose_mesh(template, geom)
        with open(output_path, "wb") as out:
            out.write(restored)
        print(f"[KolmoX] CAD Mesh successfully restored ({len(restored)} bytes).")
        return

    with open(output_path, "wb") as out:
        out.write(decompressed)
    print(f"[KolmoX] File successfully decompressed ({len(decompressed)} bytes).")


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

    # Unified Decompress
    d_parser = subparsers.add_parser("decompress", help="Auto-detect and decompress any KolmoX container")
    d_parser.add_argument("input", help="Input KolmoX file path")
    d_parser.add_argument("output", help="Output restored file path")

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
        auto_compress(args.input, args.output, args.level)
    elif args.command == "decompress":
        auto_decompress(args.input, args.output)
    elif args.command == "compress-video":
        VideoStreamEngine.compress_video_stream(args.input, args.output, max_frames=args.max_frames)
    elif args.command == "decompress-video":
        VideoStreamEngine.decompress_video_stream(args.input, args.output)


if __name__ == "__main__":
    main()
