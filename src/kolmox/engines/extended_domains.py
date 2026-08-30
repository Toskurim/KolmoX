"""
KolmoX Extended Domain Preconditioning Engines (v1.1.0)
Bit-exact, high-throughput transforms with C-acceleration and NumPy fallback.
"""

import struct
import numpy as np
from typing import Tuple, List

try:
    from kolmox.core import fast_transforms
    HAS_C_EXT = True
except ImportError:
    HAS_C_EXT = False


class ScientificFloatEngine:
    @staticmethod
    def transform_f32_byte_plane(raw_data: bytes) -> bytes:
        num_bytes = len(raw_data)
        if num_bytes % 4 != 0 or num_bytes == 0:
            return raw_data
        if HAS_C_EXT:
            return fast_transforms.transpose_f32(raw_data)
        arr = np.frombuffer(raw_data, dtype=np.uint8).reshape(-1, 4)
        return arr.T.tobytes()

    @staticmethod
    def inverse_f32_byte_plane(sliced_data: bytes) -> bytes:
        num_bytes = len(sliced_data)
        if num_bytes % 4 != 0 or num_bytes == 0:
            return sliced_data
        if HAS_C_EXT:
            return fast_transforms.untranspose_f32(sliced_data)
        n = num_bytes // 4
        arr = np.frombuffer(sliced_data, dtype=np.uint8).reshape(4, n)
        return arr.T.tobytes()


class AudioPCMEngine:
    @staticmethod
    def is_wav(data: bytes) -> bool:
        return len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WAVE"

    @staticmethod
    def transform_stereo_pcm16(raw_data: bytes) -> Tuple[bytes, bytes]:
        if AudioPCMEngine.is_wav(raw_data):
            data_pos = raw_data.find(b"data")
            if data_pos != -1 and len(raw_data) >= data_pos + 8:
                data_len = struct.unpack("<I", raw_data[data_pos + 4 : data_pos + 8])[0]
                header = raw_data[: data_pos + 8]
                pcm = raw_data[data_pos + 8 : data_pos + 8 + data_len]
            else:
                header = raw_data[:44]
                pcm = raw_data[44:]
        else:
            header = b""
            pcm = raw_data

        num_samples = len(pcm) // 4
        if num_samples == 0:
            return header, pcm

        samples = np.frombuffer(pcm[: num_samples * 4], dtype=np.int16).reshape(-1, 2)
        left = samples[:, 0].astype(np.int32)
        right = samples[:, 1].astype(np.int32)

        diff = (left - right).astype(np.int16)
        delta_left = np.empty_like(left, dtype=np.int16)
        delta_left[0] = left[0]
        delta_left[1:] = (left[1:] - left[:-1]).astype(np.int16)

        processed = delta_left.tobytes() + diff.tobytes()
        return header, processed

    @staticmethod
    def inverse_stereo_pcm16(header: bytes, processed: bytes) -> bytes:
        num_samples = len(processed) // 4
        if num_samples == 0:
            return header + processed

        delta_left = np.frombuffer(processed[: num_samples * 2], dtype=np.int16).astype(np.int32)
        diff = np.frombuffer(processed[num_samples * 2 :], dtype=np.int16).astype(np.int32)

        left = np.cumsum(delta_left).astype(np.int16)
        right = (left.astype(np.int32) - diff).astype(np.int16)

        stereo = np.empty((num_samples, 2), dtype=np.int16)
        stereo[:, 0] = left
        stereo[:, 1] = right

        return header + stereo.tobytes()


