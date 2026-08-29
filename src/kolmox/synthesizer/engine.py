"""
KolmoX - Advanced Generative Synthesis Engine
"""

import math
from typing import Optional
import numpy as np
from kolmox.synthesizer.profiler import StreamProfiler


class SynthesisEngine:
    def __init__(self, api_base_url: Optional[str] = None, model: str = "qwen2.5-coder"):
        self.api_base_url = api_base_url
        self.model = model

    def synthesize_heuristic(self, data: bytes) -> Optional[str]:
        total_len = len(data)
        profile = StreamProfiler.profile(data)

        # 1. Periodic exact repetitions
        if profile["detected_period"]:
            p = profile["detected_period"]
            pattern = list(data[:p])
            return (
                "def generate():\n"
                f"    pattern = bytes({pattern})\n"
                f"    p_len = len(pattern)\n"
                f"    total = {total_len}\n"
                "    repeats = total // p_len\n"
                "    rem = total % p_len\n"
                "    return pattern * repeats + pattern[:rem]\n"
            )

        # 2. Linear modulo sequence
        if total_len > 3:
            step = (data[1] - data[0]) % 256
            is_linear = True
            for i in range(min(512, total_len - 1)):
                if (data[i] + step) % 256 != data[i + 1]:
                    is_linear = False
                    break
            if is_linear:
                start = data[0]
                return (
                    "def generate():\n"
                    f"    buf = bytearray({total_len})\n"
                    f"    for i in range({total_len}):\n"
                    f"        buf[i] = ({start} + i * {step}) % 256\n"
                    "    return bytes(buf)\n"
                )

        # 3. Trigonometric fitting
        if total_len >= 128:
            arr = np.frombuffer(data[:min(4096, total_len)], dtype=np.uint8).astype(np.float64)
            offset = float(np.mean(arr))
            amp = float(np.ptp(arr) / 2.0)
            
            # Autocorrelation to find exact period
            norm = arr - offset
            autocorr = np.correlate(norm, norm, mode="full")[len(norm)-1:]
            peaks = np.where((autocorr[1:-1] > autocorr[:-2]) & (autocorr[1:-1] > autocorr[2:]))[0] + 1

            if len(peaks) > 0:
                period = float(peaks[0])
                omega = (2.0 * math.pi) / period
                
                # Check phase
                idx = np.arange(len(arr))
                best_phase = 0.0
                best_err = float("inf")
                for ph in np.linspace(0, 2 * math.pi, 64):
                    pred = np.clip(np.round(offset + amp * np.sin(idx * omega + ph)), 0, 255)
                    err = np.sum(np.abs(arr - pred))
                    if err < best_err:
                        best_err = err
                        best_phase = ph

                if best_err < (len(arr) * 2.0):
                    return (
                        "import math\n"
                        "def generate():\n"
                        f"    buf = bytearray({total_len})\n"
                        f"    amp = {amp:.6f}\n"
                        f"    offset = {offset:.6f}\n"
                        f"    omega = {omega:.6f}\n"
                        f"    phase = {best_phase:.6f}\n"
                        f"    for i in range({total_len}):\n"
                        "        val = int(offset + amp * math.sin(i * omega + phase))\n"
                        "        buf[i] = max(0, min(255, val))\n"
                        "    return bytes(buf)\n"
                    )

        return None

    def synthesize(self, data: bytes) -> str:
        script = self.synthesize_heuristic(data)
        if script:
            return script
        
        total_len = len(data)
        return f"def generate():\n    return bytes({total_len})\n"