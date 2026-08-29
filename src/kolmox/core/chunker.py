"""
KolmoX - Multi-Block Manager with Columnar Stride Awareness
"""

from typing import List, Tuple
import struct
import zstandard as zstd
from kolmox.synthesizer.engine import SynthesisEngine
from kolmox.core.delta import DeltaEngine
from kolmox.core.stride import StrideEngine
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
        orig_len = len(block_data)
        direct_zstd = self.cctx.compress(block_data)

        # 1. Check if columnar transposition improves entropy/synthesis
        stride = StrideEngine.detect_stride(block_data)
        data_to_encode = block_data
        if stride:
            data_to_encode = StrideEngine.transpose(block_data, stride)
            transposed_zstd = self.cctx.compress(data_to_encode)
            # If transposed zstd alone is already smaller, consider it
            if len(transposed_zstd) + 2 < len(direct_zstd):
                # Mode 2: Transposed Direct Mode
                return struct.pack(">BIIB", 2, 0, orig_len, stride) + transposed_zstd

        # 2. Try Program Synthesis
        try:
            script = self.synth_engine.synthesize(data_to_encode)
            reconstructed = self.runner.execute(script)
            residual = self.delta_engine.compute_residual(data_to_encode, reconstructed)
            
            script_bytes = script.encode("utf-8")
            s_val = stride if stride else 0
            gen_payload = struct.pack(">BIIB", 1, len(script_bytes), orig_len, s_val) + script_bytes + residual

            if len(gen_payload) < len(direct_zstd):
                return gen_payload
        except Exception:
            pass

        # Mode 0: Raw fallback
        return struct.pack(">BIIB", 0, 0, orig_len, 0) + direct_zstd

    def decompress_block(self, block_payload: bytes) -> Tuple[bytes, int]:
        mode, script_len, orig_len, stride = struct.unpack(">BIIB", block_payload[:10])

        if mode == 0:  # Direct Fallback
            decompressed = self.dctx.decompress(block_payload[10:], max_output_size=orig_len)
            return decompressed, len(block_payload)

        if mode == 2:  # Transposed Direct
            decomp = self.dctx.decompress(block_payload[10:])
            restored = StrideEngine.untranspose(decomp, stride, orig_len)
            return restored, len(block_payload)

        # Mode 1: Generative Mode
        script_end = 10 + script_len
        script_source = block_payload[10:script_end].decode("utf-8")
        residual_data = block_payload[script_end:]
        
        reconstructed = self.runner.execute(script_source)
        restored = self.delta_engine.apply_residual(reconstructed, residual_data)
        
        if stride > 0:
            restored = StrideEngine.untranspose(restored, stride, orig_len)

        return restored, len(block_payload)
