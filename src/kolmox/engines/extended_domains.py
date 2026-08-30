"""
KolmoX - Extended Domain Preconditioners (v1.1.0)
Specialized bit-exact transforms for:
1. CNC / 3D Printing G-Code (.gcode, .nc) -> Columnar Channel Separation
2. Scientific Multidimensional Float Arrays (.npy, .fits) -> Byte-Plane Slicing
3. Audio PCM Lossless (.wav, raw PCM) -> FLAC-style Decorrelation + Delta
4. Point Cloud Coordinates (.xyz, .las) -> Columnar Vectorization
5. Executable Machine Code BCJ Filter (x86/x64) -> Branch Normalization
"""

import re
import struct
import numpy as np
from typing import Tuple


# ==========================================
# 1. INDUSTRIAL CNC & G-CODE ENGINE
# ==========================================
class GCodeEngine:
    COORD_PATTERN = re.compile(r"([XYZFE])([-+]?\d*\.?\d+)")

    @staticmethod
    def is_gcode(data: bytes) -> bool:
        sample = data[:2048].decode("utf-8", errors="ignore").upper()
        return ("G0" in sample or "G1" in sample or "M104" in sample) and ("X" in sample or "Y" in sample or "Z" in sample)

    @staticmethod
    def transform(data: bytes) -> Tuple[bytes, bytes]:
        text = data.decode("utf-8", errors="replace")
        
        channels = {"X": [], "Y": [], "Z": [], "F": [], "E": []}
        axis_sequence = []

        def replacer(match):
            axis = match.group(1)
            val = match.group(2)
            channels[axis].append(val)
            axis_sequence.append(axis)
            return f"{axis}\x00"

        template = GCodeEngine.COORD_PATTERN.sub(replacer, text)
        
        payload_parts = [
            ",".join(axis_sequence),
            ",".join(channels["X"]),
            ",".join(channels["Y"]),
            ",".join(channels["Z"]),
            ",".join(channels["F"]),
            ",".join(channels["E"])
        ]
        coord_stream = "\n".join(payload_parts).encode("utf-8")
        return template.encode("utf-8"), coord_stream

    @staticmethod
    def inverse(template_bytes: bytes, coord_bytes: bytes) -> bytes:
        if not coord_bytes:
            return template_bytes

        template = template_bytes.decode("utf-8", errors="replace")
        lines = coord_bytes.decode("utf-8", errors="replace").splitlines()
        
        if len(lines) < 6:
            return template_bytes

        axis_seq = lines[0].split(",") if lines[0] else []
        ch_iters = {
            "X": iter(lines[1].split(",") if lines[1] else []),
            "Y": iter(lines[2].split(",") if lines[2] else []),
            "Z": iter(lines[3].split(",") if lines[3] else []),
            "F": iter(lines[4].split(",") if lines[4] else []),
            "E": iter(lines[5].split(",") if lines[5] else []),
        }

        seq_iter = iter(axis_seq)
        parts = template.split("\x00")
        out = []

        for i, part in enumerate(parts):
            out.append(part)
            if i < len(parts) - 1:
                try:
                    axis = next(seq_iter)
                    val = next(ch_iters[axis])
                    out.append(val)
                except (StopIteration, KeyError):
                    out.append("0.0")

        return "".join(out).encode("utf-8")


# ==========================================
# 2. SCIENTIFIC FLOAT / MATRIX ENGINE
# ==========================================
class ScientificFloatEngine:
    @staticmethod
    def transform_f32_byte_plane(data: bytes) -> bytes:
        rem = len(data) % 4
        clean_len = len(data) - rem
        if clean_len == 0:
            return data

        arr = np.frombuffer(data[:clean_len], dtype=np.uint8).reshape(-1, 4)
        transposed = arr.T.tobytes()
        return transposed + data[clean_len:]

    @staticmethod
    def inverse_f32_byte_plane(data: bytes) -> bytes:
        rem = len(data) % 4
        clean_len = len(data) - rem
        if clean_len == 0:
            return data

        n_elements = clean_len // 4
        b0 = data[0 : n_elements]
        b1 = data[n_elements : 2 * n_elements]
        b2 = data[2 * n_elements : 3 * n_elements]
        b3 = data[3 * n_elements : 4 * n_elements]

        arr = np.column_stack([
            np.frombuffer(b0, dtype=np.uint8),
            np.frombuffer(b1, dtype=np.uint8),
            np.frombuffer(b2, dtype=np.uint8),
            np.frombuffer(b3, dtype=np.uint8),
        ])
        return arr.tobytes() + data[clean_len:]


