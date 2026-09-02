import re

with open("src/kolmox/sandbox/runner.py", "r", encoding="utf-8") as f:
    code = f.read()

# Hardening builtins: esponiamo solo le primitive strettamente matematiche e costruttori sicuri
hardened_builtins = """        safe_builtins = {
            "bytearray": bytearray,
            "bytes": bytes,
            "range": range,
            "len": len,
            "int": int,
            "float": float,
            "min": min,
            "max": max,
            "abs": abs,
            "pow": pow,
            "round": round,
        }"""

code = re.sub(r'safe_builtins\s*=\s*\{.*?"__import__":\s*_safe_import,\s*\}', hardened_builtins, code, flags=re.DOTALL)

with open("src/kolmox/sandbox/runner.py", "w", encoding="utf-8") as f:
    f.write(code)

print("runner.py hardened: __import__ rimosso e sandbox blindato!")
