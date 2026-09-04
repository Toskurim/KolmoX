"""
KolmoX Domain Router & Dispatcher (v1.1.0)
Complete 10-domain auto-detection and bit-exact routing pipeline.
"""

import os
import struct
from enum import IntEnum
from typing import Optional, Tuple

from kolmox.core.stride import StrideEngine
from kolmox.engines.columnar_text import ColumnarTextEngine
from kolmox.engines.raster_engine import RasterEngine
from kolmox.engines.video_engine import VideoEngine
from kolmox.engines.extended_domains import (
    AudioPCMEngine,
    BinaryBCJEngine,
    GCodeEngine,
    PointCloudEngine,
    ScientificFloatEngine,
)

# Self-describing container for a raw, un-encoded multi-frame video blob fed
# into compress_bytes(): MAGIC(8s) + width(I) + height(I) + channels(B) + num_frames(I),
# followed by num_frames * width*height*channels concatenated raw frame bytes.
VIDEO_RAW_SEQUENCE_MAGIC = b"KMXVRAW1"
VIDEO_RAW_SEQUENCE_HEADER_FMT = ">8sIIBI"
VIDEO_RAW_SEQUENCE_HEADER_LEN = 21


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

        # 6b. Raw multi-frame video sequence (self-describing magic, checked
        # before the .raw/.rgb raster heuristic below to avoid ambiguity).
        if data[:8] == VIDEO_RAW_SEQUENCE_MAGIC:
            return DomainType.VIDEO_TEMPORAL

        # 7. Uncompressed 2D Raster (.bmp, .raw, .rgb)
        if ext in (".bmp", ".raw", ".rgb") or data[:2] == b"BM":
            return DomainType.RASTER_2D

        # 8. Executable Binary (PE / ELF / Mach-O / raw bin)
        if ext in (".exe", ".dll", ".so") or data[:2] == b"MZ" or data[:4] == b"\x7fELF":
            return DomainType.BINARY_X86

        # 9. Fixed-Stride Binary Packets (network captures, sensor frames, generic
        # binary records). The extension is only a hint - detect_stride() must
        # actually find a periodic record structure via autocorrelation.
        if ext in (".bin", ".pkt", ".pcap", ".dat") and StrideEngine.detect_stride(data) is not None:
            return DomainType.BINARY_PACKETS

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

        # Last-resort structural check: no extension hint matched anything above,
        # but the byte stream still shows a strong fixed-stride record pattern.
        if not ext and StrideEngine.detect_stride(data) is not None:
            return DomainType.BINARY_PACKETS

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
        elif domain == DomainType.BINARY_PACKETS:
            stride = StrideEngine.detect_stride(raw_data)
            if stride is None:
                raise ValueError("BINARY_PACKETS: no stride detected, cannot transpose.")
            return StrideEngine.transpose(raw_data, stride), struct.pack("<B", stride)
        elif domain == DomainType.RASTER_2D:
            return RasterEngine.transform_bmp(raw_data)
        elif domain == DomainType.VIDEO_TEMPORAL:
            if len(raw_data) < VIDEO_RAW_SEQUENCE_HEADER_LEN or raw_data[:8] != VIDEO_RAW_SEQUENCE_MAGIC:
                raise ValueError("Not a KolmoX raw video sequence blob")
            _magic, width, height, channels, num_frames = struct.unpack(
                VIDEO_RAW_SEQUENCE_HEADER_FMT, raw_data[:VIDEO_RAW_SEQUENCE_HEADER_LEN]
            )
            if channels != 3:
                # VideoEngine.decompress_sequence hardcodes channels=3 today.
                raise ValueError("VIDEO_TEMPORAL currently only supports channels=3")
            frame_size = width * height * channels
            expected_len = VIDEO_RAW_SEQUENCE_HEADER_LEN + num_frames * frame_size
            if num_frames <= 0 or len(raw_data) != expected_len:
                raise ValueError("Raw video sequence blob size mismatch")
            frame_bytes = raw_data[VIDEO_RAW_SEQUENCE_HEADER_LEN:]
            frames = [
                frame_bytes[i * frame_size : (i + 1) * frame_size] for i in range(num_frames)
            ]
            return VideoEngine.compress_sequence(frames, width, height, channels), b""
        elif domain == DomainType.TELEMETRY_CSV:
            # Righe uniformi separate da virgola: basta la forma (numero di campi).
            # delimiter=None: rilevato dai dati. Un CSV di locale europeo usa
            # il punto e virgola per i campi e la virgola per i decimali;
            # assumere la virgola spezzava i decimali e costava 14.78 punti.
            return ColumnarTextEngine.transform(raw_data, None, group_by_first_token=False)
        elif domain == DomainType.CAD_MESH_OBJ:
            # OBJ mescola tipi di riga diversi (v / vn / f / #): il token iniziale
            # fa parte della forma, cosi' i piani dei vertici restano separati.
            return ColumnarTextEngine.transform(raw_data, b" ", group_by_first_token=True)
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
        elif domain == DomainType.BINARY_PACKETS:
            (stride,) = struct.unpack("<B", auxiliary)
            return StrideEngine.untranspose(primary, stride, len(primary))
        elif domain == DomainType.RASTER_2D:
            return RasterEngine.inverse_bmp(primary, auxiliary)
        elif domain == DomainType.VIDEO_TEMPORAL:
            frames = VideoEngine.decompress_sequence(primary)
            _magic, width, height, num_frames = struct.unpack(">5sIII", primary[:17])
            header = struct.pack(
                VIDEO_RAW_SEQUENCE_HEADER_FMT,
                VIDEO_RAW_SEQUENCE_MAGIC,
                width,
                height,
                3,
                num_frames,
            )
            return header + b"".join(frames)
        elif domain in (DomainType.TELEMETRY_CSV, DomainType.CAD_MESH_OBJ):
            return ColumnarTextEngine.inverse(primary)
        else:
            return primary