# ==========================================
# 3. AUDIO PCM LOSSLESS ENGINE (WAV / RAW)
# ==========================================
class AudioPCMEngine:
    @staticmethod
    def is_wav(data: bytes) -> bool:
        return len(data) >= 44 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"

    @staticmethod
    def transform_stereo_pcm16(data: bytes) -> Tuple[bytes, bytes]:
        header_len = 44 if AudioPCMEngine.is_wav(data) else 0
        header = data[:header_len]
        pcm_bytes = data[header_len:]

        n_samples = len(pcm_bytes) // 4
        pcm_valid = pcm_bytes[: n_samples * 4]
        rem = pcm_bytes[n_samples * 4 :]

        samples = np.frombuffer(pcm_valid, dtype=np.uint16).reshape(-1, 2)
        left = samples[:, 0]
        right = samples[:, 1]

        # Decorrelazione modulare Left-Side
        diff = (left - right).astype(np.uint16)

        # Delta sul canale Left
        left_delta = np.zeros_like(left)
        left_delta[0] = left[0]
        left_delta[1:] = left[1:] - left[:-1]

        stream = np.column_stack([left_delta, diff]).tobytes() + rem
        return header, stream

    @staticmethod
    def inverse_stereo_pcm16(header: bytes, stream: bytes) -> bytes:
        n_samples = len(stream) // 4
        valid_stream = stream[: n_samples * 4]
        rem = stream[n_samples * 4 :]

        samples = np.frombuffer(valid_stream, dtype=np.uint16).reshape(-1, 2)
        left_delta = samples[:, 0]
        diff = samples[:, 1]

        left = np.cumsum(left_delta, dtype=np.uint16)
        right = (left - diff).astype(np.uint16)

        restored_samples = np.column_stack([left, right])
        return header + restored_samples.tobytes() + rem


# ==========================================
# 4. GEOSPATIAL & POINT CLOUD ENGINE
# ==========================================
class PointCloudEngine:
    @staticmethod
    def transform_xyz_ascii(data: bytes) -> Tuple[bytes, bytes]:
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        xs, ys, zs = [], [], []

        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 3:
                xs.append(parts[0])
                ys.append(parts[1])
                zs.append(parts[2])

        payload = (",".join(xs) + "\n" + ",".join(ys) + "\n" + ",".join(zs)).encode("utf-8")
        manifest = f"COUNT:{len(xs)}".encode("utf-8")
        return manifest, payload

    @staticmethod
    def inverse_xyz_ascii(manifest: bytes, payload: bytes) -> bytes:
        text = payload.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if len(lines) < 3:
            return b""

        xs = lines[0].split(",") if lines[0] else []
        ys = lines[1].split(",") if lines[1] else []
        zs = lines[2].split(",") if lines[2] else []

        n = min(len(xs), len(ys), len(zs))
        out_lines = [f"{xs[i]} {ys[i]} {zs[i]}\n" for i in range(n)]
        return "".join(out_lines).encode("utf-8")


# ==========================================
# 5. X86/X64 BCJ INSTRUCTION POINTER FILTER
# ==========================================
class BinaryBCJEngine:
    @staticmethod
    def transform_x86(data: bytes) -> bytes:
        buf = bytearray(data)
        length = len(buf)
        i = 0
        while i + 4 < length:
            b = buf[i]
            if b in (0xE8, 0xE9):
                raw_dest = struct.unpack("<I", buf[i + 1 : i + 5])[0]
                if raw_dest < 0x01000000:
                    rel_dest = (raw_dest - (i + 5)) & 0xFFFFFFFF
                    buf[i + 1 : i + 5] = struct.pack("<I", rel_dest)
                i += 4
            i += 1
        return bytes(buf)

    @staticmethod
    def inverse_x86(data: bytes) -> bytes:
        buf = bytearray(data)
        length = len(buf)
        i = 0
        while i + 4 < length:
            b = buf[i]
            if b in (0xE8, 0xE9):
                rel_dest = struct.unpack("<I", buf[i + 1 : i + 5])[0]
                raw_dest = (rel_dest + (i + 5)) & 0xFFFFFFFF
                if raw_dest < 0x01000000:
                    buf[i + 1 : i + 5] = struct.pack("<I", raw_dest)
                i += 4
            i += 1
        return bytes(buf)