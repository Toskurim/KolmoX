"""
KolmoX - Unit Tests for Local LLM Bridge
"""
from kolmox.synthesizer.local_llm import LocalLLMClient


def test_local_llm_offline_graceful_failure():
    # Punta a una porta non in ascolto per testare il fallback
    client = LocalLLMClient(base_url="http://127.0.0.1:59999/v1", timeout=0.5)
    assert client.is_available() is False
    assert client.synthesize_generator("00010203", 100) is None
