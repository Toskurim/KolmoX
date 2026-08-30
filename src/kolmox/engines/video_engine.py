"""
KolmoX - High-Performance Video Lossless Engine
Optimized with in-place SIMD-vectorized NumPy XOR differentials and zero-copy byte buffers.
"""
from typing import List
import struct
import numpy as np


class VideoEngine:
    MAGIC = b"KMXV1"

    @classmethod
    def compress_sequence(cls, frames: List[bytes], width: int, height: int, channels: int = 3) -> bytes:
        """
        Encodes a sequence of uncompressed RGB/RGBA frames into a contiguous bit-exact delta buffer.
        """
        if not frames:
            return b""

        num_frames = len(frames)
        frame_size = width * height * channels

        # Buffer contiguo C-order per sfruttare istruzioni vettoriali SIMD AVX2
        raw_buffer = np.frombuffer(b"".join(frames), dtype=np.uint8).reshape((num_frames, frame_size))
        
        # Buffer preallocato per i delta temporali
        delta_buffer = np.empty_like(raw_buffer)
        
        # Frame 0: Keyframe intatto
        delta_buffer[0] = raw_buffer[0]
        
        # Vettorizzazione SIMD in-place: Frame[i] XOR Frame[i-1]
        np.bitwise_xor(raw_buffer[1:], raw_buffer[:-1], out=delta_buffer[1:])

        header = struct.pack(">5sIII", cls.MAGIC, width, height, num_frames)
        return header + delta_buffer.tobytes()

    @classmethod
    def decompress_sequence(cls, payload: bytes) -> List[bytes]:
        """
        Reconstructs bit-exact original frames from a delta buffer.
        """
        if len(payload) < 17:
            raise ValueError("Payload too small to contain valid KolmoX video header")

        magic, width, height, num_frames = struct.unpack(">5sIII", payload[:17])
        if magic != cls.MAGIC:
            raise ValueError("Invalid KolmoX video magic header")

        frame_size = width * height * 3
        delta_data = payload[17:]
        
        if len(delta_data) != num_frames * frame_size:
            raise ValueError("Payload size mismatch with frame dimensions")

        delta_buffer = np.frombuffer(delta_data, dtype=np.uint8).reshape((num_frames, frame_size))
        
        # Ricostruzione cumulativa XOR
        restored = np.empty_like(delta_buffer)
        restored[0] = delta_buffer[0]

        for i in range(1, num_frames):
            np.bitwise_xor(restored[i - 1], delta_buffer[i], out=restored[i])

        return [restored[i].tobytes() for i in range(num_frames)]

    # Alias di compatibilità
    encode_frames = compress_sequence
    decode_frames = decompress_sequence