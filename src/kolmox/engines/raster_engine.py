"""
KolmoX - 2D Raster & Video Pre-Processing Engine
"""
import struct
from typing import Tuple
import numpy as np


class RasterEngine:
    MAGIC_HEADER = b"KMXR"

    @staticmethod
    def filter_2d_plane(plane: np.ndarray) -> bytes:
        # Encoding has no sequential dependency (left/up always read the
        # original plane, never the filtered output), so it vectorizes cleanly.
        plane_i32 = plane.astype(np.int32)
        left = np.zeros_like(plane_i32)
        left[:, 1:] = plane_i32[:, :-1]
        up = np.zeros_like(plane_i32)
        up[1:, :] = plane_i32[:-1, :]
        filtered = (plane_i32 - (left // 2 + up // 2)) % 256
        return filtered.astype(np.uint8).tobytes()

    @staticmethod
    def unfilter_2d_plane(data: bytes, height: int, width: int) -> np.ndarray:
        # Each pixel depends on the already-reconstructed left/up neighbors,
        # so unlike filter_2d_plane this can't be vectorized in NumPy; a C
        # extension (like fast_transforms.c) is the path to speed this up.
        filtered = np.frombuffer(data, dtype=np.uint8).reshape((height, width))
        plane = np.zeros((height, width), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                left = int(plane[y, x - 1]) if x > 0 else 0
                up = int(plane[y - 1, x]) if y > 0 else 0
                plane[y, x] = (int(filtered[y, x]) + (left // 2 + up // 2)) % 256
        return plane

    @classmethod
    def compress_rgb(cls, raw_rgb: bytes, width: int, height: int, channels: int = 3) -> bytes:
        total = width * height
        arr = np.frombuffer(raw_rgb[: total * channels], dtype=np.uint8).reshape((height, width, channels))
        buf = bytearray()
        for c in range(channels):
            buf.extend(cls.filter_2d_plane(arr[:, :, c]))
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
            rec[:, :, i] = cls.unfilter_2d_plane(payload[off : off + pl_size], h, w)
            off += pl_size
        return rec.tobytes()

    @classmethod
    def transform_bmp(cls, raw_data: bytes) -> Tuple[bytes, bytes]:
        """
        Parses a standard uncompressed BMP (BITMAPFILEHEADER + 40-byte
        BITMAPINFOHEADER, 24 or 32 bpp, BI_RGB, no color table) and runs the
        2D spatial-delta filter on the pixel data. Anything outside this
        common case raises ValueError so the caller falls back to plain Zstd.
        """
        if len(raw_data) < 54 or raw_data[:2] != b"BM":
            raise ValueError("Not a BMP file")

        (
            _bm,
            _file_size,
            _reserved1,
            _reserved2,
            pixel_offset,
        ) = struct.unpack("<2sIHHI", raw_data[:14])

        info_header_size = struct.unpack("<I", raw_data[14:18])[0]
        if info_header_size != 40:
            raise ValueError(f"Unsupported BITMAPINFOHEADER size {info_header_size}")

        width, height_signed, planes, bpp, compression = struct.unpack(
            "<iiHHI", raw_data[18:34]
        )
        if compression != 0:
            raise ValueError("Only uncompressed BI_RGB BMP is supported")
        if bpp not in (24, 32):
            raise ValueError(f"Unsupported bit depth {bpp}")
        if pixel_offset != 14 + info_header_size:
            raise ValueError("BMP has a color table/gap this engine does not support")
        if width <= 0 or height_signed == 0:
            raise ValueError("Invalid BMP dimensions")

        channels = bpp // 8
        height = abs(height_signed)
        row_size = width * channels
        padded_row_size = (row_size + 3) // 4 * 4
        row_padding = padded_row_size - row_size
        expected_pixel_bytes = padded_row_size * height

        raw_header = raw_data[:pixel_offset]
        pixel_data = raw_data[pixel_offset:]
        if len(pixel_data) < expected_pixel_bytes:
            raise ValueError("Truncated BMP pixel data")

        trailing = pixel_data[expected_pixel_bytes:]
        packed_rows = pixel_data[:expected_pixel_bytes]

        if row_padding > 0:
            padded_arr = np.frombuffer(packed_rows, dtype=np.uint8).reshape(
                (height, padded_row_size)
            )
            tight_pixels = np.ascontiguousarray(padded_arr[:, :row_size]).tobytes()
        else:
            tight_pixels = packed_rows

        filtered = cls.compress_rgb(tight_pixels, width, height, channels)

        aux = (
            struct.pack("<IH", len(raw_header), row_padding)
            + raw_header
            + trailing
        )
        return filtered, aux

    @classmethod
    def inverse_bmp(cls, primary: bytes, aux: bytes) -> bytes:
        header_len, row_padding = struct.unpack_from("<IH", aux, 0)
        raw_header = aux[6 : 6 + header_len]
        trailing = aux[6 + header_len :]

        tight_pixels = cls.decompress_rgb(primary)
        _magic, width, height, channels = struct.unpack(">4sIII", primary[:16])

        if row_padding > 0:
            row_size = width * channels
            tight_arr = np.frombuffer(tight_pixels, dtype=np.uint8).reshape(
                (height, row_size)
            )
            padded_arr = np.zeros((height, row_size + row_padding), dtype=np.uint8)
            padded_arr[:, :row_size] = tight_arr
            pixel_bytes = padded_arr.tobytes()
        else:
            pixel_bytes = tight_pixels

        return raw_header + pixel_bytes + trailing