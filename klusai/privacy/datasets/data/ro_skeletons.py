"""ro-realskeleton-v1: faithful real-structure Romanian documents + synthetic PII.

Upgrade over `ro_documents` (the toy `ro-synthetic-v1` track): these mirror the STRUCTURE and
boilerplate of real Romanian official document types — the CNAS `SCRISOARE MEDICALĂ` discharge
letter, a services contract, a `DECLARAȚIE PE PROPRIA RĂSPUNDERE`, an administrative letter.
Because the skeletons are authored faithful reproductions of *public document structure* (not
scraped real records), there is **no residual real PII by construction** — every identifier is
synthetic — so the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a
quality spot-check, not a personal-data hunt.

Offset-determinism is inherited from `ro_documents._fill` (splice → exact spans → byte-equality
assert → strict BIOES projection). The synthetic-context (`ro-synthetic-v1`) vs real-context
(this) gap is the Paper-2 measurement.
"""

from __future__ import annotations

import random
import re
import unicodedata

from europriv_bench.national_id import validate_cnp

from .localepack import ChecksummedID, LocalePack
from .ro_documents import Doc
from .ro_generators import COUNTIES, cui_valid, gen_ci, gen_cui, gen_person


def _ascii(s: str) -> str:
    """ASCII-fold Romanian diacritics (ă→a, î/â→i/a, ș→s, ț→t) for realistic emails."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

HOSPITALS = ["Spitalul Clinic Județean", "Spitalul Municipal", "Spitalul Clinic de Urgență"]
COMPANIES = ["SC ExempluServ SRL", "SC TehnoPlus SRL", "SC ContabExpert SRL", "SC MediCare SRL"]
CONDITIONS = [
    "hipertensiune arterială esențială", "diabet zaharat tip 2", "pneumonie comunitară",
    "gastrită cronică", "lombosciatică", "bronșită acută",
]
SECTIONS = ["Medicină Internă", "Cardiologie", "Chirurgie Generală", "Neurologie"]

# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two
# entities share a whitespace token.
TEMPLATES = [
    ("clinical", """SCRISOARE MEDICALĂ

{hospital} — Secția {section}

Pacient: {patient}
CNP: {cnp} , Serie/nr. act identitate: {ci}
Data nașterii: {dob} , Cod asigurat: {cass}
Domiciliu: {address}
Telefon: {phone}

Diagnostic principal: {condition} .
Istoricul bolii: {pacient_word} s-a prezentat în data de {date} acuzând simptomatologia descrisă.
Recomandări la externare: tratament conform schemei, control peste 30 de zile.

Medic curant: Dr. {doctor}
Data întocmirii: {date}"""),

    ("legal", """CONTRACT DE PRESTĂRI SERVICII
Nr. {contractno} din {date}

Părțile contractante:
1. {company} , cu sediul în {address2} , CUI {cui} , cont IBAN {iban} , reprezentată de {doctor} ;
2. {patient} , CNP {cnp} , {domiciliat} în {address} , telefon {phone} , e-mail {email} .

Obiectul contractului îl constituie prestarea serviciilor convenite de părți.
Prezentul contract s-a încheiat astăzi, {date} , în două exemplare."""),

    ("legal", """DECLARAȚIE PE PROPRIA RĂSPUNDERE

{subsemnat} {patient} , CNP {cnp} , {posesor} actului de identitate seria/nr. {ci} ,
{domiciliat} în {address} , telefon {phone} , e-mail {email} , declar pe propria răspundere,
cunoscând prevederile legale privind falsul în declarații, că datele furnizate sunt reale.

Data: {date}
Semnătura: ____________"""),

    ("admin", """Către: {patient}
Adresa: {address}

Ref: dosarul nr. {contractno} / {date}

{salutation} {patient} , vă comunicăm că solicitarea dumneavoastră a fost
înregistrată. Pentru informații suplimentare ne puteți contacta la {phone} sau {email} .

