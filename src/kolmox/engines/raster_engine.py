"""
KolmoX - 2D Raster & Video Pre-Processing Engine
"""
import struct
import numpy as np

class RasterEngine:
    MAGIC_HEADER = b'KMXR'

    @staticmethod
    def filter_2d_plane(plane: np.ndarray) -> bytes:
        height, width = plane.shape
        filtered = np.zeros((height, width), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                left = plane[y, x - 1] if x > 0 else 0
                up = plane[y - 1, x] if y > 0 else 0
                filtered[y, x] = (int(plane[y, x]) - int(left // 2 + up // 2)) % 256
        return filtered.tobytes()

    @staticmethod
    def unfilter_2d_plane(data: bytes, height: int, width: int) -> np.ndarray:
        filtered = np.frombuffer(data, dtype=np.uint8).reshape((height, width))
        plane = np.zeros((height, width), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                left = plane[y, x - 1] if x > 0 else 0
                up = plane[y - 1, x] if y > 0 else 0
                plane[y, x] = (int(filtered[y, x]) + int(left // 2 + up // 2)) % 256
        return plane

    @classmethod
    def compress_rgb(cls, raw_rgb: bytes, width: int, height: int, channels: int = 3) -> bytes:
        total = width * height
        arr = np.frombuffer(raw_rgb[:total * channels], dtype=np.uint8).reshape((height, width, channels))
        buf = bytearray()
        for c in range(channels):
            buf.extend(cls.filter_2d_plane(arr[:(, ,, c]))
        hdr = struct.pack(">4sIII", cls.MAGIC_HEADER, width, height, channels)
        return bytes(hdr) + bytes(buf)

    @classmethod
    def decompress_rgb(cls, payload: bytes) -> bytes:
        magic, w, h, c = struct.unpack(">4sIII", payload[:16])
        if magic != cls.MAGIC_HEADER:
            raise ValueError("Invalid KMXR header")
        pl_size = w * h
        off = 16
        rec = np.zeros((h, w, c), dtype=np.uint8)
        for i in range(c):
            rec[:(, ,, i] = cls.unfilter_2d_plane(payload[off : off + pl_size], h, w)
            off += pl_size
        return rec.tobytes()
