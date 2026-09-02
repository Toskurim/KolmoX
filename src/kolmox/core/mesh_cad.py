"""
KolmoX - Advanced CAD & Parametric Geometry Engine (Phase 3)
Supports OBJ, STL (ASCII/Binary), and ISO 10303-21 STEP/STP formats.
"""

import re
import struct
from typing import Tuple

STL_HEADER_SIZE = 80
STEP_NUMERIC_PATTERN = re.compile(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")


class MeshCADEngine:
    @staticmethod
    def is_obj_mesh(data: bytes) -> bool:
        sample = data[:4096].decode("utf-8", errors="ignore")
        has_v = bool(re.search(r"^\s*v\s+[-+]?\d", sample, re.MULTILINE))
        has_f = bool(re.search(r"^\s*f\s+\d", sample, re.MULTILINE))
        return has_v and has_f

    @staticmethod
    def is_stl(data: bytes) -> bool:
        if len(data) < 84:
            return False
        # ASCII STL check
        sample = data[:256].decode("utf-8", errors="ignore").strip().lower()
        if sample.startswith("solid") and "facet" in sample:
            return True
        # Binary STL check: Header (80B) + Triangle Count (4B) + N * 50B
        try:
            expected_triangles = struct.unpack("<I", data[80:84])[0]
            expected_size = 84 + (expected_triangles * 50)
            return len(data) == expected_size and expected_triangles > 0
        except Exception:
            return False

    @staticmethod
    def is_step(data: bytes) -> bool:
        sample = data[:512].decode("utf-8", errors="ignore").upper()
        return "ISO-10303-21" in sample or ("HEADER;" in sample and "DATA;" in sample)

    # --- OBJ Transposition ---
    @staticmethod
    def transpose_mesh(obj_bytes: bytes) -> Tuple[bytes, bytes]:
        text = obj_bytes.decode("utf-8", errors="replace")
        lines = text.splitlines(keepends=True)

        template_parts = []
        x_coords, y_coords, z_coords = [], [], []

        for line in lines:
            if line.startswith("v "):
                parts = line.strip().split()
                if len(parts) >= 4:
                    template_parts.append(f"v {{}} {{}} {{}}{''.join(' ' + p for p in parts[4:])}\n")
                    x_coords.append(parts[1])
                    y_coords.append(parts[2])
                    z_coords.append(parts[3])
                else:
                    template_parts.append(line)
            else:
                template_parts.append(line)

        template_bytes = "".join(template_parts).encode("utf-8")
        geom_stream = (
            ",".join(x_coords) + "\n" +
            ",".join(y_coords) + "\n" +
            ",".join(z_coords)
        ).encode("utf-8")

        return template_bytes, geom_stream

    @staticmethod
    def untranspose_mesh(template_bytes: bytes, geom_bytes: bytes) -> bytes:
        template_text = template_bytes.decode("utf-8", errors="replace")
        geom_text = geom_bytes.decode("utf-8", errors="replace")

        lines = geom_text.splitlines()
        if len(lines) < 3:
            return template_bytes

        x_coords = lines[0].split(",") if lines[0] else []
        y_coords = lines[1].split(",") if lines[1] else []
        z_coords = lines[2].split(",") if lines[2] else []

        restored_lines = []
        v_idx = 0
        num_v = min(len(x_coords), len(y_coords), len(z_coords))

        for line in template_text.splitlines(keepends=True):
            if line.startswith("v {} {} {}"):
                if v_idx < num_v:
                    suffix = line[10:]
                    restored_lines.append(f"v {x_coords[v_idx]} {y_coords[v_idx]} {z_coords[v_idx]}{suffix}")
                    v_idx += 1
                else:
                    restored_lines.append(line)
            else:
                restored_lines.append(line)

        return "".join(restored_lines).encode("utf-8")

    # --- STL Transposition ---
    @staticmethod
    def transpose_stl_binary(data: bytes) -> Tuple[bytes, bytes]:
        header = data[:84]
        num_triangles = struct.unpack("<I", data[80:84])[0]
        records = data[84:]

        normals = bytearray()
        vertices = bytearray()
        attributes = bytearray()

        for i in range(num_triangles):
            offset = i * 50
            normals.extend(records[offset:offset+12])
            vertices.extend(records[offset+12:offset+48])
            attributes.extend(records[offset+48:offset+50])

        geom = bytes(normals) + bytes(vertices) + bytes(attributes)
        return header, geom

    @staticmethod
    def untranspose_stl_binary(header: bytes, geom: bytes) -> bytes:
        num_triangles = struct.unpack("<I", header[80:84])[0]
        norm_len = num_triangles * 12
        vert_len = num_triangles * 36

        normals = geom[:norm_len]
        vertices = geom[norm_len:norm_len + vert_len]
        attributes = geom[norm_len + vert_len:]

        reconstructed = bytearray(header)
        for i in range(num_triangles):
            reconstructed.extend(normals[i*12:(i+1)*12])
            reconstructed.extend(vertices[i*36:(i+1)*36])
            reconstructed.extend(attributes[i*2:(i+1)*2])

        return bytes(reconstructed)

    # --- STEP / ISO 10303-21 Transposition ---
    @staticmethod
    def transpose_step(data: bytes) -> Tuple[bytes, bytes]:
        text = data.decode("utf-8", errors="replace")
        extracted_floats = []

        def replacer(match):
            val = match.group(1)
            if "." in val or "E" in val.upper():
                extracted_floats.append(val)
                return "\x00"
            return val

        template = STEP_NUMERIC_PATTERN.sub(replacer, text)
        geom = "\n".join(extracted_floats).encode("utf-8")
        return template.encode("utf-8"), geom

    @staticmethod
    def untranspose_step(template_bytes: bytes, geom_bytes: bytes) -> bytes:
        template = template_bytes.decode("utf-8", errors="replace")
        geom_floats = geom_bytes.decode("utf-8", errors="replace").splitlines()

        float_iter = iter(geom_floats)
        parts = template.split("\x00")

        out = []
        for i, part in enumerate(parts):
            out.append(part)
            if i < len(parts) - 1:
                try:
                    out.append(next(float_iter))
                except StopIteration:
                    out.append("0.0")

        return "".join(out).encode("utf-8")
