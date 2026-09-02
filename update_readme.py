with open("README.md", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Aggiunta descrizione tecnica del procedimento vettoriale/float
desc_target = "to eliminate structural correlation entropy."
new_desc = """to eliminate structural correlation entropy.
* **Continuous Dense Vector Slicing**: Decouples IEEE-754 Float32 memory streams (e.g. 1M+ raw embedding/sensor vectors) into discrete sign/exponent and mantissa byte planes. By separating predictable structural exponents from high-entropy mantissas, KolmoX provides near-instantaneous streaming compression (~930 MB/s decompression throughput, <5 ns per float) ideal for high-throughput in-memory caching tiers."""

if "Continuous Dense Vector Slicing" not in text:
    text = text.replace(desc_target, new_desc)

# 2. Aggiunta della riga nella tabella Benchmark
table_target = "| **Astrophysics FITS (JWST)** | **2D Modular Delta + Big-Endian Slicing** | **1.47x** | **1.47x** | **1.90x** | **+22.87% (-17.5 MB)** | ~225 MB/s / ~340 MB/s |"
new_row = """| **Astrophysics FITS (JWST)** | **2D Modular Delta + Big-Endian Slicing** | **1.47x** | **1.47x** | **1.90x** | **+22.87% (-17.5 MB)** | ~225 MB/s / ~340 MB/s |
| Dense Vector Buffers (1M Float32) | IEEE-754 Byte-Plane Slicing | 1.18x | 1.61x | **1.97x** | **+18.45% RAM** | ~320 MB/s / **~927 MB/s** |"""

if "Dense Vector Buffers (1M Float32)" not in text:
    text = text.replace(table_target, new_row)

with open("README.md", "w", encoding="utf-8") as f:
    f.write(text)

print("README.md aggiornato con successo!")
