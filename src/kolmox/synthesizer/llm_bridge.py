"""
KolmoX - LLM Program Synthesis Bridge
"""
import re
import requests
from typing import Optional, Dict, Any


class LLMSynthesizerBridge:
    def __init__(self, base_url: str = "http://localhost:1234/v1", model: str = "local-model", timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def synthesize_code(self, profile: Dict[str, Any], block_len: int) -> Optional[str]:
        prompt = (
            f"You are a data compression synthesis engine.\n"
            f"Write a python function `def generate() -> bytes:` that generates exactly {block_len} bytes.\n"
            f"Data sample: {profile.get('sample_integers', [])[:32]}\n"
            f"Return ONLY python code in a markdown block."
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        try:
            resp = requests.post(f"{self.base_url}/chat/completions", json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                raw = resp.json()["choices"][0]["message"]["content"]
                return self._extract_clean_code(raw)
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_clean_code(raw_text: str) -> Optional[str]:
        blocks = re.findall(r"```(?:python)?(.*?)```", raw_text, re.DOTALL)
        code = blocks[0].strip() if blocks else raw_text.strip()
        return code if "def generate" in code else None