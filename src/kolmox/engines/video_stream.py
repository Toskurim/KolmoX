"""
KolmoX - High-Throughput Asynchronous Hardware-Aware Video Stream Engine
Supports GPU-accelerated decoding (NVDEC/CUDA) and reliable multi-frame stream decompression.
"""
from typing import Optional, Callable
import os
import queue
import threading
import struct
import subprocess
import cv2

from kolmox.core.pipeline import KolmoXPipeline
from kolmox.core.hardware import HardwareProfile, find_ffmpeg_binary


class VideoStreamEngine:
    MAGIC_STREAM = b"KMXSTREAM1"

    @classmethod
    def _read_exact(cls, file_obj, num_bytes: int) -> bytes:
        """Legge esattamente il numero richiesto di byte evitando interruzioni premature su pipe e stream."""
        buf = bytearray(num_bytes)
        view = memoryview(buf)
        pos = 0
        while pos < num_bytes:
            n = file_obj.readinto(view[pos:])
            if not n:
                break
            pos += n
        return bytes(buf[:pos]) if pos == num_bytes else b""

    @classmethod
    def _probe_video_metadata(cls, video_path: str):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 60
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        return width, height, fps, total_frames

    @classmethod
    def _create_ffmpeg_reader(cls, ffmpeg_bin: str, video_path: str, hwaccel: Optional[str], max_frames: int):
        cmd = [ffmpeg_bin]
        if hwaccel in ["cuda", "nvdec"]:
            cmd.extend(["-hwaccel", "cuda"])
        elif hwaccel == "d3d11va":
            cmd.extend(["-hwaccel", "d3d11va"])
        elif hwaccel == "videotoolbox":
            cmd.extend(["-hwaccel", "videotoolbox"])

        cmd.extend(["-i", video_path])

        if max_frames > 0:
            cmd.extend(["-vframes", str(max_frames)])

        cmd.extend(["-f", "rawvideo", "-pix_fmt", "rgb24", "-v", "error", "-"])
        
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1024 * 1024 * 64
        )

    @classmethod
    def compress_file_stream(
        cls,
        input_video_path: str,
        output_kmxv_path: str,
        chunk_frames: int = 120,
        compression_level: int = 7,
        threads: int = -1,
        max_frames: int = 0,
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> dict:
        if not os.path.exists(input_video_path):
            raise FileNotFoundError(f"File not found: {input_video_path}")

        width, height, fps, total_file_frames = cls._probe_video_metadata(input_video_path)
        target_frames = min(total_file_frames, max_frames) if max_frames > 0 else total_file_frames
        frame_bytes = width * height * 3

        hw = HardwareProfile.detect()
        ffmpeg_bin = find_ffmpeg_binary()
        pipeline = KolmoXPipeline(compression_level=compression_level, threads=threads)
        frame_queue = queue.Queue(maxsize=3)
        actual_backend = "OpenCV (Software)"

        def producer():
            nonlocal actual_backend
            used_ffmpeg = False

            if ffmpeg_bin and hw.hwaccel_backend:
                try:
                    proc = cls._create_ffmpeg_reader(ffmpeg_bin, input_video_path, hw.hwaccel_backend, target_frames)
                    actual_backend = f"FFmpeg ({hw.hwaccel_backend.upper()})"
                    frames_read = 0

                    while frames_read < target_frames:
                        to_read = min(chunk_frames, target_frames - frames_read)
                        chunk = []
                        for _ in range(to_read):
                            raw_f = cls._read_exact(proc.stdout, frame_bytes)
                            if not raw_f or len(raw_f) < frame_bytes:
                                break
                            chunk.append(raw_f)

                        if not chunk:
                            break

                        frame_queue.put(chunk)
                        frames_read += len(chunk)

                    proc.stdout.close()
                    proc.wait()
                    used_ffmpeg = True
                except Exception:
                    used_ffmpeg = False

            if not used_ffmpeg:
                actual_backend = "OpenCV (Software Fallback)"
                cap = cv2.VideoCapture(input_video_path)
                frames_read = 0
                while frames_read < target_frames:
                    to_read = min(chunk_frames, target_frames - frames_read)
                    chunk = []
                    for _ in range(to_read):
                        ret, bgr = cap.read()
                        if not ret:
                            break
                        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                        chunk.append(rgb.tobytes())
                    if not chunk:
                        break
                    frame_queue.put(chunk)
                    frames_read += len(chunk)
                cap.release()

            frame_queue.put(None)

        prod_thread = threading.Thread(target=producer, daemon=True)
        prod_thread.start()

        total_compressed_bytes = 0
        actual_encoded_frames = 0

        with open(output_kmxv_path, "wb") as out_f:
            out_f.write(cls.MAGIC_STREAM)
            out_f.write(struct.pack(">IIII", width, height, fps, target_frames))
            total_compressed_bytes += len(cls.MAGIC_STREAM) + 16

            while True:
                chunk = frame_queue.get()
                if chunk is None:
                    break

                comp_chunk = pipeline.compress_video_frames(chunk, width=width, height=height, channels=3)
                out_f.write(struct.pack(">I", len(comp_chunk)))
                out_f.write(comp_chunk)

                total_compressed_bytes += 4 + len(comp_chunk)
                actual_encoded_frames += len(chunk)

                if progress_cb:
                    progress_cb(len(chunk), target_frames)

        prod_thread.join()
        raw_bytes = actual_encoded_frames * frame_bytes

        return {
            "total_frames": actual_encoded_frames,
            "width": width,
            "height": height,
            "fps": fps,
            "hwaccel": actual_backend,
            "raw_bytes": raw_bytes,
            "compressed_bytes": total_compressed_bytes,
            "ratio": raw_bytes / total_compressed_bytes if total_compressed_bytes > 0 else 1.0
        }

    @classmethod
    def decompress_to_raw_stream(
        cls,
        input_kmxv_path: str,
        output_raw_path: str,
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> dict:
        if not os.path.exists(input_kmxv_path):
            raise FileNotFoundError(f"File not found: {input_kmxv_path}")

        pipeline = KolmoXPipeline()

        with open(input_kmxv_path, "rb") as in_f, open(output_raw_path, "wb") as out_f:
            magic = cls._read_exact(in_f, len(cls.MAGIC_STREAM))
            if magic != cls.MAGIC_STREAM:
                raise ValueError("Invalid KolmoX Video Stream container")

            header_bytes = cls._read_exact(in_f, 16)
            if len(header_bytes) < 16:
                raise ValueError("Corrupted KolmoX header")
            width, height, fps, total_frames = struct.unpack(">IIII", header_bytes)

            restored_frames_count = 0
            while restored_frames_count < total_frames:
                chunk_len_bytes = cls._read_exact(in_f, 4)
                if len(chunk_len_bytes) < 4:
                    break
                chunk_len = struct.unpack(">I", chunk_len_bytes)[0]
                comp_chunk = cls._read_exact(in_f, chunk_len)
                if len(comp_chunk) < chunk_len:
                    break

                frames = pipeline.decompress_video_frames(comp_chunk)
                for f in frames:
                    out_f.write(f)

                restored_frames_count += len(frames)
                if progress_cb:
                    progress_cb(len(frames), total_frames)

        return {
            "total_frames": restored_frames_count,
            "width": width,
            "height": height,
            "fps": fps
        }