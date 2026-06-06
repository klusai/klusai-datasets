"""Faithful real-structure EE docs (RES-84) must be offset-correct, well-formed, isikukood-valid, and
the deliberate within-doc isikukood repeat must collapse to ONE subject (KLU-49 dedup)."""

import random

from europriv_bench.metrics import national_id_leakage
from europriv_bench.national_id import parse_national_id
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes, whitespace_tokens
from klusai.privacy.datasets.data.ee_skeletons import (
    ee_skeleton_pack,
    gen_document,
    generate_dataset,
)


def _iks(d):
    return [d["text"][s["start"]:s["end"]] for s in d["spans"]
            if s["label"] == "NATIONAL_ID"]


def test_realskeleton_docs_offset_correct_and_wellformed():
    docs = list(generate_dataset(80, seed=0))
    assert len(docs) == 80
    domains = set()
    for d in docs:
        assert d["country"] == "EE"  # so national_id_leakage dispatches to the isikukood validator
        validate_bioes(char_spans_to_bioes(d["text"], [Span(s["start"], s["end"], s["label"]) for s in d["spans"]]))
        assert all(set(d["text"][s["start"]:s["end"]]) for s in d["spans"])
        domains.add(d["domain"])
    assert {"clinical", "legal", "admin"} <= domains


def test_isikukood_spans_valid_and_decode_sex_dob():
    docs = list(generate_dataset(60, seed=3))
    iks = [c for d in docs for c in _iks(d)]
    assert iks
    for c in iks:
        info = parse_national_id(c, "EE")
        assert info.valid and info.disclosed_quasi_identifiers() == {"DATE_OF_BIRTH", "SEX"}


def test_checksummed_ids_self_test_passes():
    ee_skeleton_pack.checksum_self_test()


def test_gen_document_single_is_wellformed():
    d = gen_document(random.Random(11))
    assert d.text and d.domain in {"clinical", "legal", "admin"}
    validate_bioes(char_spans_to_bioes(d.text, [Span(s["start"], s["end"], s["label"]) for s in d.spans]))


def test_repeated_isikukood_collapses_to_one_subject():
    docs = list(generate_dataset(120, seed=7))
    repeated = 0
    distinct_subjects = set()
    textual_spans = 0
    for i, d in enumerate(docs):
        iks = _iks(d)
        textual_spans += len(iks)
        if len(iks) > len(set(iks)):
            repeated += 1
        for c in set(iks):
            distinct_subjects.add((i, c))
    assert repeated > 0, "no doc repeated its isikukood — dedup guard would be vacuous"
    assert textual_spans > len(distinct_subjects)

    all_o = [["O"] * len(whitespace_tokens(d["text"])) for d in docs]
    res = national_id_leakage(docs, all_o)
    assert res["decode_bearing_total"] == float(len(distinct_subjects))
    assert res["ee_total"] == float(len(distinct_subjects))
    assert res["leak_rate"] == 1.0
    # Each leaked isikukood discloses exactly DOB + SEX (2 QI) — once per subject.
    assert res["leaked_quasi_identifiers"] == 2.0 * len(distinct_subjects)
