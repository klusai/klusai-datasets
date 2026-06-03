"""legal-realskeleton-v1 (KLU-111): cleanly-licensed legal-domain real-structure RO docs + CNP.

The legal-domain real-skeleton track — EUR-Lex-style instrument / ECHR-style judgment / GDPR Art.15
DSAR response. STRUCTURE-ONLY (no source text reused), synthetic CNP-bearing PII. These tests pin:
  * the pack's checksum self-test (every CNP/CUI validates against europriv_bench);
  * country='RO' dispatch + valid, decode-bearing CNP (a leak discloses DOB+SEX+COUNTY);
  * per-distinct-subject re-id counting — the DSAR response repeats the applicant CNP, which MUST
    dedup to one subject (KLU-49), not inflate the gold count;
  * the offset / byte-equality / strict-BIOES invariants (inherited) + determinism;
  * the structure-only licensing guard: no source text is redistributed.
"""

import random

from europriv_bench.national_id import parse_national_id
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from klusai.privacy.datasets.data import ro_skeletons_legal as sk


def test_pack_checksum_self_test_passes():
    sk.ro_legal_skeleton_pack.checksum_self_test(n=400, seed=0)


def test_rows_carry_country_ro_and_legal_domain_and_family_tag():
    rows = list(sk.generate_dataset(60, seed=11))
    assert rows
    assert all(r["country"] == "RO" and r["language"] == "ro" for r in rows)
    assert all(r["domain"] == "legal" for r in rows)        # the legal-domain axis (KLU-111)
    assert all(r["family"] == "L" for r in rows)            # single authored legal family


def test_cnp_is_valid_and_decode_bearing():
    rows = list(sk.generate_dataset(80, seed=7))
    seen = 0
    for r in rows:
        for s in r["spans"]:
            if s["label"] == "NATIONAL_ID":
                value = r["text"][s["start"]:s["end"]]
                info = parse_national_id(value, "RO")
                assert info.valid and info.decode_bearing, value
                # A missed CNP discloses DOB+SEX+COUNTY (the dissociation re-id signal).
                assert info.disclosed_quasi_identifiers() == {"DATE_OF_BIRTH", "SEX", "COUNTY"}
                seen += 1
    assert seen > 0


def test_offsets_byte_equal_and_bioes_valid():
    """Inherited quality-moat invariants: every span re-extracts exactly + projects to valid BIOES."""
    for r in sk.generate_dataset(50, seed=3):
        spans = [Span(s["start"], s["end"], s["label"]) for s in r["spans"]]
        for s in r["spans"]:
            extract = r["text"][s["start"]:s["end"]]
            assert extract and 0 <= s["start"] < s["end"] <= len(r["text"])
        validate_bioes(char_spans_to_bioes(r["text"], spans))


def test_dsar_repeated_cnp_dedups_to_one_subject():
    """The GDPR Art.15 DSAR response repeats the applicant CNP (identity block + confirmation line).

    Per-distinct-subject counting (KLU-49): both occurrences carry the SAME value, so the document
    contributes exactly ONE distinct CNP subject — the repeat must not inflate the gold denominator.
    """
    rng = random.Random(0)
    saw_repeat = False
    for _ in range(400):
        doc = sk.gen_document(rng)
        if "RASPUNS LA CEREREA" not in doc.text:
            continue
        cnp_values = [doc.text[s["start"]:s["end"]] for s in doc.spans if s["label"] == "NATIONAL_ID"]
        # The DSAR template has two NATIONAL_ID slots ({cnp} + {cnp_confirm}) with identical value.
        assert len(cnp_values) == 2 and cnp_values[0] == cnp_values[1]
        assert len(set(cnp_values)) == 1  # one DISTINCT subject
        saw_repeat = True
    assert saw_repeat, "DSAR template (with repeated CNP) was never sampled"


def test_all_three_legal_document_types_appear():
    rng = random.Random(1)
    seen_titles = set()
    for _ in range(300):
        doc = sk.gen_document(rng)
        head = doc.text.splitlines()[0]
        seen_titles.add(head)
    # EUR-Lex-style instrument, ECHR-style judgment, GDPR Art.15 DSAR response.
    assert any("DECIZIE-CADRU" in t for t in seen_titles)
    assert any("CAUZA" in t and "IMPOTRIVA ROMANIEI" in t for t in seen_titles)
    assert any("RASPUNS LA CEREREA" in t for t in seen_titles)


def test_no_source_text_redistributed():
    """Structure-only guard: documents must not contain copyrighted EUR-Lex/ECHR boilerplate.

    A coarse but falsifiable check — the authored skeletons reproduce LAYOUT, not source text, so
    distinctive verbatim phrases from the real instruments must never appear. (The real ECHR formula
    is the French 'PAR CES MOTIFS, LA COUR'; ours is the authored Romanian 'PENTRU ACESTE MOTIVE'.)
    """
    forbidden = ["PAR CES MOTIFS", "FOR THESE REASONS", "THE EUROPEAN PARLIAMENT AND THE COUNCIL",
                 "Official Journal of the European Union", "© ECHR-CEDH"]
    for r in sk.generate_dataset(120, seed=5):
        for phrase in forbidden:
            assert phrase not in r["text"], f"redistributed source phrase {phrase!r}"


def test_seeded_dataset_is_deterministic():
    a = [r["text"] for r in sk.generate_dataset(15, seed=42)]
    b = [r["text"] for r in sk.generate_dataset(15, seed=42)]
    assert a == b
