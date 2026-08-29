"""
KolmoX - Dynamic Stream Segmenter & Multi-Block Manager with Competitive Fallback
"""

from typing import List, Tuple
import struct
import zstandard as zstd
from kolmox.synthesizer.engine import SynthesisEngine
from kolmox.core.delta import DeltaEngine
from kolmox.sandbox.runner import SandboxRunner


class BlockCompressor:
    def __init__(self, delta_level: int = 19):
        self.delta_level = delta_level
        self.delta_engine = DeltaEngine(compression_level=delta_level)
        self.synth_engine = SynthesisEngine()
        self.runner = SandboxRunner()
        self.cctx = zstd.ZstdCompressor(level=delta_level)
        self.dctx = zstd.ZstdDecompressor()

    def compress_block(self, block_data: bytes) -> bytes:
        """
        Synthesizes code and checks if generative mode beats standard entropy compression.
        If not, falls back to direct entropy mode (Mode 0).
        """
        # Baseline compression
        direct_zstd = self.cctx.compress(block_data)

        # Generative attempt
        try:
            script = self.synth_engine.synthesize(block_data)
            reconstructed = self.runner.execute(script)
            residual = self.delta_engine.compute_residual(block_data, reconstructed)
            
            script_bytes = script.encode("utf-8")
            gen_payload = struct.pack(">BII", 1, len(script_bytes), len(block_data)) + script_bytes + residual

            # Pick whichever is smaller
            if len(gen_payload) < len(direct_zstd):
                return gen_payload
        except Exception:
            pass

        # Fallback Mode 0: Raw compressed block
        return struct.pack(">BII", 0, 0, len(block_data)) + direct_zstd

    def decompress_block(self, block_payload: bytes) -> Tuple[bytes, int]:
        mode, script_len, original_len = struct.unpack(">BII", block_payload[:9])

        if mode == 0:  # Direct Mode
            decompressed = self.dctx.decompress(block_payload[9:], max_output_size=original_len)
            return decompressed, len(block_payload)

        # Mode 1: Generative Mode
        script_end = 9 + script_len
        script_source = block_payload[9:script_end].decode("utf-8")
        residual_data = block_payload[script_end:]
        
        reconstructed = self.runner.execute(script_source)
        restored = self.delta_engine.apply_residual(reconstructed, residual_data)
        return restored, len(block_payload)