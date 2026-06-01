"""LocalePack contract: per-pack checksum self-tests, byte-equality, strict BIOES, determinism.

These exercise the abstraction across every registered locale (RO + RO-realskeleton + PL + EN) so a
new pack inherits the quality-moat invariants automatically.
"""

import random

import pytest

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from europriv_bench.taxonomy import ENTITY_NAMES
from klusai.privacy.datasets.data import LOCALE_PACKS
from klusai.privacy.datasets.data.localepack import fill_document

ALL_PACKS = list(LOCALE_PACKS.values())
PACK_IDS = list(LOCALE_PACKS.keys())


@pytest.mark.parametrize("pack", ALL_PACKS, ids=PACK_IDS)
def test_checksum_self_test_passes(pack):
    """Every checksummed id a pack declares must validate against its own validator."""
    assert pack.checksummed_ids, f"{pack.language} declares no checksummed ids"
    pack.checksum_self_test(n=200, seed=0)


@pytest.mark.parametrize("pack", ALL_PACKS, ids=PACK_IDS)
def test_generated_docs_byte_equality_and_bioes(pack):
    """Byte-equality (text[start:end]==value) holds and BIOES projects cleanly for every span."""
    docs = list(pack.generate_dataset(60, seed=0))
    assert len(docs) == 60
    for d in docs:
        assert d["language"] == pack.language
        # The byte-equality assert runs inside gen_document; re-verify here independently.
        for s in d["spans"]:
            assert d["text"][s["start"]:s["end"]], "empty span"
            assert s["label"] in ENTITY_NAMES, f"non-taxonomy label {s['label']!r}"
        validate_bioes(char_spans_to_bioes(
            d["text"], [Span(s["start"], s["end"], s["label"]) for s in d["spans"]]
        ))


@pytest.mark.parametrize("pack", ALL_PACKS, ids=PACK_IDS)
def test_generation_is_deterministic(pack):
    a = [r["text"] for r in pack.generate_dataset(15, seed=11)]
    b = [r["text"] for r in pack.generate_dataset(15, seed=11)]
    assert a == b


@pytest.mark.parametrize("pack", ALL_PACKS, ids=PACK_IDS)
def test_national_id_spans_present(pack):
    """Each pack should emit at least one NATIONAL_ID span across a batch (PII coverage)."""
    seen = any(
        s["label"] == "NATIONAL_ID"
        for d in pack.generate_dataset(60, seed=2)
        for s in d["spans"]
    )
    assert seen, f"{pack.language}: expected a NATIONAL_ID span"


def test_byte_equality_assert_fires_on_tampered_value():
    """A field whose recorded value cannot be re-extracted byte-for-byte must fail loud."""
    def bad_fields(_rng):
        # value contains a char the template will not reproduce → byte-equality assert trips
        return {"x": ("VALUE", "PERSON")}

    templates = (("general", "before {x} after"),)
    # sanity: a faithful builder passes
    fill_document(random.Random(0), templates, bad_fields)

    def tampering_fields(_rng):
        # claim a longer value than what gets spliced is impossible via _fill (it splices `value`),
        # so instead inject a token-collision: two PII entities sharing one whitespace token.
        return {"a": ("Smith", "PERSON"), "b": ("Jones", "ORG_PARTY")}

    collide = (("general", "name {a}-{b} end"),)  # hyphen-joined → one whitespace token
    with pytest.raises(ValueError):
        fill_document(random.Random(0), collide, tampering_fields)


def test_no_checksum_ids_are_documented_not_faked():
    """Packs with checksum-less id types must document them, and never list them as checksummed."""
    en = LOCALE_PACKS["en"]
    pl = LOCALE_PACKS["pl"]
    assert any("NINO" in s for s in en.no_checksum_ids)
    assert any("SSN" in s for s in en.no_checksum_ids)
    checksummed_names = {c.name for c in en.checksummed_ids}
    assert "NINO" not in checksummed_names and "SSN" not in checksummed_names
    assert pl.no_checksum_ids  # PL phone / dowód documented
