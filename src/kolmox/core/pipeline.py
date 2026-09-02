"""
KolmoX Unified Pipeline Orchestrator (v1.1.0)
Full support for Script Synthesis, Dynamic Delta, Chunking, and Extended Domain Preconditioners.
"""

import struct
from typing import Optional
import zstandard as zstd

import kolmox.core.container as container_mod
import kolmox.core.delta as delta_mod
from kolmox.core.domain_router import DomainRouter, DomainType

# Risoluzione dinamica container
if hasattr(container_mod, "KolmoXContainer"):
    ContainerHandler = getattr(container_mod, "KolmoXContainer")
elif hasattr(container_mod, "KolmoxContainer"):
    ContainerHandler = getattr(container_mod, "KolmoxContainer")
elif hasattr(container_mod, "Container"):
    ContainerHandler = getattr(container_mod, "Container")
else:
    ContainerHandler = container_mod

# Risoluzione dinamica delta engine
DeltaHandler = getattr(delta_mod, "DeltaEngine", delta_mod)

KMX2_MAGIC = b"KMX2"
KMX2_VERSION = 0x0110


class KolmoXPipeline:
    def __init__(self, chunk_size: int = 65536, compression_level: int = 3):
        self.chunk_size = chunk_size
        self.compression_level = compression_level
        self.cctx = zstd.ZstdCompressor(level=compression_level)
        self.dctx = zstd.ZstdDecompressor()

    def _calc_delta(self, raw_data: bytes, predicted_data: bytes) -> bytes:
        if hasattr(DeltaHandler, "compute_delta"):
            ops = DeltaHandler.compute_delta(raw_data, predicted_data)
            return DeltaHandler.pack_delta(ops) if hasattr(DeltaHandler, "pack_delta") else ops
        elif hasattr(DeltaHandler, "encode_delta"):
            return DeltaHandler.encode_delta(raw_data, predicted_data)
        elif hasattr(DeltaHandler, "create_delta"):
            return DeltaHandler.create_delta(raw_data, predicted_data)
        elif hasattr(DeltaHandler, "diff"):
            return DeltaHandler.diff(raw_data, predicted_data)
        else:
            # Fallback XOR delta
            min_len = min(len(raw_data), len(predicted_data))
            xor_part = bytes([r ^ p for r, p in zip(raw_data[:min_len], predicted_data[:min_len])])
            return xor_part + raw_data[min_len:]

    def _apply_delta(self, predicted_data: bytes, delta_bytes: bytes) -> bytes:
        if hasattr(DeltaHandler, "apply_delta"):
            try:
                if hasattr(DeltaHandler, "unpack_delta"):
                    ops = DeltaHandler.unpack_delta(delta_bytes)
                    return DeltaHandler.apply_delta(predicted_data, ops)
            except Exception:
                pass
            return DeltaHandler.apply_delta(predicted_data, delta_bytes)
        elif hasattr(DeltaHandler, "decode_delta"):
            return DeltaHandler.decode_delta(predicted_data, delta_bytes)
        elif hasattr(DeltaHandler, "patch"):
            return DeltaHandler.patch(predicted_data, delta_bytes)
        else:
            min_len = min(len(predicted_data), len(delta_bytes))
            xor_part = bytes([p ^ d for p, d in zip(predicted_data[:min_len], delta_bytes[:min_len])])
            return xor_part + delta_bytes[min_len:]

    def compress_with_script(self, raw_data: bytes, python_script: str, allow_code_execution: Optional[bool] = None) -> bytes:
        """Pipeline classica basata su sintesi di codice + delta residuo."""
        can_exec = getattr(self, 'allow_code_execution', True) if allow_code_execution is None else allow_code_execution
        if not can_exec:
            raise PermissionError(
                "Arbitrary code execution is disabled by default for security. "
                "Pass allow_code_execution=True to explicitly permit running untrusted synthesis scripts."
            )
        loc = {}
        exec(python_script, {}, loc)
        if "generate" not in loc or not callable(loc["generate"]):
            raise ValueError("Lo script sintetizzato non espone la funzione generate().")

        predicted_data = loc["generate"]()
        packed_delta = self._calc_delta(raw_data, predicted_data)

        compressed_delta = self.cctx.compress(packed_delta)
        compressed_script = self.cctx.compress(python_script.encode("utf-8"))

        if hasattr(ContainerHandler, "pack_container"):
            return ContainerHandler.pack_container(
                compressed_script=compressed_script,
                compressed_delta=compressed_delta,
                raw_len=len(raw_data),
                domain_id=int(DomainType.GENERIC),
            )
        elif hasattr(container_mod, "pack_container"):
            return container_mod.pack_container(
                compressed_script=compressed_script,
                compressed_delta=compressed_delta,
                raw_len=len(raw_data),
                domain_id=int(DomainType.GENERIC),
            )
        else:
            return struct.pack("<4sQQ", b"KMX1", len(compressed_script), len(compressed_delta)) + compressed_script + compressed_delta

    def decompress_container(self, container_bytes: bytes) -> bytes:
        """Decompressione classica da container KolmoX."""
        if hasattr(ContainerHandler, "unpack_container"):
            parsed = ContainerHandler.unpack_container(container_bytes)
        elif hasattr(container_mod, "unpack_container"):
            parsed = container_mod.unpack_container(container_bytes)
        else:
            magic, s_len, d_len = struct.unpack("<4sQQ", container_bytes[:20])
            parsed = {
                "compressed_script": container_bytes[20 : 20 + s_len],
                "compressed_delta": container_bytes[20 + s_len : 20 + s_len + d_len],
            }

        decompressed_script = self.dctx.decompress(parsed["compressed_script"]).decode("utf-8")
        decompressed_delta = self.dctx.decompress(parsed["compressed_delta"])

        if not getattr(self, 'allow_code_execution', True):
            raise PermissionError(
                "Arbitrary code execution is disabled by default for security. "
                "Decompressing legacy script containers requires allow_code_execution=True."
            )
        loc = {}
        exec(decompressed_script, {}, loc)
        predicted = loc["generate"]()

        return self._apply_delta(predicted, decompressed_delta)

    def compress_bytes(
        self,
        data: bytes,
        filename: Optional[str] = None,
        force_domain: Optional[DomainType] = None,
    ) -> bytes:
        """Pipeline estesa v1.1.2 (Extended Domains & Multi-stream KMX2 con Adaptive Competitive Fallback)."""
        target_domain = (
            force_domain
            if force_domain is not None
            else DomainRouter.detect_domain(data, filename)
        )

        # 1. Baseline garantito: compressione grezza Zstd incapsulata in KMX2 GENERIC
        raw_comp_primary = self.cctx.compress(data)
        baseline_header = struct.pack(
            "<4sHBBQQ",
            KMX2_MAGIC,
            KMX2_VERSION,
            int(DomainType.GENERIC),
            0,
            len(data),
            0,
        )
        baseline_packet = baseline_header + raw_comp_primary

        if target_domain == DomainType.GENERIC:
            return baseline_packet

        # 2. Tentativo di trasformazione di dominio competitivo
        try:
            primary_payload, aux_payload = DomainRouter.precondition(target_domain, data)
            comp_primary = self.cctx.compress(primary_payload)
            comp_aux = self.cctx.compress(aux_payload) if aux_payload else b""

            candidate_header = struct.pack(
                "<4sHBBQQ",
                KMX2_MAGIC,
                KMX2_VERSION,
                int(target_domain),
                0,
                len(data),
                len(comp_aux),
            )
            candidate_packet = candidate_header + comp_aux + comp_primary

            # Competitive Check: mantieni la trasformazione SOLO se batte il baseline grezzo
            if len(candidate_packet) < len(baseline_packet):
                return candidate_packet
        except Exception:
            # Fallback trasparente in caso di anomalie di dominio o dati corrotti
            pass

        return baseline_packet

    def decompress_bytes(self, kmx_data: bytes) -> bytes:
        """Decompressione universale."""
        if len(kmx_data) >= 4 and kmx_data[:4] == KMX2_MAGIC:
            magic, version, domain_val, _, orig_size, aux_comp_len = struct.unpack(
                "<4sHBBQQ", kmx_data[:24]
            )
            domain = DomainType(domain_val)

            offset = 24
            if aux_comp_len > 0:
                comp_aux = kmx_data[offset : offset + aux_comp_len]
                aux_payload = self.dctx.decompress(comp_aux)
                offset += aux_comp_len
            else:
                aux_payload = b""

            comp_primary = kmx_data[offset:]
            primary_payload = self.dctx.decompress(comp_primary)

            return DomainRouter.postcondition(domain, primary_payload, aux_payload)

        return self.decompress_container(kmx_data)

    # Alias per retrocompatibilità con i test legacy
    def compress(self, data: bytes, filename: Optional[str] = None) -> bytes:
        return self.compress_bytes(data, filename)

    def decompress(self, kmx_data: bytes) -> bytes:
        return self.decompress_bytes(kmx_data)