# 1. Aggiorna requirements.txt assicurando tutte le dipendenze per i test
reqs = """numpy>=1.22.0
zstandard>=0.20.0
pytest>=7.0.0
astropy>=5.0.0
"""
with open("requirements.txt", "w", encoding="utf-8") as f:
    f.write(reqs)

# 2. Correggi il badge CI/CD nel README.md se punta a un nome errato
with open("README.md", "r", encoding="utf-8") as f:
    readme = f.read()

# Assicura che il badge punti alla action tests.yml del repo Toskurim/KolmoX
old_badge_ci = "https://github.com/Toskurim/KolmoX/actions/workflows/tests.yml/badge.svg"
correct_badge_ci = "https://github.com/Toskurim/KolmoX/actions/workflows/tests.yml/badge.svg?branch=main"

if "actions/workflows/tests.yml/badge.svg" in readme and "?branch=main" not in readme:
    readme = readme.replace(old_badge_ci, correct_badge_ci)

with open("README.md", "w", encoding="utf-8") as f:
    f.write(readme)

print("Dipendenze CI e configurazione aggiornate!")
