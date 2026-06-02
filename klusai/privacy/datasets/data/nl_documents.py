"""Offset-deterministic Dutch document generation (localized synthetic, template-based).

The ``nl-synthetic-v1`` track: the Dutch sibling of ``ro_documents``. Documents splice
checksum-valid Dutch PII (BSN, IBAN, …) into template segments; spans are computed from the splice
positions, so ``text[start:end] == value`` holds by construction. The shared
``localepack.fill_document`` runs the byte-equality assert and the strict ``char_spans_to_bioes`` +
``validate_bioes`` gate.

The KvK-nummer carries no public checksum (documented under ``no_checksum_ids``, never faked). Slots
are whitespace/punctuation-separated so two entities never share a whitespace token.
"""

from __future__ import annotations

import random

from .localepack import ChecksummedID, Doc, LocalePack
from .nl_generators import (
    bsn_valid,
    gen_iban_nl,
    gen_kvk,
    gen_person,
    iban_nl_valid,
)

COMPANIES = ["Voorbeeld B.V.", "TechPlus N.V.", "Administratie B.V.", "MediCare B.V."]
HOSPITALS = ["Academisch Ziekenhuis", "Streekziekenhuis", "Medisch Centrum"]
CONDITIONS = [
    "arteriële hypertensie", "diabetes type 2", "longontsteking",
    "chronische gastritis", "acute bronchitis",
]

TEMPLATES = [
    ("legal",
     "Ik, ondergetekende {person}, burgerservicenummer {bsn}, woonachtig te {address}, "
     "telefoon {phone}, verklaar het voorgaande naar waarheid op {date}."),
    ("legal",
     "Overeenkomst gesloten tussen {person} (BSN {bsn}) en het bedrijf {company}, "
     "KvK {kvk}, rekening IBAN {iban}, op {date}."),
    ("clinical",
     "Patiënt: {person}, BSN {bsn}, opgenomen op {date}. "
     "Contacttelefoon: {phone}."),
    ("clinical",
     "Ontslagbrief — {person}, woonachtig te {address}, diagnose: {condition}."),
    ("admin",
     "Geachte {person}, e-mail {email}, wij bevestigen dat de betaling op rekening {iban} "
     "op {date} is geregistreerd."),
    ("general",
     "{person} ({email}, tel. {phone}) heeft een afspraak aangevraagd voor {date} "
     "te {address}."),
]


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Build a coherent set of slot → (value, KP-label)."""
    p = gen_person(rng)
    # Dutch surnames carry tussenvoegsel ("van den Berg") → strip spaces for the email local-part.
    email = f"{p.first_name}.{p.last_name.replace(' ', '')}".lower() + "@example.nl"
    date = f"{rng.randint(1, 28):02d}-{rng.randint(1, 12):02d}-{rng.randint(1990, 2024)}"
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "bsn": (p.bsn, "NATIONAL_ID"),
        "address": (p.address, "ADDRESS"),
        "phone": (p.phone, "PHONE"),
        "iban": (p.iban, "ACCOUNT_ID"),
        "email": (email, "EMAIL"),
        "date": (date, "DATE"),
        "kvk": (gen_kvk(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated NL document (shared splice/byte-equality/strict-BIOES gate)."""
    return nl_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated NL documents ({text, spans, language, domain})."""
    return nl_pack.generate_dataset(n, seed=seed)


nl_pack = LocalePack(
    language="nl",
    name="Dutch",
    checksummed_ids=(
        ChecksummedID("BSN", lambda r: gen_person(r).bsn, bsn_valid),
        ChecksummedID("IBAN", gen_iban_nl, iban_nl_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
    no_checksum_ids=("KvK-nummer", "phone (+31)"),
)
