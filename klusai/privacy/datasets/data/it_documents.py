"""Offset-deterministic Italian document generation (localized synthetic, template-based).

The ``it-synthetic-v1`` track: the Italian sibling of ``ro_documents`` / ``pl_documents``. Documents
splice checksum-valid Italian PII (codice fiscale, partita IVA, IBAN, …) into template segments;
spans are computed from the splice positions, so ``text[start:end] == value`` holds by construction.
The shared ``localepack.fill_document`` runs the byte-equality assert and the strict
``char_spans_to_bioes`` + ``validate_bioes`` gate — the same quality-moat invariants as RO/PL/EN.

The **codice fiscale** is the critical-path decode-bearing identifier (KLU-105/106): the generator
emits checksum-valid CFs (validated against ``europriv_bench.national_id``, the single source of
truth), so a model trained here learns the correct CF invariant.

Slots are whitespace/punctuation-separated so two entities never share a whitespace token.
"""

from __future__ import annotations

import random
import unicodedata

from .it_generators import (
    codice_fiscale_valid,
    gen_iban_it,
    gen_partita_iva,
    gen_person,
    iban_it_valid,
    partita_iva_valid,
)
from .localepack import ChecksummedID, Doc, LocalePack

COMPANIES = ["Esempio S.r.l.", "TecnoPlus S.p.A.", "StudioRag S.r.l.", "MediCare S.r.l."]
HOSPITALS = ["Ospedale Civile", "Ospedale Maggiore", "Policlinico Universitario"]
CONDITIONS = [
    "ipertensione arteriosa", "diabete di tipo 2", "polmonite",
    "gastrite cronica", "bronchite acuta",
]

TEMPLATES = [
    ("legal",
     "Io sottoscritto {person}, codice fiscale {cf}, residente in {address}, "
     "telefono {phone}, dichiaro quanto sopra veritiero in data {date}."),
    ("legal",
     "Contratto stipulato tra {person} (codice fiscale {cf}) e la società {company}, "
     "partita IVA {piva}, conto IBAN {iban}, in data {date}."),
    ("clinical",
     "Paziente: {person}, codice fiscale {cf}, ricoverato in data {date}. "
     "Telefono di contatto: {phone}."),
    ("clinical",
     "Lettera di dimissione — {person}, codice fiscale {cf}, residente in {address}, "
     "diagnosi: {condition}."),
    ("admin",
     "Gentile {person}, e-mail {email}, confermiamo che il pagamento sul conto {iban} "
     "è stato registrato in data {date}."),
    ("general",
     "{person} ({email}, tel. {phone}) ha richiesto un appuntamento per il {date} "
     "presso {address}."),
]


def _ascii(s: str) -> str:
    """ASCII-fold Italian accents for realistic emails."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Build a coherent set of slot → (value, KP-label)."""
    p = gen_person(rng)
    email = _ascii(f"{p.first_name}.{p.last_name}").lower() + "@example.it"
    date = f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(1990, 2024)}"
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "cf": (p.codice_fiscale, "NATIONAL_ID"),
        "address": (p.address, "ADDRESS"),
        "phone": (p.phone, "PHONE"),
        "iban": (p.iban, "ACCOUNT_ID"),
        "email": (email, "EMAIL"),
        "date": (date, "DATE"),
        "piva": (gen_partita_iva(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated IT document (shared splice/byte-equality/strict-BIOES gate)."""
    return it_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated IT documents ({text, spans, language, domain})."""
    return it_pack.generate_dataset(n, seed=seed)


it_pack = LocalePack(
    language="it",
    name="Italian",
    checksummed_ids=(
        ChecksummedID("codice fiscale", lambda r: gen_person(r).codice_fiscale, codice_fiscale_valid),
        ChecksummedID("partita IVA", gen_partita_iva, partita_iva_valid),
        ChecksummedID("IBAN", gen_iban_it, iban_it_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
    no_checksum_ids=("phone (+39)",),  # Italian mobile numbers carry no published checksum
)
