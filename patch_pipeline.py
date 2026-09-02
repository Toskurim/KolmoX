import re

with open("src/kolmox/core/pipeline.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Modifica costruttore per supportare allow_code_execution
old_init = """    def __init__(
        self,
        level: int = 3,
        enable_cache: bool = True,
        max_cache_entries: int = 1000,
    ):
        self.cctx = zstd.ZstdCompressor(level=level)
        self.dctx = zstd.ZstdDecompressor()
        self.cache = DeduplicationCache(max_entries=max_cache_entries) if enable_cache else None"""

new_init = """    def __init__(
        self,
        level: int = 3,
        enable_cache: bool = True,
        max_cache_entries: int = 1000,
        allow_code_execution: bool = False,
    ):
        self.cctx = zstd.ZstdCompressor(level=level)
        self.dctx = zstd.ZstdDecompressor()
        self.cache = DeduplicationCache(max_entries=max_cache_entries) if enable_cache else None
        self.allow_code_execution = allow_code_execution"""

code = code.replace(old_init, new_init)

# 2. Gate exec() in compress_with_script
old_cws = """    def compress_with_script(self, raw_data: bytes, python_script: str) -> bytes:
        \"\"\"Pipeline classica basata su sintesi di codice + delta residuo.\"\"\"
        loc = {}
        exec(python_script, {}, loc)"""

new_cws = """    def compress_with_script(self, raw_data: bytes, python_script: str, allow_code_execution: Optional[bool] = None) -> bytes:
        \"\"\"Pipeline classica basata su sintesi di codice + delta residuo.\"\"\"
        can_exec = self.allow_code_execution if allow_code_execution is None else allow_code_execution
        if not can_exec:
            raise PermissionError(
                "Arbitrary code execution is disabled by default for security. "
                "Pass allow_code_execution=True to explicitly permit running untrusted synthesis scripts."
            )
        loc = {}
        exec(python_script, {}, loc)"""

code = code.replace(old_cws, new_cws)

# 3. Gate exec() in decompress_container
old_dc = """        decompressed_script = self.dctx.decompress(parsed["compressed_script"]).decode("utf-8")
        decompressed_delta = self.dctx.decompress(parsed["compressed_delta"])

        loc = {}
        exec(decompressed_script, {}, loc)"""

new_dc = """        decompressed_script = self.dctx.decompress(parsed["compressed_script"]).decode("utf-8")
        decompressed_delta = self.dctx.decompress(parsed["compressed_delta"])

        if not self.allow_code_execution:
            raise PermissionError(
                "Arbitrary code execution is disabled by default for security. "
                "Decompressing legacy script containers requires allow_code_execution=True."
            )
        loc = {}
        exec(decompressed_script, {}, loc)"""

code = code.replace(old_dc, new_dc)

# 4. Implementa Adaptive Fallback in compress_bytes
old_cb = """    def compress_bytes(
        self,
        data: bytes,
        filename: Optional[str] = None,
        force_domain: Optional[DomainType] = None,
    ) -> bytes:
        \"\"\"Pipeline estesa v1.1.0 (Extended Domains & Multi-stream KMX2).\"\"\"
        domain = (
            force_domain
            if force_domain is not None
            else DomainRouter.detect_domain(data, filename)
        )
        primary_payload, aux_payload = DomainRouter.precondition(domain, data)

        comp_primary = self.cctx.compress(primary_payload)
        comp_aux = self.cctx.compress(aux_payload) if aux_payload else b""

        header = struct.pack(
            "<4sHBBQQ",
            KMX2_MAGIC,
            KMX2_VERSION,
            int(domain),
            0,
            len(data),
            len(comp_aux),
        )
        return header + comp_aux + comp_primary"""

new_cb = """    def compress_bytes(
        self,
        data: bytes,
        filename: Optional[str] = None,
        force_domain: Optional[DomainType] = None,
    ) -> bytes:
        \"\"\"Pipeline estesa v1.1.2 (Extended Domains & Multi-stream KMX2 con Adaptive Competitive Fallback).\"\"\"
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

        return baseline_packet"""

code = code.replace(old_cb, new_cb)

with open("src/kolmox/core/pipeline.py", "w", encoding="utf-8") as f:
    f.write(code)

print("pipeline.py patchato con Security Gate e Adaptive Fallback!")
