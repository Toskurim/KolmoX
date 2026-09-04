"""
Unit tests for the Synthesis Engine.
"""

from kolmox.synthesizer.engine import SynthesisEngine
from kolmox.core.pipeline import KolmoXPipeline


def test_heuristic_linear_synthesis():
    engine = SynthesisEngine()
    # Linear modulo dataset
    data = bytes([(5 + i * 9) % 256 for i in range(5000)])
    script = engine.synthesize(data)
    
    assert script is not None
    # Percorso a sintesi di codice: unsafe by design, opt-in esplicito.
    pipeline = KolmoXPipeline(allow_code_execution=True)
    compressed = pipeline.compress_with_script(data, script)
    restored = pipeline.decompress(compressed)

    assert restored == data
    # Extremely small footprint expected for mathematical series
    assert len(compressed) < 200