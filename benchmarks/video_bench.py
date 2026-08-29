"""
Benchmark: Raw Multi-Frame Video Stream (Temporal Delta + 2D Spatial)
"""
import gzip
import numpy as np
import zstandard as zstd
from rich.console import Console
from rich.table import Table
from kolmox.engines.video_engine import VideoEngine

console = Console()
width, height, channels = 256, 256, 3
num_frames = 20

y, x = np.mgrid[:height, :width]
frames = []

# Simulazione sequenza video (movimento orizzontale e variazione armonica)
for t in range(num_frames):
    r = (np.sin((x + t * 4) / 16.0) * 120 + 128).astype(np.uint8)
    g = (np.cos((y + t * 2) / 16.0) * 120 + 128).astype(np.uint8)
    b = ((x + y + t) % 256).astype(np.uint8)
    frame_raw = np.stack([r, g, b], axis=-1).tobytes()
    frames.append(frame_raw)

full_raw_stream = b"".join(frames)
total_bytes = len(full_raw_stream)

# 1. Gzip Level 9
gz = gzip.compress(full_raw_stream, 9)

# 2. Zstandard Level 19
ctx = zstd.ZstdCompressor(level=19)
zs = ctx.compress(full_raw_stream)

# 3. KolmoX Video Engine + Zstandard
temporal_packed = VideoEngine.compress_sequence(frames, width, height, channels)
kmx = ctx.compress(temporal_packed)

t = Table(title=f"Multi-Frame RAW Video Stream Benchmark ({num_frames} frames @ 256x256 RGB)")
t.add_column("Codec", style="cyan")
t.add_column("Original", justify="right")
t.add_column("Compressed", justify="right")
t.add_column("Ratio", justify="right", style="green")

t.add_row("Gzip (Lvl 9)", f"{total_bytes:,}", f"{len(gz):,}", f"{total_bytes / len(gz):.2f}x")
t.add_row("Zstandard (Lvl 19)", f"{total_bytes:,}", f"{len(zs):,}", f"{total_bytes / len(zs):.2f}x")
t.add_row("KolmoX (Temporal + 2D)", f"{total_bytes:,}", f"{len(kmx):,}", f"{total_bytes / len(kmx):.2f}x")

console.print(t)