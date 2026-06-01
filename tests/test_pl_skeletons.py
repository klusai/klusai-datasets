"""Faithful real-structure PL docs must be offset-correct, well-formed, PESEL-valid, and the
deliberate within-doc PESEL repeat must collapse to ONE subject (KLU-49 dedup guard)."""

from europriv_bench.metrics import national_id_leakage
from europriv_bench.national_id import parse_national_id
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes, whitespace_tokens
from klusai.privacy.datasets.data.pl_skeletons import (
    gen_document,
    generate_dataset,
    pl_skeleton_pack,
)


def test_realskeleton_docs_offset_correct_and_wellformed():
    docs = list(generate_dataset(80, seed=0))
    assert len(docs) == 80
    domains = set()
    for d in docs:
        assert d["country"] == "PL"  # so national_id_leakage dispatches to the PESEL validator
        validate_bioes(char_spans_to_bioes(d["text"], [Span(s["start"], s["end"], s["label"]) for s in d["spans"]]))
        assert all(set(d["text"][s["start"]:s["end"]]) for s in d["spans"])  # non-empty spans
        domains.add(d["domain"])
    assert {"clinical", "legal", "admin"} <= domains


def test_pesel_spans_valid_decodeable_and_deterministic():
    docs = list(generate_dataset(60, seed=3))
    pesels = [d["text"][s["start"]:s["end"]] for d in docs for s in d["spans"]
              if s["label"] == "NATIONAL_ID" and d["text"][s["start"]:s["end"]].isdigit()
              and len(d["text"][s["start"]:s["end"]]) == 11]
    assert pesels
    for p in pesels:
        info = parse_national_id(p, "PL")
        assert info.valid and info.disclosed_quasi_identifiers() == {"DATE_OF_BIRTH", "SEX"}
    assert [d["text"] for d in generate_dataset(5, seed=9)] == [d["text"] for d in generate_dataset(5, seed=9)]


def test_checksummed_ids_self_test_passes():
    pl_skeleton_pack.checksum_self_test()


def test_gen_document_single_is_wellformed():
    import random
    d = gen_document(random.Random(11))
    assert d.text and d.domain in {"clinical", "legal", "admin"}
    validate_bioes(char_spans_to_bioes(d.text, [Span(s["start"], s["end"], s["label"]) for s in d.spans]))


def test_repeated_pesel_collapses_to_one_subject_no_double_count():
    """The discharge card repeats the patient PESEL (identity header + 'Identyfikator pacjenta').

    That is one subject, not two: national_id_leakage must dedup by (doc, country, value) so the
    repeat neither inflates the gold count nor lets a subject 'leak twice' (the KLU-49 CASS bug).
    """
    docs = list(generate_dataset(120, seed=7))
    # At least one clinical doc must actually carry the same PESEL twice (else the guard is vacuous).
    repeated = 0
    distinct_subjects = set()
    textual_pesel_spans = 0
    for i, d in enumerate(docs):
        pesels = [d["text"][s["start"]:s["end"]] for s in d["spans"]
                  if s["label"] == "NATIONAL_ID" and d["text"][s["start"]:s["end"]].isdigit()
                  and len(d["text"][s["start"]:s["end"]]) == 11]
        textual_pesel_spans += len(pesels)
        if len(pesels) > len(set(pesels)):
            repeated += 1
        for p in set(pesels):
            distinct_subjects.add((i, p))
    assert repeated > 0, "no doc repeated its PESEL — dedup guard would be vacuous"
    assert textual_pesel_spans > len(distinct_subjects)  # repeats exist at the textual level

    # all-O prediction → every subject leaks exactly once; total == distinct subjects (not spans).
    all_o = [["O"] * len(whitespace_tokens(d["text"])) for d in docs]
    res = national_id_leakage(docs, all_o)
    assert res["decode_bearing_total"] == float(len(distinct_subjects))
    assert res["pl_total"] == float(len(distinct_subjects))
    assert res["decode_bearing_missed"] == float(len(distinct_subjects))
    assert res["leak_rate"] == 1.0
    # Each leaked PESEL discloses exactly DOB + SEX (2 QI) — once per subject, not per mention.
    assert res["leaked_quasi_identifiers"] == 2.0 * len(distinct_subjects)
