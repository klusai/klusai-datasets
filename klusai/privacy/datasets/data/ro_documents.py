"""Offset-deterministic Romanian document generation (localized synthetic, template-based).

The panel's P0 on span fidelity: build documents by splicing PII values into template segments
and computing spans from the splice positions — so ``text[start:end] == value`` holds BY
CONSTRUCTION (no post-hoc NER, no LLM rewriting that could shift offsets, immune to the
same-length-substitution bug ``char_spans_to_bioes`` cannot catch). Every produced row is still
run through the strict ``char_spans_to_bioes`` + ``validate_bioes`` gate as a belt-and-braces check.

This is the ``ro-synthetic-v1`` track (pure localized synthetic, RO-native identifiers incl. CNP).
Real-skeleton gold (``ro-realskeleton-v1``) reuses the same splice mechanism over real document
structures — a later step.
"""

from __future__ import annotations

import random

from europriv_bench.national_id import validate_cnp

# ``Doc`` and ``_fill`` live in ``localepack`` (the splice IS the shared abstraction); re-exported
# here so existing imports (``from .ro_documents import Doc, _fill``) keep working.
from .localepack import ChecksummedID, Doc, LocalePack, _fill
from .ro_generators import (
    cui_valid,
    gen_cui,
    gen_iban_ro,
    gen_person,
    iban_ro_valid,
)

__all__ = ["Doc", "_fill", "TEMPLATES", "gen_document", "generate_dataset", "ro_pack"]

# Templates: {slot} markers map to (value-builder, KP label). Slots are always whitespace/
# punctuation separated so two entities never share a whitespace token.
TEMPLATES = [
    ("legal",
     "Subsemnatul {person}, CNP {cnp}, domiciliat în {address}, telefon {phone}, "
     "declar pe propria răspundere la data de {date}."),
    ("legal",
     "Contract încheiat între {person} (CNP {cnp}) și societatea cu CUI {cui}, "
     "cont IBAN {iban}, la {date}."),
    ("clinical",
     "Pacient: {person}, CNP {cnp}, internat la data de {date}. "
     "Telefon de contact: {phone}."),
    ("clinical",
     "Bilet de externare — {person}, CNP {cnp}, domiciliat în {address}."),
    ("admin",
     "Către {person}, email {email}, vă comunicăm că plata în contul {iban} "
     "a fost înregistrată la {date}."),
    ("general",
     "{person} ({email}, tel. {phone}) a solicitat o programare pentru {date} "
     "la adresa {address}."),
]


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Build a coherent set of slot → (value, KP-label)."""
    p = gen_person(rng)
    email = f"{p.first_name}.{p.last_name}@example.ro".lower()
    date = f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1990, 2024)}"
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "cnp": (p.cnp, "NATIONAL_ID"),
        "address": (p.address, "ADDRESS"),
        "phone": (p.phone, "PHONE"),
        "iban": (p.iban, "ACCOUNT_ID"),
        "email": (email, "EMAIL"),
        "date": (date, "DATE"),
        "cui": (gen_cui(rng), "COMPANY_ID"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated RO document. Delegates to the shared splice/byte-equality/BIOES gate.

    Behavior-preserving: ``fill_document`` runs the exact same ``_fill`` splice, byte-equality
    asserts, and strict ``char_spans_to_bioes`` + ``validate_bioes`` projection as before, with the
    same RNG call order (``rng.choice(TEMPLATES)`` then ``_fields(rng)``), so seeded output is
    unchanged.
    """
    return ro_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated RO documents ({text, spans, language, domain})."""
    return ro_pack.generate_dataset(n, seed=seed)


def _gen_cnp_selftest(rng: random.Random) -> str:
    """CNP draw for the self-test: a whole coherent person's CNP (county code + sex chosen together)."""
    return gen_person(rng).cnp


ro_pack = LocalePack(
    language="ro",
    name="Romanian",
    checksummed_ids=(
        ChecksummedID("CNP", _gen_cnp_selftest, validate_cnp),
        ChecksummedID("IBAN", gen_iban_ro, iban_ro_valid),
        ChecksummedID("CUI", gen_cui, cui_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
)
