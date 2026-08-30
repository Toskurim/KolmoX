# KolmoX ⚡

[![CI Status](https://github.com/toskurim/KolmoX/workflows/CI/badge.svg)](https://github.com/toskurim/KolmoX/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)

**KolmoX** è un framework di compressione ad alte prestazioni e **100% bit-exact**, progettato per superare i limiti dei motori entropici generici (come Gzip e Zstandard standard) combinando **precondizionatori di dominio strutturali**, **trasformazioni geometriche/colonnari**, **decompressione hardware-accelerata (CUDA/NVDEC)** e **sintesi generica basata su modelli**.

---

## 🚀 Caratteristiche Principali

- **Garanzia Bit-Exact al 100%:** Ricostruzione matematica perfetta e verificabile tramite hash crittografico (SHA-256) per ogni dominio trattato.
- **Precondizionamento Dominio-Specifico:**
  - **CAD & 3D Mesh Engine:** Separazione e planarizzazione delle coordinate di vertice `.obj` mantenendo l'ordinamento strict delle righe.
  - **Text & Telemetry Columnar Demuxer:** Riorganizzazione per colonne contigue di log industriali, CSV e flussi tabulari.
  - **Binary Stride Demuxer:** Rilevamento automatico dell'interleaving binario periodico tramite autocorrelazione.
  - **2D & Temporal Video Stream Engine:** Differenziali predittivi spaziali e temporali (Delta-XOR) con decodifica hardware NVDEC/CUDA per flussi video non compressi (fino a risoluzione 5K a 60 FPS).
- **Sintesi Generativa (LLM & Heuristic):** Generazione e applicazione di delta predittivi compatti su payload computazionalmente derivabili.
- **Pipeline Multi-Thread & Streaming:** Gestione a blocchi asincrona con buffer sicuri contro interruzioni su pipe e flussi di dati di grandi dimensioni.

---

## 📊 Benchmark Comparativi Reali

Tutti i test riportati certificano il ripristino matematico esatto dei dati (nessuna perdita di precisione):

| Dominio Dati | Pipeline / Formato | Gzip (Lvl 9) | Zstd (Lvl 19) | **KolmoX (Structural)** | Vantaggio vs Zstd |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Industrial Telemetry (`.csv`)** | Columnar Demux + Zstd | 3.93x | 19.65x | **40.20x** | **+104%** |
| **Binary Register Packets (`.bin`)** | Stride Autocorr + Demux | 2.65x | 4.83x | **55.53x** | **+1050% (11.5x)** |
| **Parametric 3D CAD Mesh (`.obj`)** | Ordered Vertex Transpose | 4.38x | 8.42x | **14.07x** | **+67%** |
| **2D Uncompressed Raster (RGB)** | 2D Spatial Delta | 2.10x | 4.30x | **89.08x** | **+1970%** |
| **5K Video Stream (5120x1440 60fps)** | CUDA / NVDEC + Delta-XOR | ~1.10x | ~1.15x | **3.15x – 6.56x** | **+170%** |

---

## 🛠️ Installazione

```bash
# Clona il repository
git clone https://github.com/toskurim/KolmoX.git
cd KolmoX

# Installa le dipendenze
pip install -r requirements.txt
pip install -e .
```

---

## 💻 Utilizzo da Riga di Comando (CLI)

### Compressione ed Estrazione Video Stream Lossless

KolmoX include un motore di streaming asincrono che sfrutta FFmpeg e l'accelerazione GPU (CUDA) per comprimere e ripristinare sequenze video RAW ad altissima risoluzione:

```bash
# Comprime uno stream video sfruttando NVDEC/CUDA
python -m src.kolmox.cli.main compress-video "input_video.mp4" "output_stream.kmxv" --max-frames 1000

# Decomprime il container ripristinando il flusso RAW bit-exact
python -m src.kolmox.cli.main decompress-video "output_stream.kmxv" "restored_stream.raw"
```

### Compressione File Generica e Pipeline Strutturata

```bash
# Compressione file generica
python -m src.kolmox.cli.main compress "dataset.csv" "dataset.kmx" -l 19

# Decompressione
python -m src.kolmox.cli.main decompress "dataset.kmx" "restored.csv"
```

---

## 🧪 Test Suite & Validazione

Esegui l'intera suite di test unitari con validazione bit-exact:

```bash
pytest tests/ -v
```

Esegui la suite di benchmark comparativi:

```bash
python benchmarks/real_world_bench.py
```

---

## 📄 Licenza

Distribuito sotto licenza **MIT**. Consulta il file [LICENSE](LICENSE) per ulteriori dettagli.
