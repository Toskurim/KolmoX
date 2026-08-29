"""
KolmoX - Unified Adaptive Pipeline with CAD & Mesh Pre-processing
"""

import struct
from typing import Optional
import zstandard as zstd
from kolmox.core.chunker import BlockCompressor
from kolmox.core.container import KolmoXContainer
from kolmox.core.delta import DeltaEngine
from kolmox.core.text_columnar import TextColumnarEngine
from kolmox.core.mesh_cad import MeshCADEngine
from kolmox.sandbox.runner import SandboxRunner

MAGIC_CONTAINER = b"KMX3"


class KolmoXPipeline:
    def __init__(self, chunk_size: int = 131072, delta_level: int = 19, api_base_url: Optional[str] = None):
        self.chunk_size = chunk_size
        self.delta_level = delta_level
        self.delta_engine = DeltaEngine(compression_level=delta_level)
        self.block_comp = BlockCompressor(delta_level=delta_level)
        self.block_comp.synth_engine.api_base_url = api_base_url
        self.runner = SandboxRunner()
        self.cctx = zstd.ZstdCompressor(level=delta_level)
        self.dctx = zstd.ZstdDecompressor()

    def compress_with_script(self, original_data: bytes, script_source: str) -> bytes:
        reconstructed = self.runner.execute(script_source)
        residual_data = self.delta_engine.compute_residual(original_data, reconstructed)
        return KolmoXContainer.pack(
            script_source=script_source,
            residual_data=residual_data,
            original_size=len(original_data),
        )

    def compress(self, data: bytes) -> bytes:
        direct = self.cctx.compress(data)

        # 1. Check 3D CAD Mesh (.obj)
        if MeshCADEngine.is_obj_mesh(data) and len(data) < 10_000_000:
            try:
                meta, geom = MeshCADEngine.transpose_mesh(data)
                rebuilt = MeshCADEngine.untranspose_mesh(meta, geom)
                if rebuilt == data:
                    comp_geom = self.cctx.compress(geom)
                    cand = struct.pack(">4sQI", b"KMXG", len(data), len(meta)) + meta + comp_geom
                    if len(cand) < len(direct):
                        return cand
            except Exception:
                pass

        # 2. Check Tabular / CSV Stream
        is_tabular, sep = TextColumnarEngine.is_tabular_text(data)
        if is_tabular and len(data) < 10_000_000:
            try:
                hdr, payload = TextColumnarEngine.transpose_text(data, sep)
                rebuilt = TextColumnarEngine.untranspose_text(hdr, payload, sep)
                if rebuilt == data:
                    comp_payload = self.cctx.compress(payload)
                    cand = struct.pack(">4sQIB", b"KMXT", len(data), len(hdr), ord(sep)) + hdr + comp_payload
                    if len(cand) < len(direct):
                        return cand
            except Exception:
                pass

        # 3. Standard Multi-Block Chunking
        chunks = [data[i : i + self.chunk_size] for i in range(0, len(data), self.chunk_size)]
        block_payloads = [self.block_comp.compress_block(c) for c in chunks]

        combined = bytearray()
        combined.extend(struct.pack(">I", len(chunks)))
        for bp in block_payloads:
            combined.extend(struct.pack(">I", len(bp)))
            combined.extend(bp)

        compressed_stream = self.cctx.compress(bytes(combined))
        header = struct.pack(">4sQI", MAGIC_CONTAINER, len(data), len(chunks))
        
        final_cand = header + compressed_stream
        return final_cand if len(final_cand) < len(direct) else struct.pack(">4sQI", b"KMX0", len(data), 0) + direct

    def decompress(self, kmx_data: bytes) -> bytes:
        magic = kmx_data[:4]

        if magic == b"KMX0":
            return self.dctx.decompress(kmx_data[16:])

        if magic == b"KMXG":
            magic, orig_size, meta_len = struct.unpack(">4sQI", kmx_data[:16])
            meta_end = 16 + meta_len
            meta = kmx_data[16:meta_end]
            decomp_geom = self.dctx.decompress(kmx_data[meta_end:])
            return MeshCADEngine.untranspose_mesh(meta, decomp_geom)

        if magic == b"KMXT":
            magic, orig_size, hdr_len, sep_byte = struct.unpack(">4sQIB", kmx_data[:17])
            sep = chr(sep_byte)
            hdr_end = 17 + hdr_len
            hdr = kmx_data[17:hdr_end]
            decomp_payload = self.dctx.decompress(kmx_data[hdr_end:])
            return TextColumnarEngine.untranspose_text(hdr, decomp_payload, sep)

        if magic == b"KMX2":
            unpacked = KolmoXContainer.unpack(kmx_data)
            reconstructed = self.runner.execute(unpacked["script_source"])
            return self.delta_engine.apply_residual(reconstructed, unpacked["residual_data"])

        header_len = struct.calcsize(">4sQI")
        magic, orig_size, chunk_count = struct.unpack(">4sQI", kmx_data[:header_len])
        if magic != MAGIC_CONTAINER:
            raise ValueError(f"Invalid magic header: {magic}")

        decompressed_stream = self.dctx.decompress(kmx_data[header_len:])
        num_chunks = struct.unpack(">I", decompressed_stream[:4])[0]
        
        offset = 4
        restored_buffer = bytearray()
        for _ in range(num_chunks):
            bp_len = struct.unpack(">I", decompressed_stream[offset : offset + 4])[0]
            offset += 4
            block_bytes = decompressed_stream[offset : offset + bp_len]
            offset += bp_len

            restored_block, _ = self.block_comp.decompress_block(block_bytes)
            restored_buffer.extend(restored_block)

        return bytes(restored_buffer)
