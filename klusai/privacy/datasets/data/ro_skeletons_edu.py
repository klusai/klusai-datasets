"""ro-realskeleton-v1 — **family B**: Romanian academic-registry documents + synthetic PII.

The second, *independent* RO template family for the real-skeleton track (KLU-101). Where family A
(``ro_skeletons``) is **official correspondence / clinical-legal-administrative prose** (CNAS
discharge letter, services contract, declarație, administrative letter), family B is the
**academic / higher-education registry** genre: a university enrollment certificate
(``ADEVERINȚĂ DE STUDENT``), an academic transcript (``FOAIE MATRICOLĂ``), and a diploma supplement
record (``SUPLIMENT LA DIPLOMĂ``). These are record/registry documents — tabular course-and-grade
listings, matriculation numbers, academic-year context — not formal letters or contracts.

Independence (hard-gated by KLU-101, asserted in ``make check`` / ``test_ro_family_independence``):
  1. **Different genre** — academic registry vs official correspondence (genre label recorded on
     each row as ``family`` + ``genre``).
  2. **Disjoint skeleton 5-grams** — the fixed boilerplate shares no vocabulary with family A
     (academic-registry Romanian vs clinical/legal/admin Romanian); the token 5-gram Jaccard
     overlap between the two families' PII-masked skeletons must be ≤ 0.10.
  3. **Different field layout** — different field set/order, different section headers, and a
     different CNP context (the CNP sits in a *student matriculation* block, not a clinical
     patient / contract-party block); plus academic-only fields (matriculation number, faculty,
     specialization, study year, GPA) absent from family A.
  4. **Disjoint synthetic-subject pool** — a *disjoint* name pool (``EDU_*`` first/last names that
     do not appear in family A's ``ro_generators`` pools) so no name — and, asserted in tests, no
     CNP — is reused across families.

Offset-determinism / byte-equality / strict-BIOES are inherited unchanged from the shared
``LocalePack`` / ``fill_document`` gate. All identifiers are synthetic (valid-checksum CNP,
CNP-consistent DOB), so the artifact stays GDPR-clean and CC-BY-redistributable.
"""

from __future__ import annotations

import random
import unicodedata

from europriv_bench.national_id import parse_cnp, validate_cnp

from .localepack import ChecksummedID, LocalePack
from .ro_documents import Doc
from .ro_generators import COUNTIES, gen_cnp, gen_phone

GENRE = "academic registry (higher-education student records)"

# ---------------------------------------------------------------------------
# Disjoint synthetic-subject pool. These name lists are intentionally disjoint
# from ro_generators.{MALE_NAMES,FEMALE_NAMES,SURNAMES} (family A) so no subject
# name — and, asserted in tests, no CNP — is shared across the two families.
# ---------------------------------------------------------------------------
EDU_MALE_NAMES = ["Tudor", "Răzvan", "Sebastian", "Adrian", "Florin", "Marius", "Octavian", "Sorin"]
EDU_FEMALE_NAMES = ["Daniela", "Larisa", "Carmen", "Bianca", "Roxana", "Teodora", "Anca", "Mihaela"]
EDU_SURNAMES = ["Vasilescu", "Georgescu", "Marinescu", "Tudorache", "Dragomir", "Nistor",
                "Cojocaru", "Lungu"]

UNIVERSITIES = [
    "Universitatea Babeș-Bolyai", "Universitatea Politehnica", "Universitatea de Vest",
    "Universitatea Tehnică", "Universitatea Alexandru Ioan Cuza",
]
FACULTIES = [
    "Facultatea de Matematică și Informatică", "Facultatea de Drept",
    "Facultatea de Litere", "Facultatea de Științe Economice", "Facultatea de Inginerie",
]
SPECIALIZATIONS = [
    "Informatică", "Drept", "Filologie", "Cibernetică economică",
    "Automatică și calculatoare", "Administrarea afacerilor",
]
COURSES = [
    "Analiză matematică", "Programare", "Baze de date", "Algoritmi", "Economie generală",
    "Limba engleză", "Statistică", "Drept civil",
]


def _ascii(s: str) -> str:
    """ASCII-fold Romanian diacritics for realistic registry emails."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _matricol(rng: random.Random) -> str:
    """A student matriculation / registry number, e.g. '2021-INF-04812'."""
    return f"{rng.randint(2016, 2024)}-{rng.choice(['INF', 'DRT', 'LIT', 'ECO', 'ING'])}-{rng.randint(10000, 99999)}"


# Family B skeletons. Slots are whitespace/punctuation-separated so no two entities share a
# whitespace token (same invariant family A relies on). The fixed (non-slot) text is deliberately
# academic-registry Romanian — no overlap with family A's clinical/legal/admin boilerplate.
TEMPLATES = [
    ("education", """ADEVERINȚĂ DE STUDENT

