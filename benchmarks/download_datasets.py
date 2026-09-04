"""
KolmoX - Downloader dei dataset reali per l'Evidence Tier 2.

Scarica in benchmarks/datasets/ i dataset pubblici usati da benchmark_real.py.
Ogni voce del manifest dichiara URL, licenza, dimensione attesa, checksum
SHA-256 e, dove serve, i vincoli di ridistribuzione.

Garanzie:
  - Il checksum viene verificato DOPO ogni download. Se non combacia il file
    viene scartato e lo script esce con codice 1: mai proseguire in silenzio.
  - Un URL morto e' un errore esplicito, non un salto silenzioso.
  - Cio' che e' gia' presente e valido viene saltato (verifica via checksum).

Limite noto sulla ripresa dei download interrotti: funziona solo dove il
server supporta le richieste HTTP Range. MAST e GitHub le supportano, Zenodo
no (risponde 403 a una richiesta Range), quindi un download Zenodo interrotto
riparte da capo. Lo skip via checksum invece funziona ovunque, perche' opera
sul file completo.

Uso:
    python benchmarks/download_datasets.py            # scarica il mancante
    python benchmarks/download_datasets.py --verify   # solo verifica, nessun download
    python benchmarks/download_datasets.py --list     # mostra il manifest ed esce
"""

import argparse
import hashlib
import os
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional

DATASETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")
BUDGET_MB = 100          # tetto complessivo per il download di terzi
UA = {"User-Agent": "Mozilla/5.0 (KolmoX benchmark dataset fetcher)"}
CHUNK = 1024 * 256


@dataclass
class Dataset:
    key: str
    domain: str
    url: str
    filename: str
    license: str
    sha256: Optional[str]           # None finche' non e' stato congelato dal primo download
    expected_bytes: Optional[int]
    supports_range: bool            # il server consente la ripresa?
    notes: str = ""
    redistribution: str = ""        # vincoli, se diversi da "libera"
    extract: List[str] = field(default_factory=list)   # membri da estrarre se e' uno zip

    @property
    def path(self) -> str:
        return os.path.join(DATASETS_DIR, self.filename)


MANIFEST: List[Dataset] = [
    Dataset(
        key="fits_jwst_smacs0723",
        domain="Astrophysics FITS",
        url="https://archive.stsci.edu/hlsps/jwst-ero/hlsp_jwst-ero_jwst_miri_smacs0723_f770w_v1_i2d.fits",
        filename="jwst_smacs0723_miri_f770w.fits",
        license="Public domain (NASA / STScI, JWST Early Release Observations)",
        sha256="4226ced414c351a3de5663d651c7c7187548d6b05c24303b01a58089299dfb22",
        expected_bytes=36_691_200,
        supports_range=True,
        notes="Il file piu' piccolo della collezione JWST ERO: le alternative "
              "sono 55, 112, 128 e 144 MB.",
    ),
    Dataset(
        key="csv_uci_appliances",
        domain="Industrial Telemetry CSV",
        url="https://archive.ics.uci.edu/static/public/374/appliances+energy+prediction.zip",
        filename="uci_appliances_energy.zip",
        license="CC BY 4.0 (UCI Machine Learning Repository)",
        sha256="2fccf354445d886e7917620b0195db1f3e3e34d5a067a93b844694a4c561255a",
        expected_bytes=11_979_507,
        supports_range=False,
        extract=["energydata_complete.csv"],
        notes="CSV pulito: virgola come separatore, intestazioni quotate.",
    ),
    Dataset(
        key="csv_uci_air_quality",
        domain="Industrial Telemetry CSV",
        url="https://archive.ics.uci.edu/static/public/360/air+quality.zip",
        filename="uci_air_quality.zip",
        license="CC BY 4.0 (UCI Machine Learning Repository)",
        sha256="d4a64013fb385288a8a48d9d193ca7079b2e1bbddf6f8d458feb8c08ab2b8a2a",
        expected_bytes=1_543_989,
        supports_range=False,
        extract=["AirQualityUCI.csv"],
        notes="CSV disordinato del mondo reale: separatore PUNTO E VIRGOLA, "
              "virgola come separatore decimale, terminatori CRLF e due colonne "
              "vuote in coda a ogni riga. Il router lo instrada su TELEMETRY_CSV "
              "per estensione, ma il demux colonnare divide sulla virgola: "
              "spezzera' i decimali. E' un test di robustezza, non un caso comodo.",
    ),
    Dataset(
        key="mesh_stl_wvs",
        domain="CAD Mesh (STL binario)",
        url="https://zenodo.org/api/records/5034614/files/WVS.stl/content",
        filename="zenodo_wvs.stl",
        license="CC0 1.0 (dominio pubblico) - Zenodo record 5034614",
        sha256="6e77d6d477545feaf09eaab08fcaea1128874753c61983e34404bdc8b7c78d84",
        expected_bytes=3_226_584,
        supports_range=False,
        notes="STL binario. Il router lo instrada su CAD_MESH_OBJ, che applica "
              "un demux colonnare testuale: su dati binari e' atteso che non "
              "guadagni nulla e scatti il fallback. E' una misura del buco "
              "STL/STEP, non un difetto del dataset.",
    ),
    Dataset(
        key="mesh_stl_ambulacral",
        domain="CAD Mesh (STL binario)",
        url="https://zenodo.org/api/records/5034614/files/Ambulacral.stl/content",
        filename="zenodo_ambulacral.stl",
        license="CC0 1.0 (dominio pubblico) - Zenodo record 5034614",
        sha256="d9208c47eed001ffc46ad5fa6cbe45a177e5aae691fc7aac98bb0af035c28b90",
        expected_bytes=759_184,
        supports_range=False,
    ),
    Dataset(
        key="gcode_linuxcnc",
        domain="CNC G-Code",
        url="https://raw.githubusercontent.com/LinuxCNC/linuxcnc/master/nc_files/3D_Chips.ngc",
        filename="linuxcnc_3d_chips.ngc",
        license="GPL-2.0 (LinuxCNC)",
        sha256="b0d584021e7ad7b1c94f53167641323dd695f67b032cd0e8810ae470abd5c108",
        expected_bytes=200_509,
        supports_range=True,
        redistribution="NON ridistribuibile con questo repository. Il file porta "
                       "una nota di copyright interna (Rab Gordon, Gary Drew, "
                       "Paul Corner). Scaricalo per uso locale di benchmark.",
    ),
]

