"""
Versionamento del payload video: KMXV1 (XOR legacy) e KMXV2 (delta aritmetico).

Il punto centrale di questi test e' la retrocompatibilita': un container
scritto dalla versione vecchia deve restare decomprimibile bit-exact dopo il
passaggio al delta aritmetico.
"""
import struct

import numpy as np
import pytest

from kolmox.core.domain_router import (
    DomainRouter,
    DomainType,
    VIDEO_RAW_SEQUENCE_HEADER_FMT,
    VIDEO_RAW_SEQUENCE_MAGIC,
)
from kolmox.core.pipeline import KolmoXPipeline
from kolmox.engines.video_engine import VideoEngine

W, H, C, N = 64, 48, 3, 8


def make_frames(seed=1):
    """Sequenza con drift temporale, piu' un frame ad alto contrasto che
    stressa il caso in cui XOR e sottrazione divergono di piu'."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[:H, :W]
    frames = []
    for t in range(N):
        r = ((x * 2) + (y * 3) + t * 3) % 256
        g = ((x * 4) - (y * 2) + t * 2) % 256
        b = ((x + y + t) * 2) % 256
        f = np.stack([r, g, b], axis=-1).astype(np.uint8)
        f = (f.astype(np.int16) + rng.integers(-3, 3, f.shape)).clip(0, 255).astype(np.uint8)
        frames.append(f.tobytes())
    # valori a cavallo del bit alto: 127/128 danno XOR=255 ma sottrazione=1
    edge = np.full((H, W, C), 127, dtype=np.uint8)
    edge[::2] = 128
    frames[N // 2] = edge.tobytes()
    return frames


def make_blob(payload_builder):
    frames = make_frames()
    header = struct.pack(VIDEO_RAW_SEQUENCE_HEADER_FMT, VIDEO_RAW_SEQUENCE_MAGIC, W, H, C, N)
    return header + b"".join(frames), frames


def test_new_writer_emits_v2():
    frames = make_frames()
    payload = VideoEngine.compress_sequence(frames, W, H, C)
    assert payload[:5] == VideoEngine.MAGIC_V2 == b"KMXV2"


def test_legacy_writer_emits_v1():
    frames = make_frames()
    payload = VideoEngine.compress_sequence_legacy_xor(frames, W, H, C)
    assert payload[:5] == VideoEngine.MAGIC == b"KMXV1"


def test_v2_roundtrip_bit_exact():
    frames = make_frames()
    payload = VideoEngine.compress_sequence(frames, W, H, C)
    assert VideoEngine.decompress_sequence(payload) == frames


def test_legacy_v1_payload_still_decodes_bit_exact():
    """RETROCOMPATIBILITA': un payload KMXV1 scritto con lo schema vecchio deve
    restare leggibile bit-exact dal decoder nuovo."""
    frames = make_frames()
    legacy = VideoEngine.compress_sequence_legacy_xor(frames, W, H, C)
    assert legacy[:5] == b"KMXV1"
    assert VideoEngine.decompress_sequence(legacy) == frames


def test_v1_and_v2_payloads_differ_but_decode_identically():
    frames = make_frames()
    v1 = VideoEngine.compress_sequence_legacy_xor(frames, W, H, C)
    v2 = VideoEngine.compress_sequence(frames, W, H, C)
    assert v1[5:] != v2[5:], "i due schemi devono produrre residui diversi"
    assert VideoEngine.decompress_sequence(v1) == VideoEngine.decompress_sequence(v2) == frames


def test_unknown_magic_is_rejected():
    frames = make_frames()
    payload = bytearray(VideoEngine.compress_sequence(frames, W, H, C))
    payload[:5] = b"KMXV9"
    with pytest.raises(ValueError):
        VideoEngine.decompress_sequence(bytes(payload))


def test_pipeline_roundtrip_v2():
    blob, _ = make_blob(None)
    pipeline = KolmoXPipeline()
    kmx = pipeline.compress_bytes(blob, filename="clip.kmxvraw")
    assert kmx[6] == int(DomainType.VIDEO_TEMPORAL)
    assert pipeline.decompress_bytes(kmx) == blob


def test_pipeline_reads_legacy_v1_container():
    """RETROCOMPATIBILITA' end-to-end: un container KMX2 con domain_id=9 il cui
    payload interno e' KMXV1 deve decomprimersi bit-exact attraverso la
    pipeline pubblica, esattamente come prima del cambio di formato."""
    blob, frames = make_blob(None)

    # Ricostruisce cio' che la pipeline avrebbe archiviato prima del cambio:
    # stesso container KMX2, stesso domain_id, ma payload interno KMXV1.
    legacy_primary = VideoEngine.compress_sequence_legacy_xor(frames, W, H, C)
    pipeline = KolmoXPipeline()
    comp_primary = pipeline.cctx.compress(legacy_primary)
    header = struct.pack(
        "<4sHBBQQ", b"KMX2", 0x0110, int(DomainType.VIDEO_TEMPORAL), 0, len(blob), 0
    )
    legacy_container = header + comp_primary

    assert pipeline.decompress_bytes(legacy_container) == blob


def test_postcondition_handles_both_versions():
    _, frames = make_blob(None)
    for payload in (
        VideoEngine.compress_sequence(frames, W, H, C),
        VideoEngine.compress_sequence_legacy_xor(frames, W, H, C),
    ):
        restored = DomainRouter.postcondition(DomainType.VIDEO_TEMPORAL, payload, b"")
        assert restored[:8] == VIDEO_RAW_SEQUENCE_MAGIC
        assert restored[21:] == b"".join(frames)
