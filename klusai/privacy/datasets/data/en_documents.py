"""Offset-deterministic English document generation (localized synthetic, template-based).

The ``en-synthetic-v1`` track: the English sibling of ``ro_documents`` / ``pl_documents``. Documents
splice coherent, valid-format English/UK PII into template segments; the shared
``localepack.fill_document`` enforces the same quality-moat invariants (byte-equality assert + strict
``char_spans_to_bioes`` + ``validate_bioes``).

Checksum self-tests cover only ids that actually define a checksum (IBAN-GB mod-97, payment card
Luhn). NINO and SSN are format-valid only — the schemes define no arithmetic checksum, so we do not
fake one (documented under the pack's ``no_checksum_ids``).

Slots are whitespace/punctuation-separated so two entities never share a whitespace token.
"""

from __future__ import annotations

import random

from .en_generators import (
    card_valid,
    gen_card,
    gen_iban_gb,
    gen_person,
    iban_gb_valid,
)
from .localepack import ChecksummedID, Doc, LocalePack

COMPANIES = ["Acme Ltd", "Globex plc", "Initech Ltd", "MediCare Ltd"]
HOSPITALS = ["Royal Infirmary", "General Hospital", "University Hospital"]
CONDITIONS = [
    "essential hypertension", "type 2 diabetes", "community-acquired pneumonia",
    "chronic gastritis", "acute bronchitis",
]

TEMPLATES = [
    ("legal",
     "I, the undersigned {person}, National Insurance number {nino}, residing at {address}, "
     "telephone {phone}, hereby declare the foregoing to be true on {date}."),
    ("legal",
     "Agreement made between {person} (NINO {nino}) and {company}, "
     "account IBAN {iban}, dated {date}."),
    ("clinical",
     "Patient: {person}, NHS contact {phone}, admitted on {date}. "
     "Presenting condition: {condition}."),
    ("clinical",
     "Discharge summary — {person}, residing at {address}, diagnosis: {condition}."),
    ("admin",
     "Dear {person}, email {email}, we confirm that the payment to account {iban} "
     "was registered on {date}."),
    ("general",
     "{person} ({email}, tel. {phone}) requested an appointment for {date} "
     "at {address}, paid by card {card}."),
]


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Build a coherent set of slot → (value, KP-label)."""
    p = gen_person(rng)
    email = f"{p.first_name}.{p.last_name}@example.co.uk".lower()
    date = f"{rng.randint(1990, 2024)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "nino": (p.nino, "NATIONAL_ID"),
        "address": (p.address, "ADDRESS"),
        "phone": (p.phone, "PHONE"),
        "iban": (p.iban, "ACCOUNT_ID"),
        "card": (p.card, "ACCOUNT_ID"),
        "email": (email, "EMAIL"),
        "date": (date, "DATE"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated EN document (shared splice/byte-equality/strict-BIOES gate)."""
    return en_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated EN documents ({text, spans, language, domain})."""
    return en_pack.generate_dataset(n, seed=seed)


en_pack = LocalePack(
    language="en",
    name="English",
    checksummed_ids=(
        ChecksummedID("IBAN-GB", gen_iban_gb, iban_gb_valid),
        ChecksummedID("CARD", gen_card, card_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
    # NINO and SSN define no arithmetic checksum — format-valid only, never faked into the self-test.
    no_checksum_ids=("NINO (format-valid)", "SSN (format-valid)", "phone (+44)"),
)
