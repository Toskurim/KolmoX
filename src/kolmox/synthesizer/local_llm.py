"""
KolmoX - Local LLM Integration Bridge
Provides seamless connectivity with local inference servers (Ollama, LM Studio, vLLM).
"""

import json
import urllib.request
import urllib.error
from typing import Optional


class LocalLLMClient:
    def __init__(self, base_url: str = "http://localhost:11434/v1", model: str = "qwen2.5-coder", timeout: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def is_available(selonly: bool = False) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/models", headers={"User-Agent": "KolmoX/1.0"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def synthesize_generator(self, preview_hex: str, total_size: int) -> Optional[str]:
        system_prompt = (
            "You are an expert data synthesis engineer. Write a Python 3 function `generate(size: int) -> bytes` "
            "that produces the exact or closest binary pattern represented by the preview hex."
            "Return ONLY the pure Python code inside a markdown ```python block."
        )
        user_prompt = f"Preview (first 64 bytes hex): {preview_hex}\nTotal size: {total_size}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 512
        }

        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "KolmoX/1.0"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]
                return content
        except Exception:
            return None
