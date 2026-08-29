from kolmox.synthesizer.llm_bridge import LLMSynthesizerBridge
from kolmox.synthesizer.engine import SynthesisEngine


def test_llm_code_extraction():
    raw = "```python\ndef generate():\n    return bytes(10)\n```"
    assert "def generate():" in LLMSynthesizerBridge._extract_clean_code(raw)


def test_engine_offline_fallback():
    engine = SynthesisEngine(api_base_url="http://localhost:59999/v1")
    assert "def generate" in engine.synthesize(b"test_data_12345")