# Domini per cui NON e' stata trovata una fonte adatta. Dichiarati apposta:
# un buco esplicito vale piu' di un dato con provenienza ambigua.
KNOWN_GAPS = {
    "LiDAR XYZ Point Cloud":
        "Nessuna fonte reale con licenza e formato adatti. USGS 3DEP e' "
        "irraggiungibile; l'unica alternativa viva (AHN3, 120 MB) e' in "
        "formato LAZ e richiederebbe laspy/PDAL, contraddicendo la promessa "
        "'zero external dependencies' del Tier 1.",
    "Audio PCM 16-bit (.wav)":
        "Nessuna fonte con WAV diretti di dimensione ragionevole. OpenSLR "
        "SLR83 contiene WAV veri ma sono 157 MB di rete per un singolo file "
        "utile; le alternative sono FLAC (LibriSpeech, 330 MB) o campioni "
        "giocattolo da pochi KB.",
}


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def human(n: Optional[int]) -> str:
    return f"{n/1_048_576:.2f} MB" if n else "?"


def download(ds: Dataset) -> None:
    """Scarica, riprendendo se il server lo consente. Solleva in caso di errore."""
    part = ds.path + ".part"
    offset = os.path.getsize(part) if (ds.supports_range and os.path.exists(part)) else 0
    if not ds.supports_range and os.path.exists(part):
        os.remove(part)           # niente ripresa possibile: si riparte pulito

    headers = dict(UA)
    if offset:
        headers["Range"] = f"bytes={offset}-"
        print(f"      ripresa da {human(offset)}")

    req = urllib.request.Request(ds.url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r, open(part, "ab" if offset else "wb") as out:
        total = r.headers.get("Content-Length")
        total = int(total) + offset if total and total.isdigit() else None
        done = offset
        while True:
            block = r.read(CHUNK)
            if not block:
                break
            out.write(block)
            done += len(block)
            if total:
                pct = done / total * 100
                print(f"\r      {human(done)} / {human(total)}  ({pct:5.1f}%)", end="")
            else:
                print(f"\r      {human(done)}", end="")
    print()
    os.replace(part, ds.path)


def process(ds: Dataset, verify_only: bool) -> dict:
    print(f"\n  [{ds.key}] {ds.domain}")
    print(f"      licenza: {ds.license}")

    if os.path.exists(ds.path):
        actual = sha256_of(ds.path)
        size = os.path.getsize(ds.path)
        if ds.sha256 is None:
            print(f"      gia' presente ({human(size)}), checksum non ancora congelato nel manifest")
            return {"status": "present-unpinned", "sha256": actual, "bytes": size}
        if actual == ds.sha256:
            print(f"      gia' presente e verificato ({human(size)})")
            return {"status": "ok-cached", "sha256": actual, "bytes": size}
        print(f"      [!] CHECKSUM NON CORRISPONDE per un file gia' presente")
        print(f"          atteso  {ds.sha256}")
        print(f"          trovato {actual}")
        return {"status": "checksum-mismatch", "sha256": actual, "bytes": size}

    if verify_only:
        print("      assente (modalita' --verify: nessun download)")
        return {"status": "missing", "sha256": None, "bytes": 0}

    try:
        download(ds)
    except urllib.error.HTTPError as e:
        print(f"      [!] URL MORTO O NON ACCESSIBILE: HTTP {e.code}")
        return {"status": f"http-{e.code}", "sha256": None, "bytes": 0}
    except Exception as e:
        print(f"      [!] DOWNLOAD FALLITO: {type(e).__name__}: {e}")
        return {"status": "download-failed", "sha256": None, "bytes": 0}

    size = os.path.getsize(ds.path)
    actual = sha256_of(ds.path)

    if ds.sha256 is not None and actual != ds.sha256:
        os.remove(ds.path)
        print(f"      [!] CHECKSUM NON CORRISPONDE - file scartato")
        print(f"          atteso  {ds.sha256}")
        print(f"          trovato {actual}")
        return {"status": "checksum-mismatch", "sha256": actual, "bytes": size}

    if ds.expected_bytes and abs(size - ds.expected_bytes) > 0:
        print(f"      [!] dimensione inattesa: {size:,} contro {ds.expected_bytes:,}")

    print(f"      scaricato {human(size)}  sha256={actual}")
    return {"status": "downloaded", "sha256": actual, "bytes": size}


def extract_members(ds: Dataset) -> None:
    """Estrae i membri dichiarati. Va eseguita anche quando l'archivio era
    gia' in cache: altrimenti un secondo giro lascia i CSV non estratti."""
    if not ds.extract or not os.path.exists(ds.path) or not zipfile.is_zipfile(ds.path):
        return
    with zipfile.ZipFile(ds.path) as z:
        for member in ds.extract:
            target = os.path.join(DATASETS_DIR, os.path.basename(member))
            if os.path.exists(target):
                continue
            with z.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            print(f"      estratto {os.path.basename(member)} ({human(os.path.getsize(target))})")


def inspect_archives():
    """Elenca il contenuto degli zip scaricati: serve a popolare `extract`."""
    printed = False
    for ds in MANIFEST:
        if os.path.exists(ds.path) and zipfile.is_zipfile(ds.path):
            if not printed:
                print("\n" + "=" * 74)
                print("CONTENUTO DEGLI ARCHIVI (per popolare il campo `extract`)")
                print("=" * 74)
                printed = True
            with zipfile.ZipFile(ds.path) as z:
                print(f"\n  {ds.filename}:")
                for info in z.infolist()[:12]:
                    print(f"     {info.file_size:>12,}  {info.filename}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--verify", action="store_true",
                   help="Verifica soltanto cio' che e' gia' presente, senza scaricare.")
    p.add_argument("--list", action="store_true", help="Mostra il manifest ed esce.")
    args = p.parse_args()

    if args.list:
        for ds in MANIFEST:
            print(f"  {ds.key:<26} {ds.domain}")
            print(f"      {ds.url}")
            print(f"      licenza: {ds.license}")
            if ds.redistribution:
                print(f"      RIDISTRIBUZIONE: {ds.redistribution}")
        print("\n  Domini senza fonte adatta:")
        for dom, why in KNOWN_GAPS.items():
            print(f"    - {dom}: {why}")
        return 0

    os.makedirs(DATASETS_DIR, exist_ok=True)
    print(f"Destinazione: {DATASETS_DIR}")
    print(f"Tetto di download per terzi: {BUDGET_MB} MB")

    results = {}
    for ds in MANIFEST:
        results[ds.key] = process(ds, args.verify)
        if results[ds.key]["status"] in ("downloaded", "ok-cached", "present-unpinned"):
            extract_members(ds)

    inspect_archives()

    print("\n" + "=" * 74)
    print("RIEPILOGO")
    print("=" * 74)
    total = sum(r["bytes"] for r in results.values())
    for ds in MANIFEST:
        r = results[ds.key]
        print(f"  {r['status']:<20} {human(r['bytes']):>10}  {ds.filename}")
        if r["sha256"]:
            print(f"                       sha256={r['sha256']}")
    print(f"\n  Totale: {human(total)}  (tetto {BUDGET_MB} MB)")
    if total > BUDGET_MB * 1_048_576:
        print(f"  [!] TETTO SUPERATO")

    print("\n  Domini senza fonte adatta (buchi dichiarati):")
    for dom, why in KNOWN_GAPS.items():
        print(f"    - {dom}")

    bad = [k for k, r in results.items()
           if r["status"] not in ("ok-cached", "downloaded", "present-unpinned")]
    if bad:
        print(f"\n  [!] PROBLEMI su: {', '.join(bad)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
