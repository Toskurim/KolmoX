"""
End-to-End Pipeline Verification Test.
"""

import pytest

from kolmox.core.pipeline import KolmoXPipeline


def test_full_pipeline_compression_cycle():
    # Il percorso a sintesi di codice e' unsafe by design e disattivato di
    # default: va abilitato esplicitamente. Vedi test_script_execution_is_refused_by_default.
    pipeline = KolmoXPipeline(allow_code_execution=True)

    # Target: Structured repeated pattern + tiny variations (e.g. sensor/telemetry series)
    original_data = bytearray()
    for i in range(10000):
        val = (i * 7) % 256
        # Introduce a few anomalies
        if i % 500 == 0:
            val = 255
        original_data.append(val)
    original_data = bytes(original_data)

    # Deterministic micro-generator simulating code synthesis output
    synthesized_script = (
        "def generate():\n"
        "    buf = bytearray(10000)\n"
        "    for i in range(10000):\n"
        "        buf[i] = (i * 7) % 256\n"
        "    return bytes(buf)\n"
    )

    # Compress
    kmx_compressed = pipeline.compress_with_script(original_data, synthesized_script)

    # Decompress
    restored_data = pipeline.decompress(kmx_compressed)

    # Bit-exact assertion
    assert restored_data == original_data

    # Verify compression efficiency (original is 10,000 bytes)
    assert len(kmx_compressed) < len(original_data)


def test_script_execution_is_refused_by_default():
    """Il gate deve essere fail-closed: senza opt-in esplicito, niente exec().

    Questa proprieta' e' regredita tre volte (un `getattr(..., True)` di
    default permissivo reintrodotto da script di patch), quindi e' fissata qui.
    """
    script = "def generate():\n    return bytes(16)\n"
    default_pipeline = KolmoXPipeline()

    assert default_pipeline.allow_code_execution is False
    with pytest.raises(PermissionError):
        default_pipeline.compress_with_script(b"x" * 16, script)

    # Anche un oggetto a cui l'attributo manca del tutto deve rifiutare,
    # non concedere: il fallback di getattr e' False, non True.
    orphan = KolmoXPipeline(allow_code_execution=True)
    del orphan.allow_code_execution
    with pytest.raises(PermissionError):
        orphan.compress_with_script(b"x" * 16, script)


def test_restricted_builtins_block_module_import():
    """I builtins ristretti non sono una sandbox, ma devono almeno impedire
    l'accesso diretto a __import__/open dallo script sintetizzato."""
    pipeline = KolmoXPipeline(allow_code_execution=True)
    hostile = "def generate():\n    import os\n    return bytes(os.name, 'ascii')\n"
    with pytest.raises(Exception):
        pipeline.compress_with_script(b"x" * 16, hostile)