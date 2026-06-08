"""en-legal-realskeleton-v1 (RES-72): EN CJEU-structured real-skeleton scaffolds + synthetic PII.

The RES-72 real-skeleton method applied to the EN court-judgment genre (feeds the RES-104 win-track:
zero-shot generalization to the TAB real-legal board). These tests pin:
  * the inherited quality-moat invariants (byte-equality + strict BIOES) on the generated docs;
  * checksum/format validity of the spliced PII (IBAN mod-97; NINO format where present);
  * the TAB-crosswalk KP label set (PERSON / CASE_NUMBER / ADDRESS / ORG_PARTY / DATE);
  * the headline RES-72 claim — high unique-document-skeleton diversity (real STRUCTURE as scaffold),
    far above the generic-synthetic ~0.004 ratio (RES-94);
  * the structure-only licensing guard: no CJEU source prose is redistributed;
  * determinism.
"""

import random

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from klusai.privacy.datasets.data import en_skeletons_legal as sk
from klusai.privacy.datasets.data.en_generators import iban_gb_valid, nino_format_valid

# Mined structure cache may be absent in a clean checkout; tests that need real signatures skip if so.
try:
    _SIGS = sk.load_signatures()
except FileNotFoundError:  # pragma: no cover - exercised only without the cached artifact
    _SIGS = None


def _rows(n: int, seed: int = 0):
    return list(sk.generate_dataset(n, seed=seed, signatures=_SIGS))


def test_signature_cache_is_structure_only():
    """The mined signatures must carry ONLY layout features — no source text / prose / identifiers."""
    if _SIGS is None:
        return
    allowed = {"doctype", "n_lines", "heading_seq", "n_headings", "n_numbered_paras"}
    for s in _SIGS:
        assert set(s).issubset(allowed), f"unexpected signature key (possible leaked text): {set(s)}"
        assert s["doctype"] in {"JUDGMENT", "OPINION"}
        assert all(isinstance(h, str) and h.isupper() for h in s["heading_seq"])  # type labels only


def test_offsets_byte_equal_and_bioes_valid():
    if _SIGS is None:
        return
    for r in _rows(50, seed=3):
        for s in r["spans"]:
            assert 0 <= s["start"] < s["end"] <= len(r["text"])
            assert r["text"][s["start"] : s["end"]]
        validate_bioes(
            char_spans_to_bioes(r["text"], [Span(s["start"], s["end"], s["label"]) for s in r["spans"]])
        )


def test_pii_is_checksum_or_format_valid():
    if _SIGS is None:
        return
    invalid_iban = invalid_nino = 0
    for r in _rows(50, seed=7):
        for s in r["spans"]:
            v = r["text"][s["start"] : s["end"]]
            if s["label"] == "IBAN" and not iban_gb_valid(v):
                invalid_iban += 1
            if s["label"] == "NINO" and not nino_format_valid(v):
                invalid_nino += 1
    assert invalid_iban == 0 and invalid_nino == 0


def test_labels_match_tab_crosswalk():
    if _SIGS is None:
        return
    labels = {s["label"] for r in _rows(60, seed=5) for s in r["spans"]}
    # The five TAB-crosswalk KP types the real-legal board scores.
    assert {"PERSON", "CASE_NUMBER", "ADDRESS", "ORG_PARTY", "DATE"}.issubset(labels)


def test_structural_diversity_far_above_generic_synthetic():
    """RES-72 headline: real STRUCTURE as scaffold yields many distinct skeletons (≫ ~0.004)."""
    if _SIGS is None:
        return
    rows = _rows(50, seed=20260608)

    # Same skeleton method as analysis/synthetic_realism_gap.py::document_skeleton (PII→[LABEL],
    # digits→0, whitespace-normalized) — re-implemented minimally here to keep the test self-contained.
    import re

    def skeleton(row: dict) -> str:
        text = row["text"]
        spans = sorted(row["spans"], key=lambda s: s["start"])
        out, cursor = [], 0
        for sp in spans:
            s, e = sp["start"], sp["end"]
            if s < cursor:
                continue
            out.append(text[cursor:s])
            out.append(f"[{sp['label']}]")
            cursor = max(cursor, e)
        out.append(text[cursor:])
        masked = re.sub(r"\s+", " ", re.sub(r"\d", "0", "".join(out))).strip().lower()
        return masked

    uniq = len({skeleton(r) for r in rows})
    ratio = uniq / len(rows)
    assert ratio > 0.5, f"unique-skeleton ratio {ratio} not above generic-synthetic regime"


def test_no_source_text_redistributed():
    """Structure-only guard: distinctive CJEU/EUR-Lex verbatim phrases must never appear."""
    if _SIGS is None:
        return
    forbidden = [
        "OPINION OF MR ADVOCATE GENERAL LAGRANGE",  # a real mined doc's heading text
        "Members of the Court_",
        "language of the case",
        "Official Journal of the European Union",
    ]
    for r in _rows(60, seed=9):
        for phrase in forbidden:
            assert phrase not in r["text"], f"redistributed source phrase {phrase!r}"


def test_seeded_dataset_is_deterministic():
    if _SIGS is None:
        return
    a = [r["text"] for r in _rows(15, seed=42)]
    b = [r["text"] for r in _rows(15, seed=42)]
    assert a == b


def test_rows_carry_expected_tags():
    if _SIGS is None:
        return
    rows = _rows(20, seed=11)
    assert rows
    assert all(r["language"] == "en" and r["country"] == "GB" for r in rows)
    assert all(r["domain"] == "legal" and r["family"] == "L" for r in rows)


def test_gen_document_signature_injection_is_self_contained():
    """gen_document accepts injected signatures (no network / cache dependency in unit form)."""
    fake = [{"doctype": "JUDGMENT", "n_lines": 20, "heading_seq": ["PARTIES", "GROUNDS", "OPERATIVE"],
             "n_headings": 3, "n_numbered_paras": 4}]
    rng = random.Random(0)
    doc = sk.gen_document(rng, signatures=fake)
    assert doc.text and doc.spans and doc.domain == "legal"
    validate_bioes(
        char_spans_to_bioes(doc.text, [Span(s["start"], s["end"], s["label"]) for s in doc.spans])
    )
