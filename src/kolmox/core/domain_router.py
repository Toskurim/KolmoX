"""
KolmoX Domain Router & Dispatcher (v1.1.0)
Auto-detects data domain and routes to optimal bit-exact preconditioning engine.
"""

from enum import IntEnum
from typing import Tuple, Optional
import os

from kolmox.engines.extended_domains import (
    GCodeEngine,
    ScientificFloatEngine,
    AudioPCMEngine,
    PointCloudEngine,
    BinaryBCJEngine,
)


class DomainType(IntEnum):
    GENERIC = 0
    GCODE = 1
    FLOAT32 = 2
    AUDIO_PCM16 = 3
    POINTCLOUD_XYZ = 4
    BINARY_X86 = 5


class DomainRouter:
    @staticmethod
    def detect_domain(data: bytes, filename: Optional[str] = None) -> DomainType:
        ext = os.path.splitext(filename)[1].lower() if filename else ""

        # 1. Audio WAV / PCM detection
        if ext in (".wav", ".wave", ".pcm") or AudioPCMEngine.is_wav(data):
            return DomainType.AUDIO_PCM16

        # 2. CNC / G-Code detection
        if ext in (".gcode", ".nc", ".ngc", ".tap") or GCodeEngine.is_gcode(data):
            return DomainType.GCODE

        # 3. Scientific Float Array (.npy / .fits / .f32)
        if ext in (".npy", ".fits", ".f32") or (data[:6] == b"\x93NUMPY" and b"float32" in data[:128]):
            return DomainType.FLOAT32

        # 4. Point Cloud Coordinates (.xyz, .pts)
        if ext in (".xyz", ".pts"):
            return DomainType.POINTCLOUD_XYZ

        # 5. Executable Binary (PE / ELF / Mach-O / raw bin)
        if ext in (".exe", ".dll", ".so", ".bin") or data[:2] == b"MZ" or data[:4] == b"\x7fELF":
            return DomainType.BINARY_X86

        # Heuristic fallback for ASCII point cloud without extension
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
            tmpl, coords = GCodeEngine.transform(raw_data)
            return tmpl, coords
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
        else:
            return primary