Cu stimă,
{doctor}
{company}
{date}"""),
]


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    patient = gen_person(rng)
    doctor = gen_person(rng)
    _, _, county = rng.choice(COUNTIES)
    m = patient.sex == "M"  # Romanian gender agreement for boilerplate (not PII → label "O")
    return {
        "subsemnat": ("Subsemnatul" if m else "Subsemnata", "O"),
        "domiciliat": ("domiciliat" if m else "domiciliată", "O"),
        "posesor": ("posesor al" if m else "posesoare a", "O"),  # genitive article agrees w/ posesor(-oare)
        "salutation": ("Stimate domnule" if m else "Stimată doamnă", "O"),
        "pacient_word": ("Pacientul" if m else "Pacienta", "O"),
        "patient": (f"{patient.first_name} {patient.last_name}", "PERSON"),
        "doctor": (f"{doctor.first_name} {doctor.last_name}", "PERSON"),
        "cnp": (patient.cnp, "NATIONAL_ID"),
        "ci": (gen_ci(rng), "NATIONAL_ID"),
        "cass": (patient.cnp, "NATIONAL_ID"),  # cod unic de asigurare = CNP (real RO practice)
        "dob": (patient.dob, "DATE"),  # DERIVED from the CNP → birthday matches the CNP
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.ro", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "cui": (gen_cui(rng), "COMPANY_ID"),
        "company": (f"{rng.choice(COMPANIES)}", "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} {county}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "section": (rng.choice(SECTIONS), "O"),   # not PII — rendered as plain text, no span
        "contractno": (f"{rng.randint(100,9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(1,28):02d}.{rng.randint(1,12):02d}.{rng.randint(2018,2025)}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure RO document.

    Behavior-preserving delegation to the shared splice/byte-equality/strict-BIOES gate (same RNG
    call order: ``rng.choice(TEMPLATES)`` then ``_fields(rng)``; non-PII "O" slots dropped before
    projection — identical to the previous inline implementation).
    """
    return ro_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated faithful-structure RO documents ({text, spans, language, domain}).

    Family A only (official-correspondence genre). For the published ``ro-realskeleton-v1`` config —
    which now spans **two independent template families** (KLU-101) — use
    :func:`generate_combined_dataset`.
    """
    return ro_skeleton_pack.generate_dataset(n, seed=seed)


def generate_combined_dataset(n_per_family: int, seed: int = 0):
    """Yield ``2 * n_per_family`` rows: family A then family B, each row tagged with its ``family``.

    The two families draw from **disjoint subject pools** (different name lists) and use independent
    seeds, so no synthetic subject is shared across families. Pre-register ``n_per_family`` so the
    per-family protector-leak Wilson upper bound is ≤ 0.02 at ≈0 leak (KLU-101 — typically ≥150–200
    distinct subjects/family).
    """
    from .ro_skeletons_edu import ro_skeleton_edu_pack

    # Distinct seeds per family so the two PII streams never coincide.
    yield from ro_skeleton_pack.generate_dataset(n_per_family, seed=seed)
    yield from ro_skeleton_edu_pack.generate_dataset(n_per_family, seed=seed + 1)


# --------------------------------------------------------------------------- #
# KLU-101 independence gate: token 5-gram Jaccard overlap between the two families'
# fixed skeleton text (PII slots masked). Computed from the template literals so it is a
# deterministic, falsifiable hard gate (asserted in make check), not eyeballing.
# --------------------------------------------------------------------------- #
_SLOT_RE = re.compile(r"\{[a-z0-9_]+\}")


def _masked_skeleton_tokens(template: str) -> list[str]:
    """Tokenize a template's FIXED text with every PII ``{slot}`` collapsed to a single ``§`` mask.

    Masking the slots is what makes this a comparison of *skeleton boilerplate* (the authored fixed
    text) rather than of the synthetic PII values — two families could share a slot name yet have
    entirely disjoint surrounding prose.
    """
    masked = _SLOT_RE.sub(" § ", template)
    # Lowercase word/number tokens; keep the mask sentinel. Punctuation is dropped (we compare prose
    # n-grams, not layout punctuation, so the overlap reflects shared *wording*).
    return [t for t in re.findall(r"§|\w+", masked.lower())]


def _family_5grams(templates: tuple[tuple[str, str], ...]) -> set[tuple[str, ...]]:
    """Union of token 5-grams across all of a family's masked skeletons."""
    grams: set[tuple[str, ...]] = set()
    for _domain, template in templates:
        toks = _masked_skeleton_tokens(template)
        grams.update(tuple(toks[i:i + 5]) for i in range(len(toks) - 4))
    return grams


def family_5gram_jaccard() -> float:
    """Token 5-gram Jaccard overlap between family A and family B masked skeletons (KLU-101 gate).

    Must be ≤ 0.10 for the two families to count as *independent* (different document genre with
    disjoint boilerplate). Returns the actual measured overlap.
    """
    from .ro_skeletons_edu import TEMPLATES as TEMPLATES_B

    a = _family_5grams(tuple(TEMPLATES))
    b = _family_5grams(tuple(TEMPLATES_B))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _gen_cnp_selftest(rng: random.Random) -> str:
    return gen_person(rng).cnp


# ro-realskeleton-v1 pack. CI (seria + număr) has no national checksum, so it's documented under
# ``no_checksum_ids`` rather than faked into the self-test.
# Genre label for family A (KLU-101 independence record): official correspondence — clinical
# discharge letter, services contract, declarație, administrative letter. Family B
# (``ro_skeletons_edu``) is the *independent* academic-registry genre.
GENRE = "official correspondence (clinical / legal / administrative)"

ro_skeleton_pack = LocalePack(
    language="ro",
    name="Romanian (real-skeleton, family A — official correspondence)",
    checksummed_ids=(
        ChecksummedID("CNP", _gen_cnp_selftest, validate_cnp),
        ChecksummedID("CUI", gen_cui, cui_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
    no_checksum_ids=("CI",),  # Romanian ID-card seria/număr carries no published checksum
    family="A",
    genre=GENRE,
)
