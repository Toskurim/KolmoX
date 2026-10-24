"""Property testing con hypothesis.

Le proprieta' che una libreria di compressione lossless deve avere sempre, su
qualunque input, e non solo sugli esempi che chi l'ha scritta aveva in mente.
La perdita dati della 1.3.0 e' stata trovata cosi': 32 proprieta' rosse alla
prima esecuzione, tutte su casi limite che nessun test a esempio copriva.

    P1  roundtrip con rilevamento automatico del dominio
    P2  ogni trasformazione di dominio e' una biiezione (o rifiuta l'input)
    P3  roundtrip con dominio forzato, per ogni dominio, su byte qualunque
    P4  mai peggio del baseline Zstd incapsulato
    P5  un container manomesso non decomprime in silenzio dati diversi
    P6  i container scritti dalla 1.3.0 restano leggibili
"""

import glob
import os
import struct

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings, strategies as st  # noqa: E402

from kolmox.core.domain_router import DomainRouter, DomainType  # noqa: E402
from kolmox.core.pipeline import KMX2_MAGIC, KMX2_VERSION, KolmoXPipeline  # noqa: E402

PIPE = KolmoXPipeline(compression_level=3)
SETTINGS = settings(
    max_examples=int(os.environ.get("KOLMOX_PROP_EXAMPLES", "150")),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "legacy_v130")


# --- Generatori di input strutturati -------------------------------------
# Byte casuali non arrivano quasi mai dentro un engine: il router li manda a
# GENERIC. Questi generatori producono file "quasi validi", che e' dove i
# bug di inversione vivono.

number = st.one_of(
    st.integers(-10**6, 10**6).map(lambda i: b"%d" % i),
    st.floats(-1e6, 1e6, allow_nan=False).map(lambda f: (b"%.4f" % f)),
    st.floats(-1e6, 1e6, allow_nan=False).map(lambda f: (b"%.3e" % f)),
)


@st.composite
def numeric_tables(draw):
    ncols = draw(st.integers(1, 7))
    sep = draw(st.sampled_from([b" ", b"\t", b"  ", b", "]))
    eol = draw(st.sampled_from([b"\n", b"\r\n"]))
    rows = draw(st.lists(st.lists(number, min_size=ncols, max_size=ncols), min_size=1, max_size=60))
    lines = [sep.join(r) for r in rows]
    # righe estranee: commenti, header, righe vuote, colonne in piu'
    extras = draw(st.lists(st.sampled_from([b"# comment", b"", b"1 2 3 4 5", b"x y z", b" 1 2 3", b"7"]), max_size=4))
    for e in extras:
        lines.insert(draw(st.integers(0, len(lines))), e)
    trailing = draw(st.sampled_from([eol, b""]))
    return eol.join(lines) + trailing


@st.composite
def wav_files(draw):
    nframes = draw(st.integers(0, 400))
    pcm = draw(st.binary(min_size=nframes * 4, max_size=nframes * 4))
    pcm += draw(st.binary(max_size=3))  # coda non multipla di 4
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 2, 44100, 44100 * 4, 4, 16)
    data = b"data" + struct.pack("<I", len(pcm)) + pcm + (b"\x00" if len(pcm) % 2 else b"")
    after = draw(st.sampled_from([b"", b"LIST" + struct.pack("<I", 4) + b"INFO", b"id3 " + struct.pack("<I", 3) + b"abc\x00"]))
    before = draw(st.sampled_from([b"", b"JUNK" + struct.pack("<I", 4) + b"data"]))  # "data" dentro un altro chunk
    body = b"WAVE" + before + fmt + data + after
    blob = b"RIFF" + struct.pack("<I", len(body)) + body
    cut = draw(st.integers(0, 3))  # file troncato
    return blob[: len(blob) - cut] if cut else blob


@st.composite
def bmp_files(draw):
    w = draw(st.integers(1, 24))
    h = draw(st.integers(1, 12))
    bpp = draw(st.sampled_from([24, 32]))
    ch = bpp // 8
    row = w * ch
    padded = (row + 3) // 4 * 4
    pixels = draw(st.binary(min_size=row * h, max_size=row * h))
    pad_byte = draw(st.sampled_from([None, 0, 0xFF]))
    rows = b""
    for y in range(h):
        pad = bytes(padded - row) if pad_byte == 0 else (
            bytes([pad_byte]) * (padded - row) if pad_byte is not None else draw(st.binary(min_size=padded - row, max_size=padded - row))
        )
        rows += pixels[y * row : (y + 1) * row] + pad
    hdr = struct.pack("<2sIHHI", b"BM", 54 + len(rows), 0, 0, 54)
    hdr += struct.pack("<IiiHHIIiiII", 40, w, draw(st.sampled_from([h, -h])), 1, bpp, 0, len(rows), 2835, 2835, 0, 0)
    return hdr + rows + draw(st.binary(max_size=5))


