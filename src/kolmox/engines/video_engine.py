"""
KolmoX - Raw Video & Multi-Frame Temporal Engine
Implements spatial-temporal lossless compression for RGB/RAW frame sequences.
"""
import struct
import numpy as np
from kolmox.engines.raster_engine import RasterEngine


class VideoEngine:
    MAGIC_HEADER = b"KMXV"

    @classmethod
    def compress_sequence(cls, frames: list[bytes], width: int, height: int, channels: int = 3) -> bytes:
        if not frames:
            raise ValueError("Frame list cannot be empty")

        num_frames = len(frames)
        frame_size = width * height * channels
        header = struct.pack(">4sIIII", cls.MAGIC_HEADER, width, height, channels, num_frames)

        # I-Frame (primo frame compresso con il filtro spaziale 2D)
        i_frame_raw = frames[0][:frame_size]
        i_frame_filtered = RasterEngine.compress_rgb(i_frame_raw, width, height, channels)
        
        payload = bytearray(header)
        payload.extend(struct.pack(">I", len(i_frame_filtered)))
        payload.extend(i_frame_filtered)

        # P-Frames (differenza temporale pixel-by-pixel rispetto al frame precedente + filtro 2D)
        prev_arr = np.frombuffer(i_frame_raw, dtype=np.uint8).reshape((height, width, channels))

        for idx in range(1, num_frames):
            curr_raw = frames[idx][:frame_size]
            curr_arr = np.frombuffer(curr_raw, dtype=np.uint8).reshape((height, width, channels))

            # Temporal Residual (modulo 256)
            temporal_diff = (curr_arr.astype(np.int16) - prev_arr.astype(np.int16)) % 256
            diff_bytes = temporal_diff.astype(np.uint8).tobytes()

            # Applica Raster 2D sul residuo temporale per comprimere sia il moto che la variazione spaziale
            p_filtered = RasterEngine.compress_rgb(diff_bytes, width, height, channels)
            
            payload.extend(struct.pack(">I", len(p_filtered)))
            payload.extend(p_filtered)
            prev_arr = curr_arr

        return bytes(payload)

    @classmethod
    def decompress_sequence(cls, payload: bytes) -> list[bytes]:
        magic, width, height, channels, num_frames = struct.unpack(">4sIIII", payload[:20])
        if magic != cls.MAGIC_HEADER:
            raise ValueError("Invalid KMXV video header")

        offset = 20
        frames = []

        # Estrai I-Frame
        i_len = struct.unpack(">I", payload[offset : offset + 4])[0]
        offset += 4
        i_frame_data = payload[offset : offset + i_len]
        offset += i_len

        i_raw = RasterEngine.decompress_rgb(i_frame_data)
        frames.append(i_raw)
        prev_arr = np.frombuffer(i_raw, dtype=np.uint8).reshape((height, width, channels))

        # Ricostruisci P-Frames
        for _ in range(1, num_frames):
            p_len = struct.unpack(">I", payload[offset : offset + 4])[0]
            offset += 4
            p_frame_data = payload[offset : offset + p_len]
            offset += p_len

            diff_raw = RasterEngine.decompress_rgb(p_frame_data)
            diff_arr = np.frombuffer(diff_raw, dtype=np.uint8).reshape((height, width, channels))

            curr_arr = (prev_arr.astype(np.int16) + diff_arr.astype(np.int16)) % 256
            curr_raw = curr_arr.astype(np.uint8).tobytes()
            frames.append(curr_raw)
            prev_arr = curr_arr.astype(np.uint8)

        return frames