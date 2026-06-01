"""Offset-deterministic Polish document generation (localized synthetic, template-based).

The ``pl-synthetic-v1`` track: the Polish sibling of ``ro_documents``. Documents are built by
splicing checksum-valid Polish PII (PESEL, NIP, IBAN, …) into template segments; spans are computed
from the splice positions, so ``text[start:end] == value`` holds by construction. The shared
``localepack.fill_document`` runs the byte-equality assert and the strict ``char_spans_to_bioes`` +
``validate_bioes`` gate — the same quality-moat invariants as RO.

Slots are whitespace/punctuation-separated so two entities never share a whitespace token (the
strict BIOES gate fails loud otherwise). Gender-agreement boilerplate (e.g. Pan/Pani) is filled but
labelled "O" so it is dropped before span projection.
"""

from __future__ import annotations

import random
import unicodedata

from .localepack import ChecksummedID, Doc, LocalePack
from .pl_generators import (
    gen_dowod,
    gen_iban_pl,
    gen_nip,
    gen_person,
    gen_regon9,
    iban_pl_valid,
    nip_valid,
    pesel_valid,
    regon9_valid,
)

COMPANIES = ["Przykład Sp. z o.o.", "TechPlus S.A.", "BiuroRach Sp. z o.o.", "MediCare Sp. z o.o."]
HOSPITALS = ["Szpital Wojewódzki", "Szpital Miejski", "Szpital Kliniczny"]
CONDITIONS = [
    "nadciśnienie tętnicze", "cukrzyca typu 2", "zapalenie płuc",
    "przewlekłe zapalenie żołądka", "ostre zapalenie oskrzeli",
]

# {slot} markers map to (value-builder, KP label).
TEMPLATES = [
    ("legal",
     "Ja, niżej podpisany {person}, PESEL {pesel}, zamieszkały pod adresem {address}, "
     "telefon {phone}, oświadczam zgodnie z prawdą w dniu {date}."),
    ("legal",
     "Umowa zawarta między {person} (PESEL {pesel}) a firmą {company}, NIP {nip}, "
     "rachunek IBAN {iban}, w dniu {date}."),
    ("clinical",
     "Pacjent: {person}, PESEL {pesel}, przyjęty w dniu {date}. "
     "Telefon kontaktowy: {phone}."),
    ("clinical",
     "Karta wypisowa — {person}, PESEL {pesel}, zamieszkały pod adresem {address}, "
     "rozpoznanie: {condition}."),
    ("admin",
     "Do {person}, e-mail {email}, informujemy, że wpłata na rachunek {iban} "
     "została zarejestrowana w dniu {date}."),
    ("general",
     "{person} ({email}, tel. {phone}) złożył wniosek o wizytę w dniu {date} "
     "pod adresem {address}."),
]


def _ascii(s: str) -> str:
    """ASCII-fold Polish diacritics (ł handled explicitly) for realistic emails."""
    s = s.replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Build a coherent set of slot → (value, KP-label)."""
    p = gen_person(rng)
    email = _ascii(f"{p.first_name}.{p.last_name}").lower() + "@example.pl"
    date = f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1990, 2024)}"
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "pesel": (p.pesel, "NATIONAL_ID"),
        "address": (p.address, "ADDRESS"),
        "phone": (p.phone, "PHONE"),
        "iban": (p.iban, "ACCOUNT_ID"),
        "email": (email, "EMAIL"),
        "date": (date, "DATE"),
        "nip": (gen_nip(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated PL document (shared splice/byte-equality/strict-BIOES gate)."""
    return pl_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated PL documents ({text, spans, language, domain})."""
    return pl_pack.generate_dataset(n, seed=seed)


pl_pack = LocalePack(
    language="pl",
    name="Polish",
    checksummed_ids=(
        ChecksummedID("PESEL", lambda r: gen_person(r).pesel, pesel_valid),
        ChecksummedID("NIP", gen_nip, nip_valid),
        ChecksummedID("REGON9", gen_regon9, regon9_valid),
        ChecksummedID("IBAN", gen_iban_pl, iban_pl_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
    no_checksum_ids=("phone (+48)", "dowód osobisty"),  # no published checksum
)

# Expose the no-checksum id generator so callers/tests can reference it (it is intentionally not in
# the checksum self-test — we never fake a checksum where none exists).
_NO_CHECKSUM_GENERATORS = {"dowód osobisty": gen_dowod}
