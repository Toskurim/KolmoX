with open("README.md", "r", encoding="utf-8") as f:
    text = f.read()

# Ripristina il badge PyPI ufficiale con la versione aggiornata
old_badge = "[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)"
pypi_badge = "[![PyPI version](https://img.shields.io/pypi/v/kolmox.svg)](https://pypi.org/project/kolmox/)"

if old_badge in text:
    text = text.replace(old_badge, f"{pypi_badge} {old_badge}")

with open("README.md", "w", encoding="utf-8") as f:
    f.write(text)

print("Badge PyPI ripristinato con successo nel README!")
