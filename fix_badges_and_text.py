with open("README.md", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Correggi i riferimenti ai vecchi numeri sintetici nel testo introduttivo
old_text_1 = "delivers up to 28x+ on arrays and +22.87% net savings over Zstd on raw JWST FITS datasets"
new_text_1 = "delivers up to 15.7x on industrial telemetry, 1.97x on dense float arrays, and +22.87% net memory savings over Zstd on raw JWST FITS datasets"

old_text_2 = "Squeezing columnar telemetry by 40x-47x drastically cuts cloud egress"
new_text_2 = "Squeezing columnar telemetry and register streams by 12x–16x drastically cuts cloud egress"

text = text.replace(old_text_1, new_text_1)
text = text.replace(old_text_2, new_text_2)

# Se le stringhe esatte differiscono per punteggiatura, usiamo una sostituzione tollerante
import re
text = re.sub(r"delivers up to \d+x\+ on arrays", "delivers up to 15.7x on binary registers and 1.97x on dense vectors", text)
text = re.sub(r"columnar telemetry by \d+x[–\-]\d+x", "columnar telemetry by 12x–16x", text)

# 2. Ripara il badge Python per non mostrare "missing"
old_py_badge = "[![Python](https://img.shields.io/pypi/pyversions/kolmox.svg)](https://pypi.org/project/kolmox/)"
new_py_badge = "[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)"
text = text.replace(old_py_badge, new_py_badge)

with open("README.md", "w", encoding="utf-8") as f:
    f.write(text)

print("Testi e badge nel README.md allineati con successo!")
