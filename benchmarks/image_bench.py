import gzip
import numpy as np
import zstandard as zstd
from rich.console import Console
from rich.table import Table
from kolmox.engines.raster_engine import RasterEngine

console = Console()
width, height, channels = 512, 512, 3

# Creazione griglia 2D corretta (shape: 512, 512)
y, x = np.mgrid[:height, :width]
r = (np.sin(x / 16.0) * 120 + 128).astype(np.uint8)
g = (np.cos(y / 16.0) * 120 + 128).astype(np.uint8)
b = ((x + y) % 256).astype(np.uint8)
raw = np.stack([r, g, b], axis=-1).tobytes()

ctx = zstd.ZstdCompressor(level=19)
gz = gzip.compress(raw, 9)
zs = ctx.compress(raw)
kmx = ctx.compress(RasterEngine.compress_rgb(raw, width, height, channels))

t = Table(title="2D Raster RGB Frame Benchmark (512x512)")
t.add_column("Codec", style="cyan")
t.add_column("Original", justify="right")
t.add_column("Compressed", justify="right")
t.add_column("Ratio", justify="right", style="green")

exp = len(raw)
t.add_row("Gzip (Lvl 9)", f"{exp:,}", f"{len(gz):,}", f"{exp / len(gz):.2f}x")
t.add_row("Zstandard (Lvl 19)", f"{exp:,}", f"{len(zs):,}", f"{exp / len(zs):.2f}x")
t.add_row("KolmoX (Raster 2D)", f"{exp:,}", f"{len(kmx):,}", f"{exp / len(kmx):.2f}x")

console.print(t)