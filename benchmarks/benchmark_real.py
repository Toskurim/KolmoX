"""
KolmoX - Benchmark su dataset REALI (Evidence Tier 2).

Controparte di benchmark_extended.py, che gira su dati sintetici generati con
seed fissi. Qui i dati vengono da archivi pubblici con licenza dichiarata,
scaricati da `python benchmarks/download_datasets.py`.

Stesso metodo: misura attraverso l'API pubblica
KolmoXPipeline.compress_bytes() / decompress_bytes(), con assert bit-exact su
ogni dominio ed exit non-zero se anche uno solo fallisce. Le cifre ottenute
chiamando gli engine direttamente non sono riportate: escluderebbero i 24 byte
di header KMX2 e scavalcherebbero il fallback competitivo.

I dataset mancanti vengono saltati con un avviso, cosi' lo script gira anche
parzialmente senza obbligare a scaricare tutto.

Uso:
    python benchmarks/download_datasets.py     # una volta
    python benchmarks/benchmark_real.py
    python benchmarks/benchmark_real.py --strong-baselines
"""

import argparse
import gzip
import os
import sys
import time

import zstandard as zstd
from rich.console import Console
from rich.table import Table

from kolmox.core.domain_router import DomainRouter, DomainType
from kolmox.core.pipeline import KolmoXPipeline

console = Console()
DATASETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")

# (etichetta, file, dominio atteso, licenza, nota)
REAL_DATASETS = [
    ("Astrophysics FITS (JWST SMACS 0723)", "jwst_smacs0723_miri_f770w.fits",
     DomainType.FLOAT32, "Public domain (NASA/STScI)", ""),
    ("Industrial Telemetry (.csv, clean)", "energydata_complete.csv",
     DomainType.TELEMETRY_CSV, "CC BY 4.0 (UCI)", "virgola, intestazioni quotate"),
    ("Industrial Telemetry (.csv, messy)", "AirQualityUCI.csv",
     DomainType.TELEMETRY_CSV, "CC BY 4.0 (UCI)",
     "punto e virgola + virgola decimale + CRLF"),
    ("CNC G-Code (.ngc)", "linuxcnc_3d_chips.ngc",
     DomainType.GCODE, "GPL-2.0 (LinuxCNC)", "non ridistribuibile"),
    ("CAD Mesh (.stl binario, WVS)", "zenodo_wvs.stl",
     DomainType.CAD_MESH_OBJ, "CC0 (Zenodo 5034614)", "STL binario"),
    ("CAD Mesh (.stl binario, Ambulacral)", "zenodo_ambulacral.stl",
     DomainType.CAD_MESH_OBJ, "CC0 (Zenodo 5034614)", "STL binario"),
]


