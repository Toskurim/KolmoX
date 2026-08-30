"""
KolmoX - High Performance Vectorized Temporal Video Engine
Computes spatial + temporal differential residuals at C-speed via NumPy.
"""
from typing import List, Tuple
import struct
import numpy as np


class VideoEngine:
    MAGIC_HEADER = b"KMXV1"

    @classmethod
    def compress_sequence(
        cls,
        frames: List[bytes],
        width: int,
        height: int,
        channels: int = 3
    ) -> bytes:
        if not frames:
            return b""

        num_frames = len(frames)
        frame_shape = (height, width, channels)
        
        # Converte tutti i frame in un blocco NumPy uint8
        np_frames = [np.frombuffer(f, dtype=np.uint8).reshape(frame_shape) for f in frames]
        
        # Header contenitore
        header = struct.pack(">5sIIIB", cls.MAGIC_HEADER, num_frames, width, height, channels)
        encoded_payload = bytearray(header)
        
        # Frame 0: Keyframe (I-Frame)
        encoded_payload.extend(np_frames[0].tobytes())
        
        # Frame successivi: Temporal XOR Delta vettorizzato
        for i in range(1, num_frames):
            delta = np.bitwise_xor(np_frames[i], np_frames[i - 1])
            encoded_payload.extend(delta.tobytes())
            
        return bytes(encoded_payload)

    @classmethod
    def decompress_sequence(cls, data: bytes) -> List[bytes]:
        magic, num_frames, width, height, channels = struct.unpack(">5sIIIB", data[:18])
        frame_size = width * height * channels
        frame_shape = (height, width, channels)
        
        offset = 18
        # Ripristino Keyframe
        prev_frame = np.frombuffer(data[offset : offset + frame_size], dtype=np.uint8).reshape(frame_shape).copy()
        offset += frame_size
        
        restored = [prev_frame.tobytes()]
        
        # Ripristino Delta cumulativo vettorizzato
        for _ in range(1, num_frames):
            delta = np.frombuffer(data[offset : offset + frame_size], dtype=np.uint8).reshape(frame_shape)
            offset += frame_size
            curr_frame = np.bitwise_xor(prev_frame, delta)
            restored.append(curr_frame.tobytes())
            prev_frame = curr_frame
            
        return restored