"""RO document generation must be offset-correct and contain valid CNPs."""

from europriv_bench.national_id import validate_cnp
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from klusai.privacy.datasets.data.ro_documents import generate_dataset


def test_generated_docs_are_offset_correct_and_wellformed():
    docs = list(generate_dataset(50, seed=0))
    assert len(docs) == 50
    for d in docs:
        # offset correctness is asserted inside gen_document; re-check BIOES projection here
        validate_bioes(char_spans_to_bioes(d["text"], [Span(s["start"], s["end"], s["label"]) for s in d["spans"]]))
        assert d["language"] == "ro"


def test_cnp_spans_are_valid_cnps():
    seen_cnp = False
    for d in generate_dataset(50, seed=1):
        for s in d["spans"]:
            if s["label"] == "NATIONAL_ID":
                assert validate_cnp(d["text"][s["start"]:s["end"]])
                seen_cnp = True
    assert seen_cnp, "expected at least one CNP span across 50 docs"


def test_generation_is_deterministic():
    a = list(generate_dataset(10, seed=7))
    b = list(generate_dataset(10, seed=7))
    assert [r["text"] for r in a] == [r["text"] for r in b]
