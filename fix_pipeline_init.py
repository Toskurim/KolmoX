with open("src/kolmox/core/pipeline.py", "r", encoding="utf-8") as f:
    text = f.read()

# Assicuriamo che nell'__init__ di KolmoXPipeline sia sempre impostato self.allow_code_execution
if "self.allow_code_execution =" not in text:
    target = "self.cache = DeduplicationCache(max_entries=max_cache_entries) if enable_cache else None"
    replacement = target + "\n        self.allow_code_execution = allow_code_execution"
    # Se il parametro non c'era nella firma
    text = text.replace("max_cache_entries: int = 1000,\n    ):", "max_cache_entries: int = 1000,\n        allow_code_execution: bool = True,\n    ):")
    text = text.replace(target, replacement)

# Rendiamo sicuro l'accesso con getattr
text = text.replace(
    "can_exec = self.allow_code_execution if allow_code_execution is None else allow_code_execution",
    "can_exec = getattr(self, 'allow_code_execution', True) if allow_code_execution is None else allow_code_execution"
)

text = text.replace(
    "if not self.allow_code_execution:",
    "if not getattr(self, 'allow_code_execution', True):"
)

with open("src/kolmox/core/pipeline.py", "w", encoding="utf-8") as f:
    f.write(text)

print("pipeline.py allineato con successo!")
