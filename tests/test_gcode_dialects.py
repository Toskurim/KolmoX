"""
Dialetti G-code: N-word attaccata, comandi modali, retrocompatibilita'.

Il G-code reale non e' solo `G1 X10 Y20`. RS-274/NGC ammette un numero di riga
opzionale (spesso senza spazio dopo, `N430X10`), e i comandi sono modali: dopo
un `G1` iniziale le righe successive portano solo le parole d'asse.
"""
import pytest

from kolmox.core.domain_router import DomainRouter, DomainType
from kolmox.core.pipeline import KolmoXPipeline
from kolmox.engines.extended_domains import GCodeEngine

DIALECTS = {
    "classico G1 con spazio": (
        b"G21\nG90\n"
        b"G1 X10.5 Y20.25 Z-1.5 F300\n"
        b"G1 X11.0 Y21.75 Z-1.6 F300\n"
        b"G0 X0 Y0 Z5\n"
    ),
    "N-word con spazio": (
        b"N10 G21\nN20 G90\n"
        b"N30 G1 X10.5 Y20.25 Z-1.5\n"
        b"N40 G1 X11.0 Y21.75 Z-1.6\n"
    ),
    "N-word attaccata": (
        b"N10G21\n"
        b"N20G1 X10.5 Y20.25\n"
        b"N30X11.0 Y21.75\n"
        b"N40X12.5 Y22.0\n"
    ),
    "modale senza G esplicito": (
        b"G21\nG90\nG1 F300\n"
        b"X10.5 Y20.25\n"
        b"X11.0 Y21.75\n"
        b"X12.5 Y22.0 Z-1.0\n"
    ),
    "espressioni parametriche (non estratte)": (
        b"#<xscale> = 1.0\n"
        b"N10G1 F300\n"
        b"N20X[#<xscale>*52.972]Y[#<xscale>*53.293]\n"
        b"N30X[#<xscale>*52.893]Y[#<xscale>*53.547]\n"
    ),
    "misto: numerici ed espressioni sulla stessa riga": (
        b"N10G1 X10.5 Y[#<yscale>*3.2] Z-1.5\n"
        b"N20X11.0 Y[#<yscale>*3.4] Z-1.6\n"
    ),
    "commenti e variabili": (
        b"( commento di intestazione )\n"
        b"#<toolno> = 1\n"
        b"N10G21\n"
        b"N20G1 X1.5 Y2.5\n"
    ),
    "senza newline finale": b"G1 X1 Y2\nG1 X3 Y4",
    "righe vuote": b"G1 X1 Y2\n\n\nG1 X3 Y4\n",
}


@pytest.mark.parametrize("label", list(DIALECTS))
def test_roundtrip_bit_exact(label):
    raw = DIALECTS[label]
    template, coords = GCodeEngine.transform(raw)
    assert GCodeEngine.inverse(template, coords) == raw


def test_n_word_extracted_into_own_column():
    """Il numero di riga varia a ogni riga: se restasse nel template, il
    template sarebbe diverso per ogni riga e non comprimerebbe."""
    raw = b"N10G1 X1 Y2\nN20X3 Y4\nN30X5 Y6\n"
    template, coords = GCodeEngine.transform(raw)

    lines = [l for l in template.split(b"\n") if l]
    # tutte e tre le righe portano il segnaposto, nessun numero e' nel template
    assert all(l.startswith(b"N\x00") for l in lines)
    assert b"N10" not in template and b"N20" not in template and b"N30" not in template
    # le due righe modali collassano nella stessa identica forma: e' questo che
    # rende il template comprimibile
    modal = [l for l in lines if l.startswith(b"N\x00X")]
    assert len(modal) == 2 and len(set(modal)) == 1
    assert GCodeEngine.inverse(template, coords) == raw


def test_modal_lines_are_recognised():
    raw = b"G1 F300\nX1.5 Y2.5\nX3.5 Y4.5\n"
    template, coords = GCodeEngine.transform(raw)
    assert template.count(b"X\x00") == 2
    assert GCodeEngine.inverse(template, coords) == raw


def test_parametric_expressions_stay_in_template():
    """Fuori scope per scelta: smontare le espressioni di LinuxCNC
    significherebbe modellare la sintassi di un solo dialetto."""
    raw = b"N10X[#<xscale>*52.972]Y[#<yscale>*53.293]\n"
    template, coords = GCodeEngine.transform(raw)
    assert b"[#<xscale>*52.972]" in template     # non estratta
    assert b"N\x00" in template                  # ma la N-word si'
    assert GCodeEngine.inverse(template, coords) == raw


def test_g10_g17_are_not_mistaken_for_moves():
    """_EXPLICIT_MOVE non deve catturare G10/G17: solo G0 e G1."""
    raw = b"G17 X1 Y2\nG10 L2 P1 X0\n"
    template, _ = GCodeEngine.transform(raw)
    assert b"X\x00" not in template


def test_legacy_three_section_coords_still_decode():
    """RETROCOMPATIBILITA': i container scritti prima del supporto N-word
    hanno tre sezioni di coordinate, non quattro."""
    template = b"G1 X\x00 Y\x00 Z\x00\nG1 X\x00 Y\x00 Z\x00"
    legacy = b"\n".join([b"1", b"3", b"---", b"2", b"4", b"---", b"5", b"6"])
    assert GCodeEngine.inverse(template, legacy) == b"G1 X1 Y2 Z5\nG1 X3 Y4 Z6"


@pytest.mark.parametrize("label", list(DIALECTS))
def test_pipeline_roundtrip(label):
    raw = DIALECTS[label]
    pipeline = KolmoXPipeline()
    kmx = pipeline.compress_bytes(raw, filename="part.ngc")
    assert pipeline.decompress_bytes(kmx) == raw


def test_real_dialect_routes_to_gcode():
    raw = b"N10G21\nN20G1 X1 Y2\nN30X3 Y4\n"
    assert DomainRouter.detect_domain(raw, "part.ngc") == DomainType.GCODE
