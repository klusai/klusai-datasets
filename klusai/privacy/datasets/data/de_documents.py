"""Offset-deterministic German document generation (localized synthetic, template-based).

The ``de-synthetic-v1`` track: the German sibling of ``ro_documents``. Documents splice
checksum-valid German PII (Steuer-IdNr, USt-IdNr, IBAN, …) into template segments; spans are
computed from the splice positions, so ``text[start:end] == value`` holds by construction. The shared
``localepack.fill_document`` runs the byte-equality assert and the strict ``char_spans_to_bioes`` +
``validate_bioes`` gate.

Slots are whitespace/punctuation-separated so two entities never share a whitespace token.
"""

from __future__ import annotations

import random
import unicodedata

from .de_generators import (
    gen_iban_de,
    gen_person,
    gen_ust_idnr,
    iban_de_valid,
    steuer_id_valid,
    ust_idnr_valid,
)
from .localepack import ChecksummedID, Doc, LocalePack

COMPANIES = ["Beispiel GmbH", "TechPlus AG", "BüroService GmbH", "MediCare GmbH"]
HOSPITALS = ["Universitätsklinikum", "Städtisches Krankenhaus", "Klinikum am Park"]
CONDITIONS = [
    "arterielle Hypertonie", "Diabetes mellitus Typ 2", "Lungenentzündung",
    "chronische Gastritis", "akute Bronchitis",
]

TEMPLATES = [
    ("legal",
     "Ich, der Unterzeichnende {person}, Steuer-IdNr {steuerid}, wohnhaft in {address}, "
     "Telefon {phone}, erkläre Vorstehendes als wahrheitsgemäß am {date}."),
    ("legal",
     "Vertrag geschlossen zwischen {person} (Steuer-IdNr {steuerid}) und der Firma {company}, "
     "USt-IdNr {ustid}, Konto IBAN {iban}, am {date}."),
    ("clinical",
     "Patient: {person}, Steuer-IdNr {steuerid}, aufgenommen am {date}. "
     "Kontakttelefon: {phone}."),
    ("clinical",
     "Entlassungsbrief — {person}, wohnhaft in {address}, Diagnose: {condition}."),
    ("admin",
     "Sehr geehrte/r {person}, E-Mail {email}, wir bestätigen, dass die Zahlung auf das Konto {iban} "
     "am {date} verbucht wurde."),
    ("general",
     "{person} ({email}, Tel. {phone}) hat einen Termin für den {date} "
     "in {address} angefragt."),
]


def _ascii(s: str) -> str:
    """ASCII-fold German umlauts/ß for realistic emails."""
    s = s.replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    s = s.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Build a coherent set of slot → (value, KP-label)."""
    p = gen_person(rng)
    email = _ascii(f"{p.first_name}.{p.last_name}").lower() + "@example.de"
    date = f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1990, 2024)}"
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "steuerid": (p.steuer_id, "NATIONAL_ID"),
        "address": (p.address, "ADDRESS"),
        "phone": (p.phone, "PHONE"),
        "iban": (p.iban, "ACCOUNT_ID"),
        "email": (email, "EMAIL"),
        "date": (date, "DATE"),
        "ustid": (gen_ust_idnr(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated DE document (shared splice/byte-equality/strict-BIOES gate)."""
    return de_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated DE documents ({text, spans, language, domain})."""
    return de_pack.generate_dataset(n, seed=seed)


de_pack = LocalePack(
    language="de",
    name="German",
    checksummed_ids=(
        ChecksummedID("Steuer-IdNr", lambda r: gen_person(r).steuer_id, steuer_id_valid),
        ChecksummedID("USt-IdNr", gen_ust_idnr, ust_idnr_valid),
        ChecksummedID("IBAN", gen_iban_de, iban_de_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
    no_checksum_ids=("phone (+49)",),
)
