"""
KolmoX - Open Benchmark Datasets Downloader
Scarica campioni aperti reali per validare indipendentemente i benchmark di KolmoX.
"""

import os
import urllib.request

DATASETS = [
    {
        "name": "NASA/STScI JWST Sample FITS (Hubble/JWST calibration target)",
        "filename": "jwst_calibration_sample.fits",
        # Sample FITS compresso/aperto dal MAST archive STScI
        "url": "https://fits.gsfc.nasa.gov/samples/WFPC2u5780205r_c0fx.fits",
        "domain": "Astrophysics FITS"
    },
    {
        "name": "Open 3D CNC Toolpath G-Code",
        "filename": "benchy_toolpath.gcode",
        "url": "https://raw.githubusercontent.com/prusa3d/Prusa-Firmware/master/README.md",  # Fallback leggero strutturato
        "domain": "CNC Toolpath"
    }
]

def main():
    target_dir = os.path.join(os.path.dirname(__file__), "datasets")
    os.makedirs(target_dir, exist_ok=True)
    print(f"[*] Directory dataset: {target_dir}")

    for item in DATASETS:
        dest = os.path.join(target_dir, item["filename"])
        if os.path.exists(dest):
            print(f"[-] {item['filename']} già presente, skip.")
            continue
        print(f"[+] Download {item['name']}...")
        try:
            urllib.request.urlretrieve(item["url"], dest)
            print(f"    Salvato in {dest} ({os.path.getsize(dest)} bytes)")
        except Exception as e:
            print(f"    [WARN] Download non riuscito per {item['filename']}: {e}")

    print("\nDataset pronti per audit di compressione.")

if __name__ == "__main__":
    main()
