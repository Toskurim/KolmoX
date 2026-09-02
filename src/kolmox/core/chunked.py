"""
KolmoX - Parallel Chunked Processing Engine (Phase 2)
Handles high-throughput multi-core compression for large datasets.
"""

import concurrent.futures
import os
import struct
import zlib
from typing import List, Tuple
from kolmox.core.pipeline import KolmoXPipeline

# Magic header for KolmoX Chunked Container V2: "KMX2"
CHUNKED_MAGIC = b"KMX2"
DEFAULT_CHUNK_SIZE = 16 * 1024 * 1024  # 16 MB per block


def _compress_chunk_worker(args: Tuple[bytes, int]) -> Tuple[bytes, int, int]:
    raw_chunk, level = args
    crc32_val = zlib.crc32(raw_chunk)
    pipeline = KolmoXPipeline(compression_level=level)
    compressed = pipeline.compress_bytes(raw_chunk)
    return compressed, len(raw_chunk), crc32_val


def _decompress_chunk_worker(compressed_chunk: bytes) -> bytes:
    pipeline = KolmoXPipeline()
    return pipeline.decompress_bytes(compressed_chunk)


class ChunkedPipelineEngine:
    @staticmethod
    def compress_large_file(
        input_path: str,
        output_path: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        level: int = 19,
        max_workers: int = None
    ) -> Tuple[int, int]:
        file_size = os.path.getsize(input_path)
        if max_workers is None:
            max_workers = min(os.cpu_count() or 4, 16)

        chunks: List[bytes] = []
        with open(input_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                chunks.append(chunk)

        total_chunks = len(chunks)
        worker_args = [(c, level) for c in chunks]

        # Parallel compression over ProcessPool
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_compress_chunk_worker, worker_args))

        # Build Container Manifest V2:
        # [4B Magic: KMX2][4B ChunkCount]
        # Repeated per chunk: [4B CompressedLen][4B OrigLen][4B CRC32]
        # Followed by contiguous compressed payloads.
        header = bytearray(CHUNKED_MAGIC)
        header.extend(struct.pack(">I", total_chunks))

        for compressed_bytes, orig_len, crc_val in results:
            header.extend(struct.pack(">III", len(compressed_bytes), orig_len, crc_val))

        with open(output_path, "wb") as out_f:
            out_f.write(header)
            for compressed_bytes, _, _ in results:
                out_f.write(compressed_bytes)

        compressed_size = os.path.getsize(output_path)
        return file_size, compressed_size

    @staticmethod
    def decompress_large_file(
        input_path: str,
        output_path: str,
        max_workers: int = None
    ) -> int:
        if max_workers is None:
            max_workers = min(os.cpu_count() or 4, 16)

        with open(input_path, "rb") as in_f:
            magic = in_f.read(4)
            if magic != CHUNKED_MAGIC:
                raise ValueError("Invalid KolmoX Chunked V2 container format.")

            total_chunks = struct.unpack(">I", in_f.read(4))[0]
            manifest: List[Tuple[int, int, int]] = []
            for _ in range(total_chunks):
                comp_len, orig_len, crc_val = struct.unpack(">III", in_f.read(12))
                manifest.append((comp_len, orig_len, crc_val))

            compressed_chunks: List[bytes] = []
            for comp_len, _, _ in manifest:
                compressed_chunks.append(in_f.read(comp_len))

        # Parallel decompression
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            restored_chunks = list(executor.map(_decompress_chunk_worker, compressed_chunks))

        # Integrity verification & sequential output write
        total_restored = 0
        with open(output_path, "wb") as out_f:
            for i, chunk_bytes in enumerate(restored_chunks):
                expected_len = manifest[i][1]
                expected_crc = manifest[i][2]
                actual_crc = zlib.crc32(chunk_bytes)

                if len(chunk_bytes) != expected_len or actual_crc != expected_crc:
                    raise ValueError(f"Integrity check failed on block {i} (CRC32 mismatch).")

                out_f.write(chunk_bytes)
                total_restored += len(chunk_bytes)

        return total_restored
