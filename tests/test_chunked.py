"""
Unit tests for KolmoX Parallel Chunked Pipeline Engine (Phase 2)
"""

import os
import pytest
from pathlib import Path
from kolmox.core.chunked import ChunkedPipelineEngine


def test_parallel_chunked_roundtrip_bit_exact(tmp_path: Path):
    # Create synthetic multi-block payload (> 2.5 MB with 512 KB chunk size to test multi-process)
    raw_payload = b"".join(f"RECORD_{i:08d},VALUE={i * 3.14159:.4f},DATA=KOLMOX_STREAM_PAYLOAD\n".encode("utf-8") for i in range(45000))
    
    in_file = tmp_path / "large_dataset.raw"
    comp_file = tmp_path / "large_dataset.kmx2"
    restored_file = tmp_path / "large_dataset_restored.raw"

    in_file.write_bytes(raw_payload)

    # Compress with 512KB chunk size to force multiple parallel chunks
    orig_size, comp_size = ChunkedPipelineEngine.compress_large_file(
        str(in_file),
        str(comp_file),
        chunk_size=512 * 1024,
        level=10,
        max_workers=4
    )

    assert comp_size > 0
    assert comp_file.exists()

    # Decompress in parallel
    restored_len = ChunkedPipelineEngine.decompress_large_file(
        str(comp_file),
        str(restored_file),
        max_workers=4
    )

    assert restored_len == orig_size
    assert restored_file.read_bytes() == raw_payload
