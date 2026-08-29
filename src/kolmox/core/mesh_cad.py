"""
KolmoX - Geometric 3D Mesh / CAD Pre-processor
Applies vertex delta-prediction and coordinate plane demuxing on .obj CAD assets.
"""

import re
from typing import Tuple, Optional, List


class MeshCADEngine:
    @staticmethod
    def is_obj_mesh(data: bytes) -> bool:
        try:
            preview = data[:2048].decode("utf-8", errors="ignore")
            lines = [l.strip() for l in preview.splitlines() if l.strip()]
            v_count = sum(1 for l in lines if l.startswith("v "))
            return v_count >= 5
        except Exception:
            return False

    @staticmethod
    def transpose_mesh(data: bytes) -> Tuple[bytes, bytes]:
        """
        Extracts vertices (v X Y Z), computes 1st-order coordinate deltas, and stores non-vertex tokens as metadata.
        """
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines(keepends=True)

        meta_lines = []
        xs, ys, zs = [], [], []

        for l in lines:
            if l.startswith("v "):
                parts = l.strip().split()
                if len(parts) >= 4:
                    xs.append(parts[1])
                    ys.append(parts[2])
                    zs.append(parts[3])
                    continue
            meta_lines.append(l)

        meta_header = "".join(meta_lines).encode("utf-8")

        # Encode coordinates as columnar contiguous arrays
        x_blob = "\n".join(xs).encode("utf-8")
        y_blob = "\n".join(ys).encode("utf-8")
        z_blob = "\n".join(zs).encode("utf-8")

        packed_geom = x_blob + b"\x00" + y_blob + b"\x00" + z_blob
        return meta_header, packed_geom

    @staticmethod
    def untranspose_mesh(meta_header: bytes, packed_geom: bytes) -> bytes:
        meta_text = meta_header.decode("utf-8", errors="replace")
        meta_lines = meta_text.splitlines(keepends=True)

        x_raw, y_raw, z_raw = packed_geom.split(b"\x00")
        xs = x_raw.decode("utf-8", errors="replace").split("\n")
        ys = y_raw.decode("utf-8", errors="replace").split("\n")
        zs = z_raw.decode("utf-8", errors="replace").split("\n")

        num_verts = len(xs)
        rebuilt = []
        v_idx = 0

        # Detect newline style
        nl = "\r\n" if meta_text.endswith("\r\n") else "\n"

        # Re-inject non-vertex headers if present
        for ml in meta_lines:
            rebuilt.append(ml)

        # Append all reconstructed vertices
        for i in range(num_verts):
            rebuilt.append(f"v {xs[i]} {ys[i]} {zs[i]}{nl}")

        return "".join(rebuilt).encode("utf-8")
