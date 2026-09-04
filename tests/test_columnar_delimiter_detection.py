"""
Rilevamento automatico del separatore di campo in ColumnarTextEngine.

Il separatore veniva assunto (virgola). Un CSV di locale europeo usa il punto
e virgola per i campi e la virgola per i decimali: assumendo la virgola il
demux spezza i decimali e produce righe irregolari.

Il rilevamento lavora a livello di byte. Il modulo che ospitava questa
euristica prima (TextColumnarEngine, ritirato) decodificava con
errors="replace", distruggendo irreversibilmente i byte non-UTF8.
"""
import struct

import pytest

from kolmox.core.domain_router import DomainRouter, DomainType
from kolmox.core.pipeline import KolmoXPipeline
from kolmox.engines.columnar_text import ColumnarTextEngine


def build(delim: bytes, rows: int = 40, fields: int = 6, decimal: bytes = b".") -> bytes:
    header = delim.join(b"col%d" % i for i in range(fields))
    out = [header]
    for r in range(rows):
        out.append(delim.join(b"%d%s%02d" % (r, decimal, c) for c in range(fields)))
    return b"\n".join(out) + b"\n"


# ---------------------------------------------------------------- rilevamento

@pytest.mark.parametrize("delim", [b",", b";", b"\t", b"|"])
def test_detects_each_candidate(delim):
    assert ColumnarTextEngine.detect_delimiter(build(delim)) == delim


def test_european_csv_prefers_semicolon_over_comma():
    """Il caso reale: punto e virgola per i campi, virgola per i decimali.
    La virgola compare piu' spesso, ma produce conteggi irregolari."""
    raw = build(b";", decimal=b",")
    assert ColumnarTextEngine.detect_delimiter(raw) == b";"


def test_absent_delimiter_is_not_chosen():
    """Un separatore che non compare darebbe una sola classe di forma, cioe'
    il punteggio migliore: va scartato, non premiato."""
    raw = build(b";")
    for absent in (b"\t", b"|"):
        assert ColumnarTextEngine.detect_delimiter(raw, (absent,)) == absent  # unico candidato
    # con tutti i candidati vince quello che compare davvero
    assert ColumnarTextEngine.detect_delimiter(raw) == b";"


def test_no_delimiter_at_all_falls_back_to_default():
    raw = b"\n".join(b"riga senza separatori %d" % i for i in range(20))
    assert ColumnarTextEngine.detect_delimiter(raw) == b","


def test_empty_input_falls_back_to_default():
    assert ColumnarTextEngine.detect_delimiter(b"") == b","


def test_detection_does_not_decode():
    """Byte non-UTF8 non devono far esplodere ne' alterare il rilevamento."""
    raw = b"a;b;c\n\xff\xfe;\x80\x81;\xc0\xc1\n" + b"\n".join(
        b"%d;%d;%d" % (i, i, i) for i in range(20)
    )
    assert ColumnarTextEngine.detect_delimiter(raw) == b";"


# ------------------------------------------------------------ bit-exactness

EDGE_CASES = {
    "virgola":            build(b","),
    "punto e virgola":    build(b";"),
    "tab":                build(b"\t"),
    "pipe":               build(b"|"),
    "europeo (; e ,)":    build(b";", decimal=b","),
    "CRLF":               build(b";").replace(b"\n", b"\r\n"),
    "colonne vuote in coda": b"\n".join(
        b"a;b;c;;" if i == 0 else b"%d;%d;%d;;" % (i, i, i) for i in range(20)) + b"\n",
    "righe irregolari":   b"a;b;c\n1;2\n3;4;5;6\n7\n8;9;10\n11;12\n13;14;15\n16;17;18\n",
    "byte non-UTF8":      b"a;b\n\xff\xfe;\x00\x01\n\x80\x81;\xc0\xc1\n" + b"\n".join(
        b"%d;%d" % (i, i) for i in range(20)) + b"\n",
    "senza newline finale": build(b";")[:-1],
    "righe vuote in mezzo": b"a;b;c\n1;2;3\n\n4;5;6\n\n\n7;8;9\n10;11;12\n13;14;15\n",
    "nessun separatore":  b"\n".join(b"riga %d" % i for i in range(20)),
}


@pytest.mark.parametrize("label", list(EDGE_CASES))
def test_roundtrip_bit_exact_with_autodetect(label):
    raw = EDGE_CASES[label]
    primary, aux = ColumnarTextEngine.transform(raw)
    assert aux == b""
    assert ColumnarTextEngine.inverse(primary) == raw


@pytest.mark.parametrize("label", list(EDGE_CASES))
def test_pipeline_roundtrip(label):
    raw = EDGE_CASES[label]
    pipeline = KolmoXPipeline()
    kmx = pipeline.compress_bytes(raw, filename="telemetry.csv")
    assert pipeline.decompress_bytes(kmx) == raw


# --------------------------------------------------------- retrocompatibilita'

def test_delimiter_is_stored_in_the_header():
    """Il separatore vive nell'header del primary: e' per questo che il
    rilevamento non richiede un bump di versione del sottoformato."""
    for delim in (b",", b";", b"\t", b"|"):
        primary, _ = ColumnarTextEngine.transform(build(delim))
        version, delim_byte, _, _ = struct.unpack(
            ColumnarTextEngine.HEADER_FMT, primary[: ColumnarTextEngine.HEADER_LEN]
        )
        assert version == ColumnarTextEngine.VERSION
        assert bytes([delim_byte]) == delim


def test_container_written_with_explicit_comma_still_decodes():
    """RETROCOMPATIBILITA': un container scritto prima del rilevamento
    automatico usava sempre la virgola. Deve continuare a decodificare."""
    raw = build(b";", decimal=b",")          # oggi il rilevamento sceglierebbe ';'
    legacy_primary, _ = ColumnarTextEngine.transform(raw, b",")   # forzato come prima
    assert legacy_primary[1:2] == b","
    assert ColumnarTextEngine.inverse(legacy_primary) == raw


def test_explicit_delimiter_still_honoured():
    """Il percorso OBJ passa lo spazio esplicitamente: non deve essere
    scavalcato dal rilevamento."""
    obj = b"# c\no M\n" + b"\n".join(b"v %d.0 %d.0 %d.0" % (i, i, i) for i in range(20)) + b"\n"
    primary, _ = ColumnarTextEngine.transform(obj, b" ", group_by_first_token=True)
    assert primary[1:2] == b" "
    assert ColumnarTextEngine.inverse(primary) == obj


def test_router_uses_autodetection_for_csv():
    raw = build(b";", decimal=b",")
    assert DomainRouter.detect_domain(raw, "t.csv") == DomainType.TELEMETRY_CSV
    primary, aux = DomainRouter.precondition(DomainType.TELEMETRY_CSV, raw)
    assert primary[1:2] == b";"
    assert DomainRouter.postcondition(DomainType.TELEMETRY_CSV, primary, aux) == raw
