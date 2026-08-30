"""
KolmoX - Full Video Stream Streaming Compressor & Benchmark
Bounded-memory streaming compression with disk target and max_frames limit.
"""
import sys
import os
import time
import struct
import cv2
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table

from kolmox.core.pipeline import KolmoXPipeline

console = Console()


def compress_full_video(
    video_path: str,
    output_kmxv: str = "output_full.kmxv",
    chunk_frames: int = 120,
    max_frames: int = 0
):
    if not os.path.exists(video_path):
        console.print(f"[bold red]Errore: File non trovato: {video_path}[/bold red]")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        console.print("[bold red]Impossibile aprire il video.[/bold red]")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_file_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    frames_to_process = min(total_file_frames, max_frames) if max_frames > 0 else total_file_frames
    bytes_per_frame = width * height * 3
    total_raw_bytes = frames_to_process * bytes_per_frame

    console.print(f"[bold cyan]Input Video:[/] {os.path.basename(video_path)}")
    console.print(f"[dim]Risoluzione: {width}x{height} | {fps:.2f} FPS | Frame target: {frames_to_process:,} / {total_file_frames:,}[/dim]")
    console.print(f"[dim]Volume RAW RGB totale stimato: {total_raw_bytes / (1024**3):.2f} GB[/dim]")
    console.print(f"[dim]Destinazione output: {output_kmxv}[/dim]\n")

    pipeline = KolmoXPipeline(compression_level=7, threads=-1)

    t0 = time.perf_counter()
    total_compressed_bytes = 0
    frames_done = 0

    with open(output_kmxv, "wb") as out_f:
        # Container Header
        out_f.write(b"KMXSTREAM1")
        out_f.write(struct.pack(">IIII", width, height, int(fps), frames_to_process))

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("• {task.completed}/{task.total} frame"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[green]Compressione KolmoX...", total=frames_to_process)

            while frames_done < frames_to_process:
                to_read = min(chunk_frames, frames_to_process - frames_done)
                chunk_buffer = []
                for _ in range(to_read):
                    ret, bgr_frame = cap.read()
                    if not ret:
                        break
                    rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                    chunk_buffer.append(rgb_frame.tobytes())

                if not chunk_buffer:
                    break

                comp_chunk = pipeline.compress_video_frames(chunk_buffer, width=width, height=height, channels=3)
                out_f.write(struct.pack(">I", len(comp_chunk)))
                out_f.write(comp_chunk)

                total_compressed_bytes += 4 + len(comp_chunk)
                frames_done += len(chunk_buffer)
                progress.update(task, advance=len(chunk_buffer))

    cap.release()
    total_time = time.perf_counter() - t0

    ratio_raw = total_raw_bytes / total_compressed_bytes if total_compressed_bytes > 0 else 1.0
    throughput_mb_s = (total_raw_bytes / (1024 * 1024)) / total_time

    table = Table(title=f"Riepilogo Compressione KolmoX: {os.path.basename(video_path)}")
    table.add_column("Metrica", style="cyan")
    table.add_column("Valore", justify="right")

    table.add_row("Frame Elaborati", f"{frames_done:,} frame ({width}x{height})")
    table.add_row("Volume RAW RGB Equivalente", f"{total_raw_bytes / (1024**3):.2f} GB ({total_raw_bytes:,} B)")
    table.add_row("File KolmoX Bit-Exact Generato", f"{total_compressed_bytes / (1024**3):.2f} GB ({total_compressed_bytes:,} B)")
    table.add_row("Compression Ratio (vs RAW)", f"[bold green]{ratio_raw:.2f}x[/bold green]")
    table.add_row("Tempo Totale Impiegato", f"{total_time:.2f} s ({total_time / 60:.2f} min)")
    table.add_row("Throughput Medio di Encoding", f"{throughput_mb_s:.2f} MB/s ({frames_done / total_time:.1f} FPS)")

    console.print("\n")
    console.print(table)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python benchmark_full_video_stream.py <video.mp4> [output.kmxv] [max_frames]")
    else:
        out_target = sys.argv[2] if len(sys.argv) > 2 else "output_full.kmxv"
        max_f = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        compress_full_video(sys.argv[1], output_kmxv=out_target, max_frames=max_f)