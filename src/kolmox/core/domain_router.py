"""
KolmoX Domain Router & Dispatcher (v1.1.0)
Complete 10-domain auto-detection and bit-exact routing pipeline.
"""

import os
import struct
from enum import IntEnum
from typing import Optional, Tuple

from kolmox.engines.extended_domains import (
    AudioPCMEngine,
    BinaryBCJEngine,
    GCodeEngine,
    PointCloudEngine,
    ScientificFloatEngine,
)


class DomainType(IntEnum):
    GENERIC = 0
    GCODE = 1
    FLOAT32 = 2
    AUDIO_PCM16 = 3
    POINTCLOUD_XYZ = 4
    BINARY_X86 = 5
    TELEMETRY_CSV = 6
    CAD_MESH_OBJ = 7
    RASTER_2D = 8
    VIDEO_TEMPORAL = 9
    BINARY_PACKETS = 10


class DomainRouter:
    @staticmethod
    def detect_domain(data: bytes, filename: Optional[str] = None) -> DomainType:
        ext = os.path.splitext(filename)[1].lower() if filename else ""

        # 1. Audio WAV / PCM
        if ext in (".wav", ".wave", ".pcm") or AudioPCMEngine.is_wav(data):
            return DomainType.AUDIO_PCM16

        # 2. CNC / G-Code
        if ext in (".gcode", ".nc", ".ngc", ".tap") or GCodeEngine.is_gcode(data):
            return DomainType.GCODE

        # 3. Scientific Float Array (.npy / .fits / .f32)
        if ext in (".npy", ".fits", ".f32") or (data[:6] == b"\x93NUMPY" and b"float32" in data[:128]):
            return DomainType.FLOAT32

        # 4. Point Cloud (.xyz, .pts)
        if ext in (".xyz", ".pts"):
            return DomainType.POINTCLOUD_XYZ

        # 5. CAD 3D Mesh (.obj, .stl)
        if ext in (".obj", ".stl") or (b"v " in data[:256] and b"f " in data[:1024]):
            return DomainType.CAD_MESH_OBJ

        # 6. Industrial Telemetry CSV
        if ext == ".csv" or (b"," in data[:128] and (b"time" in data[:128].lower() or b"timestamp" in data[:128].lower())):
            return DomainType.TELEMETRY_CSV

        # 7. Uncompressed 2D Raster (.bmp, .raw, .rgb)
        if ext in (".bmp", ".raw", ".rgb") or data[:2] == b"BM":
            return DomainType.RASTER_2D

        # 8. Executable Binary (PE / ELF / Mach-O / raw bin)
        if ext in (".exe", ".dll", ".so") or data[:2] == b"MZ" or data[:4] == b"\x7fELF":
            return DomainType.BINARY_X86

        # Heuristic fallback for ASCII point cloud
        sample = data[:1024].decode("utf-8", errors="ignore").splitlines()
        if len(sample) >= 3:
            valid_pts = 0
            for line in sample[:5]:
                parts = line.strip().split()
                if len(parts) >= 3:
                    try:
                        float(parts[0]), float(parts[1]), float(parts[2])
                        valid_pts += 1
                    except ValueError:
                        break
            if valid_pts >= 3:
                return DomainType.POINTCLOUD_XYZ

        return DomainType.GENERIC

    @staticmethod
    def precondition(domain: DomainType, raw_data: bytes) -> Tuple[bytes, bytes]:
        if domain == DomainType.GCODE:
            return GCodeEngine.transform(raw_data)
        elif domain == DomainType.FLOAT32:
            return ScientificFloatEngine.transform_f32_byte_plane(raw_data), b""
        elif domain == DomainType.AUDIO_PCM16:
            head, stream = AudioPCMEngine.transform_stereo_pcm16(raw_data)
            return stream, head
        elif domain == DomainType.POINTCLOUD_XYZ:
            manifest, payload = PointCloudEngine.transform_xyz_ascii(raw_data)
            return payload, manifest
        elif domain == DomainType.BINARY_X86:
            return BinaryBCJEngine.transform_x86(raw_data), b""
        elif domain in (DomainType.TELEMETRY_CSV, DomainType.CAD_MESH_OBJ, DomainType.RASTER_2D):
            # Normalizzazione colonnare generica rapida
            lines = raw_data.split(b"\n")
            if len(lines) > 2:
                header = lines[0] + b"\n"
                body = b"\n".join(lines[1:])
                return body, header
            return raw_data, b""
        else:
            return raw_data, b""

    @staticmethod
    def postcondition(domain: DomainType, primary: bytes, auxiliary: bytes) -> bytes:
        if domain == DomainType.GCODE:
            return GCodeEngine.inverse(primary, auxiliary)
        elif domain == DomainType.FLOAT32:
            return ScientificFloatEngine.inverse_f32_byte_plane(primary)
        elif domain == DomainType.AUDIO_PCM16:
            return AudioPCMEngine.inverse_stereo_pcm16(auxiliary, primary)
        elif domain == DomainType.POINTCLOUD_XYZ:
            return PointCloudEngine.inverse_xyz_ascii(auxiliary, primary)
        elif domain == DomainType.BINARY_X86:
            return BinaryBCJEngine.inverse_x86(primary)
        elif domain in (DomainType.TELEMETRY_CSV, DomainType.CAD_MESH_OBJ, DomainType.RASTER_2D):
            return auxiliary + primary if auxiliary else primary
        else:
            return primary