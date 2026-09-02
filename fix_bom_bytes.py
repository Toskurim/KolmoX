path = "src/kolmox/engines/extended_domains.py"
with open(path, "rb") as f:
    raw = f.read()

# Rimuove qualsiasi byte BOM UTF-8 ovunque sia posizionato nel file
cleaned = raw.replace(b"\xef\xbb\xbf", b"")

with open(path, "wb") as f:
    f.write(cleaned)

print(f"Byte BOM rimossi: {(len(raw) - len(cleaned)) // 3}")