csv_files = st.lists(
    st.lists(number, min_size=3, max_size=3), min_size=1, max_size=40
).flatmap(
    lambda rows: st.sampled_from([b",", b";"]).map(
        lambda d: b"time" + d + b"a" + d + b"b\n" + b"\n".join(d.join(r) for r in rows) + b"\n"
    )
)

gcode_files = st.lists(
    st.tuples(st.sampled_from([b"G0", b"G1", b"", b"M3"]), st.lists(st.tuples(st.sampled_from(b"XYZF"), number), max_size=3)),
    min_size=1,
    max_size=40,
).map(
    lambda ls: b"G1 X0\n" + b"\n".join(
        b" ".join(([c] if c else []) + [bytes([a]) + v for a, v in words]) for c, words in ls
    )
)

structured = st.one_of(
    st.tuples(numeric_tables(), st.sampled_from(["a.xyz", "a.pts", "a.txt", None])),
    st.tuples(wav_files(), st.sampled_from(["a.wav", None])),
    st.tuples(bmp_files(), st.sampled_from(["a.bmp", None])),
    st.tuples(csv_files, st.just("a.csv")),
    st.tuples(gcode_files, st.sampled_from(["a.gcode", None])),
    st.tuples(st.binary(max_size=2048), st.sampled_from([None, "a.bin", "a.xyz", "a.wav", "a.bmp", "a.csv", "a.obj"])),
)


def baseline_len(data: bytes) -> int:
    return 24 + len(PIPE.cctx.compress(data))


# --- P1 -------------------------------------------------------------------

@SETTINGS
@given(structured)
def test_p1_roundtrip_auto_domain(case):
    data, filename = case
    assert PIPE.decompress_bytes(PIPE.compress_bytes(data, filename)) == data


# --- P2 -------------------------------------------------------------------

DOMAIN_INPUTS = {
    DomainType.POINTCLOUD_XYZ: numeric_tables(),
    DomainType.AUDIO_PCM16: st.one_of(wav_files(), st.binary(max_size=512)),
    DomainType.RASTER_2D: bmp_files(),
    DomainType.TELEMETRY_CSV: csv_files,
    DomainType.GCODE: gcode_files,
}


@pytest.mark.parametrize("domain", list(DOMAIN_INPUTS), ids=lambda d: d.name)
def test_p2_transform_is_bijection(domain):
    @SETTINGS
    @given(DOMAIN_INPUTS[domain])
    def check(data):
        try:
            primary, aux = DomainRouter.precondition(domain, data)
        except ValueError:
            return  # rifiutare l'input e' lecito: la pipeline ripiega su Zstd
        assert DomainRouter.postcondition(domain, primary, aux) == data

    check()


# --- P3 -------------------------------------------------------------------

@pytest.mark.parametrize("domain", [d for d in DomainType if d != DomainType.GENERIC], ids=lambda d: d.name)
def test_p3_roundtrip_forced_domain(domain):
    @SETTINGS
    @given(st.binary(max_size=1024))
    def check(data):
        assert PIPE.decompress_bytes(PIPE.compress_bytes(data, force_domain=domain)) == data

    check()


# --- P4 -------------------------------------------------------------------

@SETTINGS
@given(structured)
def test_p4_never_worse_than_baseline(case):
    data, filename = case
    assert len(PIPE.compress_bytes(data, filename)) <= baseline_len(data)


# --- P5 -------------------------------------------------------------------
# Copertura: tutto cio' che segue l'header di 24 byte (frame Zstd con
# checksum XXH64) e il campo della taglia originale. Magic, versione e
# domain_id non sono protetti da checksum: e' un limite noto, dichiarato in
# README, che richiederebbe un cambio di formato.

@SETTINGS
@given(structured, st.data())
def test_p5_tampered_container_is_never_silent(case, draw):
    data, filename = case
    packet = bytearray(PIPE.compress_bytes(data, filename))
    covered = list(range(24, len(packet))) + list(range(8, 16))
    pos = draw.draw(st.sampled_from(covered))
    bit = draw.draw(st.integers(0, 7))
    packet[pos] ^= 1 << bit
    try:
        out = PIPE.decompress_bytes(bytes(packet))
    except Exception:
        return  # errore esplicito: corretto
    assert out == data, f"byte {pos} manomesso decompresso in silenzio in dati diversi"


# --- P6 -------------------------------------------------------------------

LEGACY = sorted(glob.glob(os.path.join(FIXTURES, "*.kmx")))


@pytest.mark.parametrize("path", LEGACY, ids=lambda p: os.path.basename(p))
def test_p6_legacy_v130_containers_still_decode(path):
    with open(path, "rb") as fh:
        packet = fh.read()
    with open(path[:-4] + ".orig", "rb") as fh:
        original = fh.read()
    assert packet[:4] == KMX2_MAGIC and struct.unpack_from("<H", packet, 4)[0] == KMX2_VERSION
    assert PIPE.decompress_bytes(packet) == original


def test_p6_fixtures_exist():
    assert len(LEGACY) >= 5
