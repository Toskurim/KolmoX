"""
KolmoX - High-Throughput Asynchronous Video Stream Engine
Uses double-buffered threading to overlap frame extraction with multi-threaded compression.
"""
from typing import Optional, Callable
import os
import queue
import threading
import struct
import cv2
from kolmox.core.pipeline import KolmoXPipeline


class VideoStreamEngine:
    MAGIC_STREAM = b"KMXSTREAM1"

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

        cap = cv2.VideoCapture(input_video_path)
        if not cap.isOpened():
            raise ValueError(f"OpenCV could not open video: {input_video_path}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        total_file_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        target_frames = min(total_file_frames, max_frames) if max_frames > 0 else total_file_frames

        pipeline = KolmoXPipeline(compression_level=compression_level, threads=threads)
        frame_queue = queue.Queue(maxsize=2)

        def producer():
            read_count = 0
            while read_count < target_frames:
                to_read = min(chunk_frames, target_frames - read_count)
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
                read_count += len(chunk)
            cap.release()
            frame_queue.put(None)

        prod_thread = threading.Thread(target=producer, daemon=True)
        prod_thread.start()

        total_compressed_bytes = 0
        with open(output_kmxv_path, "wb") as out_f:
            out_f.write(cls.MAGIC_STREAM)
            out_f.write(struct.pack(">IIII", width, height, fps, target_frames))
            total_compressed_bytes += len(cls.MAGIC_STREAM) + 16

            processed = 0
            while True:
                chunk = frame_queue.get()
                if chunk is None:
                    break

                comp_chunk = pipeline.compress_video_frames(chunk, width=width, height=height, channels=3)
                out_f.write(struct.pack(">I", len(comp_chunk)))
                out_f.write(comp_chunk)

                total_compressed_bytes += 4 + len(comp_chunk)
                processed += len(chunk)
                if progress_cb:
                    progress_cb(len(chunk), target_frames)

        prod_thread.join()
        raw_bytes = target_frames * width * height * 3

        return {
            "total_frames": target_frames,
            "width": width,
            "height": height,
            "fps": fps,
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
            magic = in_f.read(len(cls.MAGIC_STREAM))
            if magic != cls.MAGIC_STREAM:
                raise ValueError("Invalid KolmoX Video Stream container")

            header_bytes = in_f.read(16)
            width, height, fps, total_frames = struct.unpack(">IIII", header_bytes)

            restored_frames_count = 0
            while restored_frames_count < total_frames:
                chunk_len_bytes = in_f.read(4)
                if not chunk_len_bytes or len(chunk_len_bytes) < 4:
                    break
                chunk_len = struct.unpack(">I", chunk_len_bytes)[0]
                comp_chunk = in_f.read(chunk_len)

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