"""RES-95 stage-B EN narrative generation: gold integrity, sanitization, fallback, determinism.

These tests use a *fake* narrator so they run with no model download and no mlx-lm — the gold-
integrity moat (byte-equality + strict BIOES + valid ids) is exercised exactly as in a real run,
because the splice/validation path is identical regardless of who authored the body. This mirrors
``test_ro_stageb`` to confirm the stage-B upgrade is language-agnostic.
"""

from __future__ import annotations

import pytest

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from europriv_bench.taxonomy import ENTITY_NAMES
from klusai.privacy.datasets.data.en_generators import iban_gb_valid, nino_format_valid
from klusai.privacy.datasets.data.en_stageb import (
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
        "I, the undersigned {person}, National Insurance number {nino}, residing at {address}, "
        "reachable on {phone} and by email at {email}, confirm the account {iban} as of {date}.",
        "Dear Sir or Madam, {person} (NINO {nino}) hereby requests an appointment on {date}; the "
        "correspondence address is {address}, contact number {phone}, email {email}, account {iban}.",
        "To the council: {person}, residing at {address}, telephone {phone}, email {email}, "
        "registered under {nino}, lodges this submission on {date} quoting account {iban}.",
        "We confirm that the file for {person}, identified by {nino}, was updated on {date}; "
        "correspondence goes to {address}, the contact email is {email}, telephone {phone}, "
        "settlement to account {iban}.",
    ]

    def __init__(self):
        self.calls = 0

    def write_body(self, genre, slots, seed):
        self.calls += 1
        return self.BODIES[seed % len(self.BODIES)]


class BadNarrator:
    """Always returns an unusable body → forces the deterministic stage-A fallback path."""

    def write_body(self, genre, slots, seed):
        return "This body lacks the required placeholders and has a digit 7."  # missing slots + digit


def _rows(narrator, n=24, seed=5):
    return list(generate_stageb(StageBConfig(n=n, seed=seed), narrator=narrator))


def test_yields_n_rows_with_en_metadata():
    rows = _rows(FakeNarrator(), n=20)
    assert len(rows) == 20
    for r in rows:
        assert r["language"] == "en"
        assert r["text"] and isinstance(r["spans"], list)
        assert r["family"] == "stageb"


def test_gold_integrity_byte_equality_and_bioes():
    """Every span is byte-exact and projects to valid BIOES — the inherited quality moat."""
    for r in _rows(FakeNarrator(), n=40, seed=7):
        assert r["spans"], "expected PII spans"
        for s in r["spans"]:
            assert r["text"][s["start"]:s["end"]], "empty span"
            assert s["label"] in ENTITY_NAMES, f"non-taxonomy label {s['label']!r}"
        validate_bioes(char_spans_to_bioes(
            r["text"], [Span(s["start"], s["end"], s["label"]) for s in r["spans"]]
        ))


def test_national_id_spans_are_format_valid_nino():
    """The NATIONAL_ID gold value must be a format-valid NINO (LLM never authors the value)."""
    seen = 0
    for r in _rows(FakeNarrator(), n=40, seed=3):
        for s in r["spans"]:
            if s["label"] == "NATIONAL_ID":
                seen += 1
                assert nino_format_valid(r["text"][s["start"]:s["end"]]), "invalid NINO reached gold"
    assert seen >= 30, "expected a NINO in (almost) every doc"


def test_account_id_iban_spans_are_checksum_valid():
    """Each ACCOUNT_ID gold value that is a GB IBAN must pass the mod-97 checksum."""
    seen = 0
    for r in _rows(FakeNarrator(), n=40, seed=9):
        for s in r["spans"]:
            if s["label"] == "ACCOUNT_ID":
                seen += 1
                assert iban_gb_valid(r["text"][s["start"]:s["end"]]), "invalid IBAN reached gold"
    assert seen >= 30, "expected an IBAN in (almost) every doc"


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
    body = ("{person} with NINO {nino}, residing at {address}, telephone {phone}, email {email}, "
            "account {iban}, on {date}.")
    assert _sanitize_template(body, REQUIRED_SLOTS) is not None


def test_sanitizer_rejects_missing_slot():
    body = "{person} with NINO {nino}, telephone {phone}, email {email}, account {iban}, on {date}."  # no {address}
    assert _sanitize_template(body, REQUIRED_SLOTS) is None


def test_sanitizer_allows_repeated_known_slot():
    """A repeated slot is realistic and safe — every occurrence splices the same valid value."""
    body = ("{person} ({nino}) confirms: {person}, residing at {address}, telephone {phone}, "
            "email {email}, account {iban}, on {date}.")
    assert _sanitize_template(body, REQUIRED_SLOTS) is not None


def test_repeated_slot_splices_byte_exact_spans():
    """A {person} used twice yields two byte-exact PERSON spans (gold integrity under repetition)."""
    body = ("{person} confirms that {person} ({nino}) resides at {address}, telephone {phone}, "
            "email {email}, account {iban}, on {date}.")

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
    body = "{person} {nino} {address} {phone} {email} {iban} {date} {ssn}"  # unknown {ssn}
    assert _sanitize_template(body, REQUIRED_SLOTS) is None


def test_sanitizer_rejects_digits_outside_slots():
    """A literal digit the model smuggled into the prose is rejected (could masquerade as PII)."""
    body = "{person} {nino} {address} {phone} {email} {iban} {date} amount 1500 pounds"
    assert _sanitize_template(body, REQUIRED_SLOTS) is None


def test_sanitizer_rejects_stray_brace():
    body = "{person} {nino} {address} {phone} {email} {iban} {date} extra {"
    assert _sanitize_template(body, REQUIRED_SLOTS) is None


def test_sanitizer_rejects_leaked_markup():
    body = "```json {person} {nino} {address} {phone} {email} {iban} {date}```"
    assert _sanitize_template(body, REQUIRED_SLOTS) is None


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_fake_bodies_are_all_acceptable(seed):
    """Guard the fixtures themselves stay valid templates."""
    body = FakeNarrator.BODIES[seed % len(FakeNarrator.BODIES)]
    assert _sanitize_template(body, REQUIRED_SLOTS) is not None
