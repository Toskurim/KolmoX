with open("src/kolmox/sandbox/runner.py", "r", encoding="utf-8") as f:
    code = f.read()

old_exec = """        try:
            exec(script_source, global_scope, local_scope)"""

new_exec = """        if not kwargs.get("allow_code_execution", False):
            raise PermissionError(
                "Arbitrary code execution in sandbox is disabled by default. "
                "Explicitly provide allow_code_execution=True to run synthesis scripts."
            )
        try:
            exec(script_source, global_scope, local_scope)"""

if "allow_code_execution" not in code:
    code = code.replace(old_exec, new_exec)
    with open("src/kolmox/sandbox/runner.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("runner.py patchato con guardie di sicurezza!")
else:
    print("runner.py già protetto.")
