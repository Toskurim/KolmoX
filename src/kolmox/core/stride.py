"""
KolmoX - Stride & Columnar Demuxer
Detects record intervals (strides) and transposes interleaved data into smooth homogeneous streams.
"""

from typing import Tuple, Optional
import numpy as np


class StrideEngine:
    @staticmethod
    def detect_stride(data: bytes, max_stride: int = 64) -> Optional[int]:
        """
        Uses autocorrelation to find if the stream has a recurring record structure.
        """
        if len(data) < max_stride * 4:
            return None

        arr = np.frombuffer(data[:4096], dtype=np.uint8).astype(np.float64)
        norm = arr - np.mean(arr)
        autocorr = np.correlate(norm, norm, mode="full")[len(norm)-1:]

        # Look for sharp periodic correlation peaks
        for s in [16, 8, 4, 12, 24, 32]:
            if s < len(autocorr) and autocorr[s] > (autocorr[0] * 0.35):
                return s

        return None

    @staticmethod
    def transpose(data: bytes, stride: int) -> bytes:
        """
        Interleaved [A0, B0, C0, A1, B1, C1] -> Columnar [A0, A1, B0, B1, C0, C1]
        """
        num_records = len(data) // stride
        rem = len(data) % stride
        
        arr = np.frombuffer(data[:num_records * stride], dtype=np.uint8).reshape((num_records, stride))
        transposed = arr.T.tobytes()
        
        if rem > 0:
            return transposed + data[num_records * stride:]
        return transposed

    @staticmethod
    def untranspose(data: bytes, stride: int, original_len: int) -> bytes:
        """
        Restores Columnar back to Interleaved structure bit-by-bit.
        """
        num_records = original_len // stride
        rem = original_len % stride
        stride_bytes = num_records * stride

        arr_t = np.frombuffer(data[:stride_bytes], dtype=np.uint8).reshape((stride, num_records))
        untransposed = arr_t.T.tobytes()

        if rem > 0:
            return untransposed + data[stride_bytes:]
        return untransposed
