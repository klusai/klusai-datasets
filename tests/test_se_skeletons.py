"""Faithful real-structure SE docs (RES-80) must be offset-correct, well-formed, personnummer-valid,
and the deliberate within-doc personnummer repeat must collapse to ONE subject (KLU-49 dedup)."""

import random

from europriv_bench.metrics import national_id_leakage
from europriv_bench.national_id import parse_national_id
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes, whitespace_tokens
from klusai.privacy.datasets.data.se_skeletons import (
    gen_document,
    generate_dataset,
    se_skeleton_pack,
)


def _pnrs(d):
    return [d["text"][s["start"]:s["end"]] for s in d["spans"]
            if s["label"] == "NATIONAL_ID"]


def test_realskeleton_docs_offset_correct_and_wellformed():
    docs = list(generate_dataset(80, seed=0))
    assert len(docs) == 80
    domains = set()
    for d in docs:
        assert d["country"] == "SE"  # so national_id_leakage dispatches to the personnummer validator
        validate_bioes(char_spans_to_bioes(d["text"], [Span(s["start"], s["end"], s["label"]) for s in d["spans"]]))
        assert all(set(d["text"][s["start"]:s["end"]]) for s in d["spans"])
        domains.add(d["domain"])
    assert {"clinical", "legal", "admin"} <= domains


def test_personnummer_spans_valid_and_decode_sex_dob():
    docs = list(generate_dataset(60, seed=3))
    pnrs = [p for d in docs for p in _pnrs(d)]
    assert pnrs
    for p in pnrs:
        info = parse_national_id(p, "SE")
        assert info.valid and info.disclosed_quasi_identifiers() == {"DATE_OF_BIRTH", "SEX"}


def test_checksummed_ids_self_test_passes():
    se_skeleton_pack.checksum_self_test()


def test_gen_document_single_is_wellformed():
    d = gen_document(random.Random(11))
    assert d.text and d.domain in {"clinical", "legal", "admin"}
    validate_bioes(char_spans_to_bioes(d.text, [Span(s["start"], s["end"], s["label"]) for s in d.spans]))


def test_repeated_personnummer_collapses_to_one_subject():
    docs = list(generate_dataset(120, seed=7))
    repeated = 0
    distinct_subjects = set()
    textual_spans = 0
    for i, d in enumerate(docs):
        pnrs = _pnrs(d)
        textual_spans += len(pnrs)
        if len(pnrs) > len(set(pnrs)):
            repeated += 1
        for p in set(pnrs):
            distinct_subjects.add((i, p))
    assert repeated > 0, "no doc repeated its personnummer — dedup guard would be vacuous"
    assert textual_spans > len(distinct_subjects)

    all_o = [["O"] * len(whitespace_tokens(d["text"])) for d in docs]
    res = national_id_leakage(docs, all_o)
    assert res["decode_bearing_total"] == float(len(distinct_subjects))
    assert res["se_total"] == float(len(distinct_subjects))
    assert res["leak_rate"] == 1.0
    # Each leaked personnummer discloses exactly DOB + SEX (2 QI) — once per subject.
    assert res["leaked_quasi_identifiers"] == 2.0 * len(distinct_subjects)
