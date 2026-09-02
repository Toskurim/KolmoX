"""
KolmoX - Deterministic Sandbox Runner
Safely executes synthesized generative code in an isolated scope.
"""

import math
from typing import Dict, Any

ALLOWED_MODULES = {"math": math}

def _safe_import(name, *args, **kwargs):
    if name in ALLOWED_MODULES:
        return ALLOWED_MODULES[name]
    raise ImportError(f"Import of module '{name}' is prohibited in KolmoX sandbox.")


class SandboxRunner:
    @staticmethod
    def execute(script_source: str, entry_point: str = "generate") -> bytes:
                safe_builtins = {
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
        }

        local_scope: Dict[str, Any] = {}
        global_scope = {
            "__builtins__": safe_builtins,
            "math": math,
        }

        if not kwargs.get("allow_code_execution", False):
            raise PermissionError(
                "Arbitrary code execution in sandbox is disabled by default. "
                "Explicitly provide allow_code_execution=True to run synthesis scripts."
            )
        try:
            exec(script_source, global_scope, local_scope)
            if entry_point not in local_scope:
                raise ValueError(f"Entrypoint '{entry_point}' not defined in script.")

            result = local_scope[entry_point]()
            if not isinstance(result, (bytes, bytearray)):
                raise TypeError(f"Generator must return bytes/bytearray, got {type(result)}")

            return bytes(result)
        except Exception as e:
            raise RuntimeError(f"Sandbox execution failed: {e}") from e