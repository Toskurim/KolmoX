"""
Unit tests for KolmoX Unified CLI and Rich Telemetry
"""

import subprocess
import sys
from pathlib import Path


def test_cli_compress_decompress_roundtrip(tmp_path: Path):
    in_file = tmp_path / "telemetry_input.csv"
    data = (
        "id,timestamp,val_x,val_y\n"
        + "\n".join(f"{i},170000000{i},{i*1.5:.2f},{i*2.5:.2f}" for i in range(50))
    )
    in_file.write_text(data, encoding="utf-8")

    kmx_file = tmp_path / "telemetry.kmx"
    restored_file = tmp_path / "telemetry_restored.csv"

    # Test compression with --quiet flag
    cmd_comp = [sys.executable, "-m", "src.kolmox.cli.main", "compress", str(in_file), str(kmx_file), "-q"]
    res_comp = subprocess.run(cmd_comp, capture_output=True, text=True)
    assert res_comp.returncode == 0
    assert kmx_file.exists()
    assert kmx_file.stat().st_size > 0

    # Test decompression with --quiet flag
    cmd_decomp = [sys.executable, "-m", "src.kolmox.cli.main", "decompress", str(kmx_file), str(restored_file), "-q"]
    res_decomp = subprocess.run(cmd_decomp, capture_output=True, text=True)
    assert res_decomp.returncode == 0
    assert restored_file.exists()

    # Bit-exact check
    assert restored_file.read_bytes() == in_file.read_bytes()
