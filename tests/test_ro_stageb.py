"""RES-95 stage-B RO narrative generation: gold integrity, sanitization, fallback, determinism.

These tests use a *fake* narrator so they run with no model download and no mlx-lm — the gold-
integrity moat (byte-equality + strict BIOES + checksum-valid ids) is exercised exactly as in a real
run, because the splice/validation path is identical regardless of who authored the body.
"""

from __future__ import annotations

import pytest

from europriv_bench.national_id import validate_cnp
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from europriv_bench.taxonomy import ENTITY_NAMES
from klusai.privacy.datasets.data.ro_stageb import (
    REQUIRED_SLOTS,
    StageBConfig,
    _sanitize_template,
    generate_stageb,
)


class FakeNarrator:
    """Deterministic stand-in for MlxNarrator: emits varied, valid bodies (slots placed once each)."""

    # A pool of clean bodies, each using every required slot exactly once, digit-free, distinct
    # structure — mirrors what the LLM is prompted to produce.
    BODIES = [
        "Subsemnatul {person} vă comunic, la data de {date}, că domiciliez în {address} și pot fi "
        "contactat la {phone}, conform CNP {cnp}.",
        "Prin prezenta, {person} (CNP {cnp}) solicită o programare pentru {date}; adresa de "
        "corespondență este {address}, telefon {phone}.",
        "Către primărie: {person}, cu reședința în {address}, telefon {phone}, înregistrat cu CNP "
        "{cnp}, depune cererea în data de {date}.",
        "Vă informăm că dosarul lui {person}, identificat prin CNP {cnp}, a fost actualizat la "
        "{date}; corespondența se trimite la {address}, iar telefonul de contact este {phone}.",
    ]

    def __init__(self):
        self.calls = 0

    def write_body(self, genre, slots, seed):
        self.calls += 1
        return self.BODIES[seed % len(self.BODIES)]


class BadNarrator:
    """Always returns an unusable body → forces the deterministic stage-A fallback path."""

    def write_body(self, genre, slots, seed):
        return "Acest corp nu conține substituenții ceruți și are o cifră 7."  # missing slots + digit


def _rows(narrator, n=24, seed=5):
    return list(generate_stageb(StageBConfig(n=n, seed=seed), narrator=narrator))


def test_yields_n_rows_with_ro_metadata():
    rows = _rows(FakeNarrator(), n=20)
    assert len(rows) == 20
    for r in rows:
        assert r["language"] == "ro"
        assert r["text"] and isinstance(r["spans"], list)
        assert r["family"] == "stageb"


def test_gold_integrity_byte_equality_and_bioes():
    """Every span is byte-exact and projects to valid BIOES — the inherited quality moat."""
    for r in _rows(FakeNarrator(), n=40, seed=7):
        assert r["spans"], "expected PII spans"
        for s in r["spans"]:
            assert r["text"][s["start"]:s["end"]], "empty span"
            assert s["label"] in ENTITY_NAMES, f"non-taxonomy label {s['label']!r}"
        # independent re-projection (fill_document already asserted this internally)
        validate_bioes(char_spans_to_bioes(
            r["text"], [Span(s["start"], s["end"], s["label"]) for s in r["spans"]]
        ))


def test_national_id_spans_are_checksum_valid_cnp():
    """The NATIONAL_ID gold value must be a checksum-valid CNP (LLM never authors the value)."""
    seen = 0
    for r in _rows(FakeNarrator(), n=40, seed=3):
        for s in r["spans"]:
            if s["label"] == "NATIONAL_ID":
                seen += 1
                assert validate_cnp(r["text"][s["start"]:s["end"]]), "invalid CNP reached gold"
    assert seen >= 30, "expected a CNP in (almost) every doc"


def test_determinism():
    a = [r["text"] for r in _rows(FakeNarrator(), n=15, seed=11)]
    b = [r["text"] for r in _rows(FakeNarrator(), n=15, seed=11)]
    assert a == b


def test_bad_body_falls_back_deterministically_and_stays_valid():
    """An unusable LLM body must not stall or corrupt — it falls back to a valid stage-A doc."""
    rows = _rows(BadNarrator(), n=12, seed=1)
    assert len(rows) == 12
    for r in rows:
        for s in r["spans"]:
            assert r["text"][s["start"]:s["end"]]
            assert s["label"] in ENTITY_NAMES
        validate_bioes(char_spans_to_bioes(
            r["text"], [Span(s["start"], s["end"], s["label"]) for s in r["spans"]]
        ))


# --------------------------------------------------------------------------- #
# Sanitizer unit tests — the gate that keeps LLM output safe to splice
# --------------------------------------------------------------------------- #
def test_sanitizer_accepts_clean_body():
    body = "{person} cu CNP {cnp}, domiciliat în {address}, telefon {phone}, la {date}."
    assert _sanitize_template(body, REQUIRED_SLOTS) is not None


def test_sanitizer_rejects_missing_slot():
    body = "{person} cu CNP {cnp}, telefon {phone}, la {date}."  # no {address}
    assert _sanitize_template(body, REQUIRED_SLOTS) is None


def test_sanitizer_allows_repeated_known_slot():
    """A repeated slot is realistic and safe — every occurrence splices the same valid value."""
    body = "{person} ({cnp}) confirmă: {person}, domiciliat în {address}, telefon {phone}, la {date}."
    assert _sanitize_template(body, REQUIRED_SLOTS) is not None


def test_repeated_slot_splices_byte_exact_spans():
    """A {person} used twice yields two byte-exact PERSON spans (gold integrity under repetition)."""
    from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes

    body = "{person} confirmă că {person} (CNP {cnp}) locuiește în {address}, telefon {phone}, la {date}."

    class TwiceNarrator:
        def write_body(self, genre, slots, seed):
            return body

    rows = list(generate_stageb(StageBConfig(n=4, seed=2), narrator=TwiceNarrator()))
    for r in rows:
        persons = [s for s in r["spans"] if s["label"] == "PERSON"]
        assert len(persons) == 2, "both {person} occurrences should be spliced as spans"
        for s in r["spans"]:
            assert r["text"][s["start"]:s["end"]]
        validate_bioes(char_spans_to_bioes(
            r["text"], [Span(s["start"], s["end"], s["label"]) for s in r["spans"]]
        ))


def test_sanitizer_rejects_unknown_slot():
    body = "{person} {cnp} {address} {phone} {date} {iban}"  # unknown {iban}
    assert _sanitize_template(body, REQUIRED_SLOTS) is None


def test_sanitizer_rejects_digits_outside_slots():
    """A literal digit the model smuggled into the prose is rejected (could masquerade as PII)."""
    body = "{person} {cnp} {address} {phone} {date} suma 1500 lei"
    assert _sanitize_template(body, REQUIRED_SLOTS) is None


def test_sanitizer_rejects_stray_brace():
    body = "{person} {cnp} {address} {phone} {date} extra {"
    assert _sanitize_template(body, REQUIRED_SLOTS) is None


def test_sanitizer_rejects_leaked_markup():
    body = '```json {person} {cnp} {address} {phone} {date}```'
    assert _sanitize_template(body, REQUIRED_SLOTS) is None


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_fake_bodies_are_all_acceptable(seed):
    """Guard the fixtures themselves stay valid templates."""
    body = FakeNarrator.BODIES[seed % len(FakeNarrator.BODIES)]
    assert _sanitize_template(body, REQUIRED_SLOTS) is not None
