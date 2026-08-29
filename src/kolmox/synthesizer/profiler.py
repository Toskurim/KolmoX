"""
KolmoX - Data Stream Profiler
Extracts structural and statistical metrics from raw byte buffers to guide synthesis.
"""

from typing import Dict, Any, List
import numpy as np


class StreamProfiler:
    @staticmethod
    def profile(data: bytes, sample_limit: int = 4096) -> Dict[str, Any]:
        sample = data[:sample_limit]
        arr = np.frombuffer(sample, dtype=np.uint8)
        
        diffs = np.diff(arr)
        is_monotonic = np.all(diffs >= 0) or np.all(diffs <= 0)
        
        # Check simple periodicity
        period = None
        for p in range(1, min(256, len(sample) // 4)):
            slices = [sample[i:i+p] for i in range(0, p * 4, p)]
            if len(slices) == 4 and slices[0] == slices[1] == slices[2] == slices[3]:
                period = p
                break

        return {
            "total_bytes": len(data),
            "sample_size": len(sample),
            "sample_hex_preview": sample[:64].hex(),
            "sample_integers": arr[:64].tolist(),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "is_monotonic": bool(is_monotonic),
            "detected_period": period,
        }