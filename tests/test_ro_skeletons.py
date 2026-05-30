"""Faithful real-structure RO docs must be offset-correct, well-formed, and CNP-valid."""

from europriv_bench.national_id import validate_cnp
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from klusai.privacy.datasets.data.ro_skeletons import generate_dataset


def test_realskeleton_docs_offset_correct_and_wellformed():
    docs = list(generate_dataset(60, seed=0))
    assert len(docs) == 60
    domains = set()
    for d in docs:
        validate_bioes(char_spans_to_bioes(d["text"], [Span(s["start"], s["end"], s["label"]) for s in d["spans"]]))
        assert all(set(d["text"][s["start"]:s["end"]]) for s in d["spans"])  # non-empty spans
        domains.add(d["domain"])
    assert {"clinical", "legal", "admin"} <= domains


def test_cnp_spans_valid_and_deterministic():
    docs = list(generate_dataset(40, seed=3))
    cnps = [d["text"][s["start"]:s["end"]] for d in docs for s in d["spans"]
            if s["label"] == "NATIONAL_ID" and d["text"][s["start"]:s["end"]].isdigit()
            and len(d["text"][s["start"]:s["end"]]) == 13]
    assert cnps and all(validate_cnp(c) for c in cnps)
    assert [d["text"] for d in generate_dataset(5, seed=9)] == [d["text"] for d in generate_dataset(5, seed=9)]
