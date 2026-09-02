import os

count = 0
for root, _, files in os.walk("."):
    if ".git" in root or ".pytest_cache" in root or "venv" in root:
        continue
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "rb") as f:
                content = f.read()
            # Rimuove il BOM UTF-8 se presente (\xef\xbb\xbf)
            if content.startswith(b"\xef\xbb\xbf"):
                with open(path, "wb") as f:
                    f.write(content[3:])
                count += 1

print(f"BOM rimosso con successo da {count} file Python!")
