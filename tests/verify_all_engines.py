"""
KolmoX - Comprehensive End-to-End Suite Validator
Validates bit-exact roundtrips across all multimodal engines and pipeline paths.
"""
import numpy as np
from rich.console import Console
from rich.table import Table

from kolmox.core.pipeline import KolmoXPipeline
from kolmox.engines.raster_engine import RasterEngine
from kolmox.engines.video_engine import VideoEngine

console = Console()
pipeline = KolmoXPipeline()
results = []


def run_test(name: str, passed: bool, orig_bytes: int, comp_bytes: int):
    ratio = orig_bytes / comp_bytes if comp_bytes > 0 else 1.0
    results.append({
        "Engine / Mode": name,
        "Status": "[bold green]PASS (Bit-Exact)[/bold green]" if passed else "[bold red]FAIL[/bold red]",
        "Original": f"{orig_bytes:,} B",
        "Compressed": f"{comp_bytes:,} B",
        "Ratio": f"{ratio:.2f}x"
    })


# 1. Industrial Telemetry / CSV Engine (Text Columnar)
csv_content = "timestamp,temp,pressure,flow_rate\n" + "\n".join(
    f"2026-08-29T12:00:{i%60:02d}.000Z,{20.0 + (i % 5) * 0.1:.2f},{101.3 + (i % 3) * 0.05:.2f},{45.0 + (i % 10) * 0.5:.2f}"
    for i in range(1000)
)
csv_raw = csv_content.encode("utf-8")
csv_comp = pipeline.compress(csv_raw)
csv_restored = pipeline.decompress(csv_comp)
run_test("Industrial Telemetry (.csv)", csv_restored == csv_raw, len(csv_raw), len(csv_comp))

# 2. Binary Stride Packets (Sensors & IoT)
bin_data = bytearray()
for i in range(2000):
    bin_data.extend(int(i % 256).to_bytes(1, "big"))
    bin_data.extend(int(50 + (i % 10)).to_bytes(2, "big"))
    bin_data.extend(int(1000 + (i % 5)).to_bytes(4, "big"))
bin_raw = bytes(bin_data)
bin_comp = pipeline.compress(bin_raw)
bin_restored = pipeline.decompress(bin_comp)
run_test("Binary Stride Packets (.bin)", bin_restored == bin_raw, len(bin_raw), len(bin_comp))

# 3. 2D Raster Frame (Paeth-based Residuals)
w, h, c = 256, 256, 3
y_grid, x_grid = np.mgrid[:h, :w]
r = (np.sin(x_grid / 8.0) * 120 + 128).astype(np.uint8)
g = (np.cos(y_grid / 8.0) * 120 + 128).astype(np.uint8)
b = ((x_grid + y_grid) % 256).astype(np.uint8)
raster_raw = np.stack([r, g, b], axis=-1).tobytes()
raster_comp = pipeline.compress_bytes(raster_raw, format_hint="raster", width=w, height=h, channels=c)
raster_restored = pipeline.decompress_bytes(raster_comp)
run_test("2D Raster RGB Frame", raster_restored == raster_raw, len(raster_raw), len(raster_comp))

# 4. Multi-Frame RAW Video Stream (Temporal Delta + 2D)
num_frames = 10
frames = []
for t in range(num_frames):
    r_t = (np.sin((x_grid + t * 2) / 8.0) * 120 + 128).astype(np.uint8)
    g_t = (np.cos((y_grid + t) / 8.0) * 120 + 128).astype(np.uint8)
    b_t = ((x_grid + y_grid + t) % 256).astype(np.uint8)
    frames.append(np.stack([r_t, g_t, b_t], axis=-1).tobytes())
video_raw_len = sum(len(f) for f in frames)
video_comp = pipeline.compress_video_frames(frames, width=w, height=h, channels=c)
video_restored = pipeline.decompress_video_frames(video_comp)
video_exact = (len(frames) == len(video_restored)) and all(o == r for o, r in zip(frames, video_restored))
run_test("Temporal Video Stream (10 Frames)", video_exact, video_raw_len, len(video_comp))

# 5. Program Synthesis & XOR Residual (Deterministic Generator)
script_exact = "def generate():\n    return bytes([(10 + i * 3) % 256 for i in range(4000)])\n"
synth_raw = bytes([(10 + i * 3) % 256 if i % 100 != 0 else 0 for i in range(4000)])
synth_comp = pipeline.compress_with_script(synth_raw, script_exact)
synth_restored = pipeline.decompress_with_script(synth_comp)
run_test("Generative Synthesis XOR Delta", synth_restored == synth_raw, len(synth_raw), len(synth_comp))

# Summary Table
table = Table(title="KolmoX Complete Engine Verification & Bit-Exact Results")
table.add_column("Engine / Mode", style="cyan")
table.add_column("Verification", justify="center")
table.add_column("Original", justify="right")
table.add_column("Compressed", justify="right")
table.add_column("Ratio", justify="right", style="bold green")

for r in results:
    table.add_row(r["Engine / Mode"], r["Status"], r["Original"], r["Compressed"], r["Ratio"])

console.print(table)