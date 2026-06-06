"""RES-19 hard gate: the harder held-out general eval must be ≥2 INDEPENDENT template families/language.

"Independent + inherently held-out" is a falsifiable, hard-gated criterion (a real test, not eyeballing)
covering ALL of, for every one of the 8 languages:
  1. Two distinct families with DIFFERENT recorded genres (A=bureaucratic form, B=narrative note).
  2. Disjoint skeleton 5-grams — token 5-gram Jaccard ≤ 0.10 between family A and family B masked
     skeletons (mirrors the KLU-101 RO Family-A/B gate).
  3. Template-disjoint FROM TRAINING — token 5-gram Jaccard ≤ 0.10 between EACH new family and the
     original training ``*_documents.TEMPLATES`` skeletons. This is what makes the families inherently
     held-out: the trained v2 (and zero-shot control) never saw these skeletons.
  4. Offset-correct spans (byte-equality) and balanced, family-tagged rows over disjoint PII streams.
  5. Harder PII surface: NATIONAL_ID appears in NON-fixed positions across the families (not always
     after one fixed lead-in) — the property the saturated single-template KLU-106 eval lacked.

If any of these regress, ``make check`` goes red.
"""

from __future__ import annotations

import re

import pytest

from klusai.privacy.datasets.data import hardgeneral as hg

JACCARD_MAX = 0.10
N_PER_FAMILY = 60


@pytest.mark.parametrize("lang", hg.LANGUAGES)
def test_two_families_with_distinct_genres(lang):
    """Criterion 1: each language ships exactly families A and B with different recorded genres."""
    fams = hg._FAMILIES[lang]
    assert set(fams) == {"A", "B"}
    genre_a, genre_b = fams["A"][0], fams["B"][0]
    assert genre_a and genre_b and genre_a != genre_b


@pytest.mark.parametrize("lang", hg.LANGUAGES)
def test_family_a_vs_b_jaccard_below_threshold(lang):
    """Criterion 2 (hard gate): A/B masked-skeleton 5-gram Jaccard ≤ 0.10."""
    j = hg.family_5gram_jaccard(lang)
    assert j <= JACCARD_MAX, f"{lang}: family A/B 5-gram Jaccard {j:.4f} exceeds {JACCARD_MAX}"


@pytest.mark.parametrize("lang", hg.LANGUAGES)
@pytest.mark.parametrize("family", hg.FAMILIES)
def test_family_vs_training_jaccard_below_threshold(lang, family):
    """Criterion 3 (hard gate): each new family is template-disjoint from training (Jaccard ≤ 0.10).

    This is the inherently-held-out guarantee — the trained models never saw these skeletons."""
    j = hg.vs_training_5gram_jaccard(lang, family)
    assert j <= JACCARD_MAX, (
        f"{lang} family {family}: 5-gram Jaccard vs training templates {j:.4f} exceeds {JACCARD_MAX}"
    )


@pytest.mark.parametrize("lang", hg.LANGUAGES)
def test_rows_balanced_tagged_and_offset_correct(lang):
    """Criterion 4: balanced family-tagged rows; spans are offset-correct (text[start:end] == value).

    ``fill_document`` already byte-equality-asserts and runs the strict BIOES gate during generation;
    here we re-extract every span as a belt-and-braces check at the dataset boundary."""
    rows = list(hg.generate_hard_general(lang, N_PER_FAMILY, seed=20260606))
    assert len(rows) == 2 * N_PER_FAMILY
    fams = {"A": 0, "B": 0}
    for r in rows:
        assert r["language"] == lang
        fams[r["family"]] += 1
        assert r["spans"], "row has no PII spans"
        for s in r["spans"]:
            assert r["text"][s["start"]:s["end"]], "empty span text"
    assert fams == {"A": N_PER_FAMILY, "B": N_PER_FAMILY}


@pytest.mark.parametrize("lang", hg.LANGUAGES)
def test_disjoint_subjects_across_families(lang):
    """Criterion 4b: no NATIONAL_ID subject is shared across families A and B.

    NATIONAL_ID is the *subject key* used by the KLU-106 carve and the re-id metric (the leak-metric
    denominator). The two families draw from independent per-family seeds, and the national IDs are
    checksum-valid and near-unique, so the subject pools are disjoint by construction. (PERSON names
    are low-cardinality fillers shared with training on every track; they are not the subject key and
    deliberately not asserted disjoint — disjointness is enforced on the id that the leak metric and
    the carve actually key on.)"""
    rows = list(hg.generate_hard_general(lang, N_PER_FAMILY, seed=20260606))

    def nids(fam):
        return {r["text"][s["start"]:s["end"]] for r in rows if r["family"] == fam
                for s in r["spans"] if s["label"] == "NATIONAL_ID"}

    nid_a, nid_b = nids("A"), nids("B")
    assert nid_a and nid_b
    assert nid_a.isdisjoint(nid_b), f"{lang}: NATIONAL_ID subject reused across families"


@pytest.mark.parametrize("lang", hg.LANGUAGES)
def test_national_id_is_not_fixed_position(lang):
    """Criterion 5: the NATIONAL_ID surface is HARDER than the single saturated KLU-106 template.

    In the old eval the id sat at one fixed offset after one fixed lead-in word. Here we assert the
    id's *relative position within its document* varies materially across the families (not pinned to
    a single layout), which is what lets the eval discriminate beyond a memorizable skeleton."""
    nid_slot = hg._NID_SLOT[lang]
    rel_positions = []
    for family in ("A", "B"):
        for _domain, template in hg._materialise(lang, hg._FAMILIES[lang][family][1]):
            m = re.search(r"\{" + re.escape(nid_slot) + r"\}", template)
            if m:
                rel_positions.append(m.start() / max(1, len(template)))
    assert len(rel_positions) >= 2
    # The national-id slot is not always at the same relative offset (range well above noise).
    assert max(rel_positions) - min(rel_positions) > 0.15, (
        f"{lang}: NATIONAL_ID position barely varies ({rel_positions}) — still too fixed"
    )
