import re, os, shutil

# 1. Bump setup.py
with open("setup.py", "r", encoding="utf-8") as f:
    setup_txt = f.read()
setup_txt = re.sub(r'version\s*=\s*["\']1\.1\.1["\']', 'version="1.1.2"', setup_txt)
with open("setup.py", "w", encoding="utf-8") as f:
    f.write(setup_txt)

# 2. Bump pyproject.toml
with open("pyproject.toml", "r", encoding="utf-8") as f:
    pyproj_txt = f.read()
pyproj_txt = re.sub(r'version\s*=\s*["\']1\.1\.1["\']', 'version = "1.1.2"', pyproj_txt)
with open("pyproject.toml", "w", encoding="utf-8") as f:
    f.write(pyproj_txt)

# 3. Bump __init__.py se presente la versione
init_path = os.path.join("src", "kolmox", "__init__.py")
if os.path.exists(init_path):
    with open(init_path, "r", encoding="utf-8") as f:
        init_txt = f.read()
    init_txt = re.sub(r'__version__\s*=\s*["\']1\.1\.1["\']', '__version__ = "1.1.2"', init_txt)
    with open(init_path, "w", encoding="utf-8") as f:
        f.write(init_txt)

# 4. Pulisci la vecchia cartella dist/
if os.path.exists("dist"):
    shutil.rmtree("dist")

print("Versione aggiornata a 1.1.2 e dist/ pulita!")
