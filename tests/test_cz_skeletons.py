"""Faithful real-structure CZ docs (RES-80) must be offset-correct, well-formed, rodné-číslo-valid,
and the deliberate within-doc rodné-číslo repeat must collapse to ONE subject (KLU-49 dedup)."""

import random

from europriv_bench.metrics import national_id_leakage
from europriv_bench.national_id import parse_national_id
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes, whitespace_tokens
from klusai.privacy.datasets.data.cz_skeletons import (
    cz_skeleton_pack,
    gen_document,
    generate_dataset,
)


def _rcs(d):
    return [d["text"][s["start"]:s["end"]] for s in d["spans"]
            if s["label"] == "NATIONAL_ID"]


def test_realskeleton_docs_offset_correct_and_wellformed():
    docs = list(generate_dataset(80, seed=0))
    assert len(docs) == 80
    domains = set()
    for d in docs:
        assert d["country"] == "CZ"  # so national_id_leakage dispatches to the rodné-číslo validator
        validate_bioes(char_spans_to_bioes(d["text"], [Span(s["start"], s["end"], s["label"]) for s in d["spans"]]))
        assert all(set(d["text"][s["start"]:s["end"]]) for s in d["spans"])
        domains.add(d["domain"])
    assert {"clinical", "legal", "admin"} <= domains


def test_rodne_cislo_spans_valid_and_decode_sex_dob():
    docs = list(generate_dataset(60, seed=3))
    rcs = [r for d in docs for r in _rcs(d)]
    assert rcs
    for r in rcs:
        info = parse_national_id(r, "CZ")
        assert info.valid and info.disclosed_quasi_identifiers() == {"DATE_OF_BIRTH", "SEX"}


def test_checksummed_ids_self_test_passes():
    cz_skeleton_pack.checksum_self_test()


def test_gen_document_single_is_wellformed():
    d = gen_document(random.Random(11))
    assert d.text and d.domain in {"clinical", "legal", "admin"}
    validate_bioes(char_spans_to_bioes(d.text, [Span(s["start"], s["end"], s["label"]) for s in d.spans]))


def test_repeated_rodne_cislo_collapses_to_one_subject():
    docs = list(generate_dataset(120, seed=7))
    repeated = 0
    distinct_subjects = set()
    textual_spans = 0
    for i, d in enumerate(docs):
        rcs = _rcs(d)
        textual_spans += len(rcs)
        if len(rcs) > len(set(rcs)):
            repeated += 1
        for r in set(rcs):
            distinct_subjects.add((i, r))
    assert repeated > 0, "no doc repeated its rodné číslo — dedup guard would be vacuous"
    assert textual_spans > len(distinct_subjects)

    all_o = [["O"] * len(whitespace_tokens(d["text"])) for d in docs]
    res = national_id_leakage(docs, all_o)
    assert res["decode_bearing_total"] == float(len(distinct_subjects))
    assert res["cz_total"] == float(len(distinct_subjects))
    assert res["leak_rate"] == 1.0
    assert res["leaked_quasi_identifiers"] == 2.0 * len(distinct_subjects)
