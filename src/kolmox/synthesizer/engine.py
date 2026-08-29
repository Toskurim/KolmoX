"""
KolmoX - Generative Synthesis Engine
"""
import math
from typing import Optional
import numpy as np
from kolmox.synthesizer.profiler import StreamProfiler
from kolmox.synthesizer.llm_bridge import LLMSynthesizerBridge


class SynthesisEngine:
    def __init__(self, api_base_url: Optional[str] = None, model: str = "local-model"):
        self.api_base_url = api_base_url
        self.model = model
        self.llm_bridge = LLMSynthesizerBridge(base_url=api_base_url, model=model) if api_base_url else None

    def synthesize_heuristic(self, data: bytes) -> Optional[str]:
        total_len = len(data)
        profile = StreamProfiler.profile(data)

        if profile["detected_period"]:
            p = profile["detected_period"]
            pattern = list(data[:p])
            return (
                f"def generate():\n"
                f"    pattern = bytes({pattern})\n"
                f"    return pattern * ({total_len} // {p}) + pattern[:{total_len} % {p}]\n"
            )

        if total_len > 3:
            step = (data[1] - data[0]) % 256
            if all((data[i] + step) % 256 == data[i + 1] for i in range(min(512, total_len - 1))):
                return (
                    f"def generate():\n"
                    f"    buf = bytearray({total_len})\n"
                    f"    for i in range({total_len}):\n"
                    f"        buf[i] = ({data[0]} + i * {step}) % 256\n"
                    f"    return bytes(buf)\n"
                )
        return None

    def synthesize(self, data: bytes) -> str:
        script = self.synthesize_heuristic(data)
        if script:
            return script

        if self.llm_bridge and self.llm_bridge.is_available():
            profile = StreamProfiler.profile(data)
            res = self.llm_bridge.synthesize_code(profile, len(data))
            if res:
                return res

        return f"def generate():\n    return bytes({len(data)})\n"