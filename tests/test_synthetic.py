"""synthetic.generate() stage-A: drives the merged LocalePack splice, gold spans at gen time."""

import pytest

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from europriv_bench.taxonomy import ENTITY_NAMES
from klusai.privacy.datasets.data.synthetic import GenConfig, generate

PACKS = ["ro", "en", "pl"]


@pytest.mark.parametrize("lang", PACKS)
def test_generate_yields_n_rows(lang):
    rows = list(generate(GenConfig(language=lang, n=25, seed=3)))
    assert len(rows) == 25
    for r in rows:
        assert r["language"] == lang
        assert r["text"] and isinstance(r["spans"], list)


@pytest.mark.parametrize("lang", PACKS)
def test_generate_byte_equality_and_bioes(lang):
    """Gold spans are byte-correct and project to valid BIOES (the inherited quality moat)."""
    for r in generate(GenConfig(language=lang, n=40, seed=7)):
        for s in r["spans"]:
            assert r["text"][s["start"]:s["end"]], "empty span"
            assert s["label"] in ENTITY_NAMES
        validate_bioes(char_spans_to_bioes(
            r["text"], [Span(s["start"], s["end"], s["label"]) for s in r["spans"]]
        ))


@pytest.mark.parametrize("lang", PACKS)
def test_generate_is_deterministic(lang):
    a = [r["text"] for r in generate(GenConfig(language=lang, n=12, seed=99))]
    b = [r["text"] for r in generate(GenConfig(language=lang, n=12, seed=99))]
    assert a == b


def test_generate_unknown_pack_fails_loud():
    with pytest.raises(KeyError):
        list(generate(GenConfig(language="zz", n=1)))


def test_generate_is_lazy_iterator():
    """generate returns an iterator (so a 50k volume need not be fully materialized to start)."""
    gen = generate(GenConfig(language="ro", n=5, seed=1))
    first = next(gen)
    assert first["language"] == "ro"
