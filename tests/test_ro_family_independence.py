"""KLU-101 hard gate: the 2nd RO real-skeleton template family must be INDEPENDENT of family A.

"Independent" is a falsifiable, hard-gated criterion (a real test, not eyeballing) covering ALL of:
  1. Different document genre (recorded genre labels differ).
  2. Disjoint skeleton 5-grams — token 5-gram Jaccard overlap ≤ 0.10 between the two families'
     fixed (PII-masked) skeleton text.
  3. Different field layout (different field set / section headers / CNP context).
  4. Disjoint synthetic-subject pools — no CNP and no subject name reused across families.

If any of these regress, `make check` goes red.
"""

from europriv_bench.national_id import validate_cnp
from klusai.privacy.datasets.data.ro_generators import (
    FEMALE_NAMES,
    MALE_NAMES,
    SURNAMES,
)
from klusai.privacy.datasets.data.ro_skeletons import (
    GENRE as GENRE_A,
)
from klusai.privacy.datasets.data.ro_skeletons import (
    TEMPLATES as TEMPLATES_A,
)
from klusai.privacy.datasets.data.ro_skeletons import (
    family_5gram_jaccard,
    generate_combined_dataset,
)
from klusai.privacy.datasets.data.ro_skeletons_edu import (
    EDU_FEMALE_NAMES,
    EDU_MALE_NAMES,
    EDU_SURNAMES,
)
from klusai.privacy.datasets.data.ro_skeletons_edu import (
    GENRE as GENRE_B,
)
from klusai.privacy.datasets.data.ro_skeletons_edu import (
    TEMPLATES as TEMPLATES_B,
)

# Pre-registered per-family N (KLU-101): 250 docs/family so each family clears ≥150 — and in fact
# ≥190 — distinct valid-CNP subjects, giving a protector-leak Wilson upper bound ≤ 0.02 at ≈0
# observed leak. Family B yields one CNP subject per doc (250); family A's official-correspondence
# templates yield ~190 distinct valid-CNP subjects per 250 docs (not every template carries a CNP,
# and the CASS "cod asigurat" duplicate dedups to one subject — KLU-49).
PREREGISTERED_N_PER_FAMILY = 250


def test_genre_differs():
    """Criterion 1: the two families record DIFFERENT document genres."""
    assert GENRE_A and GENRE_B
    assert GENRE_A != GENRE_B


def test_skeleton_5gram_jaccard_below_threshold():
    """Criterion 2 (the hard gate): token 5-gram Jaccard overlap ≤ 0.10 on masked skeletons."""
    overlap = family_5gram_jaccard()
    assert overlap <= 0.10, f"family A/B skeleton 5-gram Jaccard {overlap:.4f} exceeds 0.10"


def test_field_layout_differs():
    """Criterion 3: different field set / section headers / CNP context.

    Family B carries academic-registry-only fields (matriculation number, faculty, specialization,
    study year) absent from family A, and uses different section headers. We assert the set of slot
    names and the set of section-header lines are not equal between the families.
    """
    import re

    def slots(templates):
        return {m for _d, t in templates for m in re.findall(r"\{([a-z0-9_]+)\}", t)}

    slots_a, slots_b = slots(TEMPLATES_A), slots(TEMPLATES_B)
    assert slots_a != slots_b
    # Academic-only fields present in B, absent in A.
    assert {"matricol", "specialization", "study_year"} <= slots_b
    assert not ({"matricol", "specialization", "study_year"} & slots_a)
    # Section-header / title lines (the first non-empty line of each template) are disjoint.
    def titles(templates):
        return {t.strip().splitlines()[0].strip() for _d, t in templates}
    assert titles(TEMPLATES_A).isdisjoint(titles(TEMPLATES_B))


def test_disjoint_subject_pools():
    """Criterion 4: no CNP and no subject name reused across the two families.

    Checked over the pre-registered per-family N so the disjointness claim holds at the size the
    dissociation is actually measured.
    """
    rows = list(generate_combined_dataset(PREREGISTERED_N_PER_FAMILY, seed=20260531))

    def values(fam, label):
        return {r["text"][s["start"]:s["end"]] for r in rows if r.get("family") == fam
                for s in r["spans"] if s["label"] == label}

    cnp_a, cnp_b = values("A", "NATIONAL_ID"), values("B", "NATIONAL_ID")
    assert cnp_a and cnp_b
    assert cnp_a.isdisjoint(cnp_b), "CNP reused across families — independence contaminated"
    assert all(validate_cnp(c) for c in cnp_b if c.isdigit() and len(c) == 13)

    names_a, names_b = values("A", "PERSON"), values("B", "PERSON")
    assert names_a and names_b
    assert names_a.isdisjoint(names_b), "subject name reused across families"

    # Name *pools* are disjoint by construction (the strongest guarantee).
    assert not (set(EDU_MALE_NAMES) & set(MALE_NAMES))
    assert not (set(EDU_FEMALE_NAMES) & set(FEMALE_NAMES))
    assert not (set(EDU_SURNAMES) & set(SURNAMES))


def test_preregistered_n_gives_leak_wilson_upper_bound_at_most_002():
    """The pre-registered N delivers a protector-leak Wilson upper bound ≤ 0.02 per family at 0 leak.

    This is the *exact* sizing requirement (KLU-101): per distinct VALID-CNP subject (the leak-metric
    denominator), at ≈0 observed leak the 95% Wilson upper bound must be ≤ 0.02. Computed with the
    harness metric (single source of truth) so the dataset size and the scored statistic agree.
    """
    from europriv_bench.metrics import cnp_leakage, wilson_interval
    from europriv_bench.spans import whitespace_tokens

    rows = list(generate_combined_dataset(PREREGISTERED_N_PER_FAMILY, seed=20260531))
    for fam in ("A", "B"):
        fr = [r for r in rows if r.get("family") == fam]
        # cnp_total = distinct VALID-CNP subjects after (doc, value) dedup (KLU-49).
        all_o = [["O"] * len(whitespace_tokens(r["text"])) for r in fr]
        total = int(cnp_leakage(fr, all_o)["cnp_total"])
        ub = wilson_interval(0, total)[1]
        assert total >= 150, f"family {fam}: only {total} distinct valid-CNP subjects"
        assert ub <= 0.02, f"family {fam}: leak Wilson UB {ub:.4f} > 0.02 at n={total}"