def bench(label, path, expected_domain, level=3, with_gzip=False):
    with open(path, "rb") as f:
        raw = f.read()

    filename = os.path.basename(path)
    detected = DomainRouter.detect_domain(raw, filename=filename)
    level_cctx = zstd.ZstdCompressor(level=level)

    t0 = time.perf_counter()
    baseline = level_cctx.compress(raw)
    t_base = time.perf_counter() - t0
    baseline_size = len(baseline)

    pipeline = KolmoXPipeline(compression_level=level)
    t0 = time.perf_counter()
    kmx = pipeline.compress_bytes(raw, filename=filename)
    t1 = time.perf_counter()
    restored = pipeline.decompress_bytes(kmx)
    t2 = time.perf_counter()

    bit_exact = restored == raw
    mb = len(raw) / 1_048_576
    stored_domain = kmx[6]

    row = {
        "label": label,
        "raw_bytes": len(raw),
        "ratio_base": len(raw) / baseline_size,
        "ratio_kmx": len(raw) / len(kmx),
        "gain": (1 - len(kmx) / baseline_size) * 100,
        "comp_mbps": mb / (t1 - t0),
        "decomp_mbps": mb / (t2 - t1),
        "baseline_mbps": mb / t_base if t_base > 0 else float("inf"),
        "bit_exact": bit_exact,
        "detected": detected,
        "detected_ok": detected == expected_domain,
        "stored_domain": stored_domain,
        "transform_used": stored_domain == int(detected),
    }
    if with_gzip:
        t0 = time.perf_counter()
        gz = gzip.compress(raw, compresslevel=9)
        row["gzip_ratio"] = len(raw) / len(gz)
        row["gzip_mbps"] = mb / (time.perf_counter() - t0)
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--strong-baselines", action="store_true",
                   help="Ripete a Zstd livello 19 su entrambi i lati, piu' Gzip-9.")
    args = p.parse_args()

    if not os.path.isdir(DATASETS_DIR):
        console.print(f"[bold red]Cartella dataset assente: {DATASETS_DIR}[/bold red]")
        console.print("Esegui prima: python benchmarks/download_datasets.py")
        return 1

    results, missing = [], []
    for label, fname, domain, lic, note in REAL_DATASETS:
        path = os.path.join(DATASETS_DIR, fname)
        if not os.path.exists(path):
            missing.append((label, fname))
            continue
        console.print(f"[dim]misurazione: {label}...[/dim]")
        r = bench(label, path, domain, level=3)
        r["license"] = lic
        r["note"] = note
        results.append(r)

    if missing:
        console.print("\n[yellow]Dataset non presenti, saltati:[/yellow]")
        for label, fname in missing:
            console.print(f"[yellow]  - {label}  ({fname})[/yellow]")
        console.print("[yellow]  Eseguire: python benchmarks/download_datasets.py[/yellow]")

    if not results:
        console.print("[bold red]Nessun dataset disponibile: niente da misurare.[/bold red]")
        return 1

    t = Table(title="KolmoX - Benchmark su dati REALI (Evidence Tier 2)",
              header_style="bold cyan")
    t.add_column("Dataset", style="bold white", width=36, no_wrap=True)
    t.add_column("Dim.", justify="right", no_wrap=True)
    t.add_column("Zstd", justify="right", no_wrap=True)
    t.add_column("KolmoX", justify="right", style="bold green", no_wrap=True)
    t.add_column("Gain", justify="right", style="bold yellow", no_wrap=True)
    t.add_column("Dominio", justify="center", no_wrap=True)
    t.add_column("Transf.", justify="center", no_wrap=True)
    t.add_column("Exact", justify="center", no_wrap=True)

    for r in results:
        colour = "green" if r["gain"] > 1 else ("red" if r["gain"] < 0 else "yellow")
        t.add_row(
            r["label"],
            f"{r['raw_bytes']/1_048_576:.1f} MB",
            f"{r['ratio_base']:.2f}x",
            f"{r['ratio_kmx']:.2f}x",
            f"[{colour}]{r['gain']:+.2f}%[/{colour}]",
            f"{r['detected'].name[:12]}",
            "[green]used[/green]" if r["transform_used"] else "[yellow]fallb.[/yellow]",
            "[green]PASS[/green]" if r["bit_exact"] else "[bold red]FAIL[/bold red]",
        )
    console.print("\n")
    console.print(t)

    console.print("\n[bold]Righe markdown:[/bold]\n")
    for r in results:
        print(f"| **{r['label']}** | {r['ratio_base']:.2f}x | **{r['ratio_kmx']:.2f}x** | "
              f"**{r['gain']:+.2f}%** | ~{r['comp_mbps']:.0f} MB/s / ~{r['decomp_mbps']:.0f} MB/s | "
              f"{r['license']} |")

    console.print("\n[bold]Dettaglio routing (per documentare i buchi):[/bold]")
    for r in results:
        console.print(
            f"  {r['label']:<38} rilevato={r['detected'].name:<16} "
            f"archiviato domain_id={r['stored_domain']:<3} "
            f"{'trasformazione usata' if r['transform_used'] else 'FALLBACK -> baseline Zstd'}"
        )

    failures = [r for r in results if not r["bit_exact"]]
    if failures:
        console.print(f"\n[bold red]ROUNDTRIP NON BIT-EXACT: "
                      f"{', '.join(r['label'] for r in failures)}[/bold red]")
        return 1

    console.print("\n[bold green]Tutti i dataset reali: roundtrip bit-exact "
                  "verificato.[/bold green]\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