class GCodeEngine:
    @staticmethod
    def is_gcode(data: bytes) -> bool:
        sample = data[:1024].decode("utf-8", errors="ignore").upper()
        return "G1 " in sample or "G0 " in sample or "M104" in sample

    @staticmethod
    def transform(raw_data: bytes) -> Tuple[bytes, bytes]:
        lines = raw_data.split(b"\n")
        template_lines = []
        vals_x, vals_y, vals_z = [], [], []

        for line in lines:
            if line.startswith((b"G1 ", b"G0 ")):
                parts = line.split(b" ")
                new_parts = []
                for p in parts:
                    if p.startswith(b"X"):
                        vals_x.append(p[1:])
                        new_parts.append(b"X\x00")
                    elif p.startswith(b"Y"):
                        vals_y.append(p[1:])
                        new_parts.append(b"Y\x00")
                    elif p.startswith(b"Z"):
                        vals_z.append(p[1:])
                        new_parts.append(b"Z\x00")
                    else:
                        new_parts.append(p)
                template_lines.append(b" ".join(new_parts))
            else:
                template_lines.append(line)

        template = b"\n".join(template_lines)
        coords = b"\n".join(vals_x + [b"---"] + vals_y + [b"---"] + vals_z)
        return template, coords

    @staticmethod
    def inverse(template: bytes, coords: bytes) -> bytes:
        if not coords:
            return template
        sections = coords.split(b"\n---\n")
        vals_x = sections[0].split(b"\n") if len(sections) > 0 and sections[0] else []
        vals_y = sections[1].split(b"\n") if len(sections) > 1 and sections[1] else []
        vals_z = sections[2].split(b"\n") if len(sections) > 2 and sections[2] else []

        ix, iy, iz = 0, 0, 0
        lines = template.split(b"\n")
        out_lines = []

        for line in lines:
            if b"\x00" in line:
                parts = line.split(b" ")
                new_parts = []
                for p in parts:
                    if p == b"X\x00" and ix < len(vals_x):
                        new_parts.append(b"X" + vals_x[ix])
                        ix += 1
                    elif p == b"Y\x00" and iy < len(vals_y):
                        new_parts.append(b"Y" + vals_y[iy])
                        iy += 1
                    elif p == b"Z\x00" and iz < len(vals_z):
                        new_parts.append(b"Z" + vals_z[iz])
                        iz += 1
                    else:
                        new_parts.append(p)
                out_lines.append(b" ".join(new_parts))
            else:
                out_lines.append(line)

        return b"\n".join(out_lines)


class PointCloudEngine:
    @staticmethod
    def transform_xyz_ascii(raw_data: bytes) -> Tuple[bytes, bytes]:
        lines = raw_data.split(b"\n")
        xs, ys, zs = [], [], []
        for line in lines:
            parts = line.split()
            if len(parts) == 3:
                xs.append(parts[0])
                ys.append(parts[1])
                zs.append(parts[2])
        manifest = struct.pack("<I", len(xs))
        payload = b"\n".join(xs + [b"---"] + ys + [b"---"] + zs)
        return manifest, payload

    @staticmethod
    def inverse_xyz_ascii(manifest: bytes, payload: bytes) -> bytes:
        if len(manifest) < 4:
            return payload
        count = struct.unpack("<I", manifest[:4])[0]
        sections = payload.split(b"\n---\n")
        if len(sections) < 3:
            return payload
        xs = sections[0].split(b"\n")
        ys = sections[1].split(b"\n")
        zs = sections[2].split(b"\n")
        out = []
        for i in range(count):
            out.append(xs[i] + b" " + ys[i] + b" " + zs[i])
        return b"\n".join(out) + b"\n"


class BinaryBCJEngine:
    @staticmethod
    def transform_x86(raw_data: bytes) -> bytes:
        data = bytearray(raw_data)
        length = len(data)
        i = 0
        while i + 4 < length:
            b = data[i]
            if b in (0xE8, 0xE9):
                rel = struct.unpack("<i", data[i + 1 : i + 5])[0]
                abs_addr = (rel + (i + 5)) & 0xFFFFFFFF
                data[i + 1 : i + 5] = struct.pack("<I", abs_addr)
                i += 5
            else:
                i += 1
        return bytes(data)

    @staticmethod
    def inverse_x86(transformed: bytes) -> bytes:
        data = bytearray(transformed)
        length = len(data)
        i = 0
        while i + 4 < length:
            b = data[i]
            if b in (0xE8, 0xE9):
                abs_addr = struct.unpack("<I", data[i + 1 : i + 5])[0]
                rel = (abs_addr - (i + 5)) & 0xFFFFFFFF
                data[i + 1 : i + 5] = struct.pack("<i", struct.unpack("<i", struct.pack("<I", rel))[0])
                i += 5
            else:
                i += 1
        return bytes(data)
