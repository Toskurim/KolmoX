"""
KolmoX - Bit-Exact Lossless Verification Test
Validates that decompressed frames match original frames byte-for-byte via SHA-256.
"""
import sys
import hashlib
import cv2
from rich.console import Console
from rich.table import Table

from kolmox.core.pipeline import KolmoXPipeline

console = Console()


def verify_bit_exact(video_path: str, num_frames: int = 60):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        console.print(f"[bold red]Impossibile aprire: {video_path}[/bold red]")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    console.print(f"[cyan]Lettura di {num_frames} frame da:[/] {video_path}")
    raw_frames = []
    hasher_orig = hashlib.sha256()

    for _ in range(num_frames):
        ret, bgr = cap.read()
        if not ret:
            break
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        b = rgb.tobytes()
        raw_frames.append(b)
        hasher_orig.update(b)

    cap.release()
    original_sha256 = hasher_orig.hexdigest()
    console.print(f"[dim]SHA-256 Originale RAW :[/dim] [yellow]{original_sha256}[/yellow]")

    # Pipeline KolmoX: Compressione
    pipeline = KolmoXPipeline(compression_level=7, threads=-1)
    compressed = pipeline.compress_video_frames(raw_frames, width=width, height=height, channels=3)
    console.print(f"[dim]Dimensione compressa :[/dim] {len(compressed):,} byte")

    # Pipeline KolmoX: Decompressione
    restored_frames = pipeline.decompress_video_frames(compressed)

    # Calcolo SHA-256 Decompresso
    hasher_restored = hashlib.sha256()
    for f in restored_frames:
        hasher_restored.update(f)
    restored_sha256 = hasher_restored.hexdigest()
    console.print(f"[dim]SHA-256 Decompresso RAW:[/dim] [yellow]{restored_sha256}[/yellow]")

    # Confronto bit-exact
    is_identical = (original_sha256 == restored_sha256)

    table = Table(title="Certificazione Lossless KolmoX")
    table.add_column("Parametro", style="cyan")
    table.add_column("Esito", justify="right")

    table.add_row("Frame Verificati", f"{len(raw_frames)}")
    table.add_row("Volume RAW Convalidato", f"{(len(raw_frames) * width * height * 3) / (1024**2):.2f} MB")
    table.add_row("SHA-256 Match", "[bold green]100% IDENTICO (0 differenze)[/bold green]" if is_identical else "[bold red]FAIL[/bold red]")
    table.add_row("Integrità Bit-Exact", "[bold green]CERTIFICATA[/bold green]" if is_identical else "[bold red]CORROTTA[/bold red]")

    console.print("\n")
    console.print(table)


if __name__ == "__main__":
    v_path = sys.argv[1] if len(sys.argv) > 1 else "2026-05-17 07-49-37.mp4"
    verify_bit_exact(v_path, num_frames=120)