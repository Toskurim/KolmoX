"""
KolmoX - Hardware-Aware Vectorized Temporal Video Engine
Computes spatial + temporal differential residuals in parallel via NumPy.
"""
from typing import List
import struct
import numpy as np
from concurrent.futures import ThreadPoolExecutor


class VideoEngine:
    MAGIC_HEADER = b"KMXV1"

    @classmethod
    def _compute_delta_pair(cls, curr: np.ndarray, prev: np.ndarray) -> bytes:
        return np.bitwise_xor(curr, prev).tobytes()

    @classmethod
    def compress_sequence(
        cls,
        frames: List[bytes],
        width: int,
        height: int,
        channels: int = 3,
        workers: int = 4
    ) -> bytes:
        if not frames:
            return b""

        num_frames = len(frames)
        frame_shape = (height, width, channels)
        
        np_frames = [np.frombuffer(f, dtype=np.uint8).reshape(frame_shape) for f in frames]
        
        header = struct.pack(">5sIIIB", cls.MAGIC_HEADER, num_frames, width, height, channels)
        encoded_payload = bytearray(header)
        encoded_payload.extend(np_frames[0].tobytes())

        if num_frames > 1:
            # Calcolo parallelo dei residui XOR
            pairs = [(np_frames[i], np_frames[i - 1]) for i in range(1, num_frames)]
            with ThreadPoolExecutor(max_workers=min(workers, len(pairs))) as executor:
                deltas = list(executor.map(lambda p: cls._compute_delta_pair(p[0], p[1]), pairs))
            
            for d in deltas:
                encoded_payload.extend(d)
            
        return bytes(encoded_payload)

    @classmethod
    def decompress_sequence(cls, data: bytes) -> List[bytes]:
        magic, num_frames, width, height, channels = struct.unpack(">5sIIIB", data[:18])
        frame_size = width * height * channels
        frame_shape = (height, width, channels)
        
        offset = 18
        prev_frame = np.frombuffer(data[offset : offset + frame_size], dtype=np.uint8).reshape(frame_shape).copy()
        offset += frame_size
        
        restored = [prev_frame.tobytes()]
        
        for _ in range(1, num_frames):
            delta = np.frombuffer(data[offset : offset + frame_size], dtype=np.uint8).reshape(frame_shape)
            offset += frame_size
            curr_frame = np.bitwise_xor(prev_frame, delta)
            restored.append(curr_frame.tobytes())
            prev_frame = curr_frame
            
        return restored