{university} , {faculty}

Prin prezenta se adeverește că studentul/studenta {student} , născut(ă) la {dob} ,
înmatriculat(ă) sub numărul matricol {matricol} , având codul numeric personal {cnp} ,
urmează cursurile programului de studii {specialization} în anul {study_year} .
Prezenta servește la stabilirea drepturilor de asigurat și a fost eliberată la cerere.

Secretariat, contact: {phone} sau {email} ."""),

    ("education", """FOAIE MATRICOLĂ

{university}
{faculty} — programul {specialization}

Titular: {student}
Număr matricol: {matricol}
Cod numeric personal: {cnp}
Anul de studiu: {study_year}

Situația școlară (extras):
  {course1} — nota {grade1}
  {course2} — nota {grade2}
Media generală a anilor de studiu: {gpa} ."""),

    ("education", """SUPLIMENT LA DIPLOMĂ

Instituția emitentă: {university}
Domeniul / programul: {specialization} , {faculty}

Date de identificare a titularului:
  Nume și prenume: {student}
  Cod numeric personal: {cnp}
  Număr matricol: {matricol}
  E-mail instituțional: {email}

Calificarea a fost obținută în urma promovării examenului de finalizare a studiilor,
cu media {gpa} . Document generat din registrul electronic al instituției."""),
]


def _gen_student(rng: random.Random):
    """A coherent synthetic student drawn from the DISJOINT family-B name pool.

    Same coherence guarantees as family A's ``gen_person`` (CNP county == address county logic via
    the shared county code; CNP sex == name sex; DOB DERIVED from the CNP), but the name pool is
    disjoint from family A so no subject is shared across families.
    """
    code, _plate, _county = rng.choice(COUNTIES)
    sex = rng.choice(["M", "F"])
    first = rng.choice(EDU_MALE_NAMES if sex == "M" else EDU_FEMALE_NAMES)
    last = rng.choice(EDU_SURNAMES)
    # Students skew young: bias the birth year so the academic-year context is plausible.
    birth_year = rng.randint(1995, 2006)
    cnp = gen_cnp(rng, code, sex, birth_year=birth_year)
    y, m, d = parse_cnp(cnp).birth_date.split("-")
    dob = f"{d}.{m}.{y}"
    return first, last, sex, cnp, dob


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    first, last, _sex, cnp, dob = _gen_student(rng)
    return {
        "student": (f"{first} {last}", "PERSON"),
        "cnp": (cnp, "NATIONAL_ID"),
        "dob": (dob, "DATE"),  # DERIVED from the CNP → birthday matches the CNP
        "matricol": (_matricol(rng), "CASE_NUMBER"),
        "university": (rng.choice(UNIVERSITIES), "ORG_PARTY"),
        "faculty": (rng.choice(FACULTIES), "O"),         # not PII — plain registry text
        "specialization": (rng.choice(SPECIALIZATIONS), "O"),
        "study_year": (str(rng.randint(1, 4)), "O"),
        "course1": (rng.choice(COURSES), "O"),
        "course2": (rng.choice(COURSES), "O"),
        "grade1": (str(rng.randint(5, 10)), "O"),
        "grade2": (str(rng.randint(5, 10)), "O"),
        "gpa": (f"{rng.uniform(6.0, 9.99):.2f}", "O"),
        "phone": (gen_phone(rng), "PHONE"),
        "email": (_ascii(f"{first}.{last}").lower() + "@stud.example.ro", "EMAIL"),
    }


def _gen_cnp_selftest(rng: random.Random) -> str:
    return _gen_student(rng)[3]


# ro-realskeleton-v1 family B pack. Same checksum self-test contract as family A (CNP), so a
# generator that emits an invalid-checksum CNP fails loud.
ro_skeleton_edu_pack = LocalePack(
    language="ro",
    name="Romanian (real-skeleton, family B — academic registry)",
    checksummed_ids=(ChecksummedID("CNP", _gen_cnp_selftest, validate_cnp),),
    fields=_fields,
    templates=tuple(TEMPLATES),
    family="B",
    genre=GENRE,
)


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated family-B (academic-registry) RO document."""
    return ro_skeleton_edu_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated family-B RO documents ({text, spans, language, domain})."""
    return ro_skeleton_edu_pack.generate_dataset(n, seed=seed)
