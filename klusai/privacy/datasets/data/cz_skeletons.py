"""cz-realskeleton-v1: faithful real-structure Czech documents + synthetic PII.

The Czech sibling of ``ro_skeletons`` / ``pl_skeletons``: documents that mirror the STRUCTURE and
boilerplate of real Czech official document types — a hospital discharge report
(`Propouštěcí zpráva`), a services contract (`Smlouva o poskytování služeb`), a sworn declaration
(`Čestné prohlášení`), and an administrative decision letter (`Rozhodnutí`) — populated with
**synthetic** Czech identifiers (checksum-valid rodné číslo, rodné-číslo-consistent date of birth,
IČO, Czech IBAN, +420 phones, addresses), with Czech gender agreement (the -ová feminine surname).

Because the skeletons are authored faithful reproductions of *public document structure* (not
scraped real records), there is **no residual real PII by construction** — every identifier is
synthetic — so the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a
quality spot-check, not a personal-data hunt.

Offset-determinism, the byte-equality assert and the strict BIOES gate are inherited unchanged
from the shared ``localepack.fill_document`` (same invariants as RO/PL/IT). This is a **decode-
bearing** measurement: a missed (un-redacted) rodné číslo deterministically discloses DATE_OF_BIRTH
+ SEX (the year/month/day are fully recoverable for the modern 10-digit form, with the female month
+50 offset and the YY-century convention). Scored zero-shot with ``national_id_leakage``
(``country='CZ'`` on every row dispatches to the rodné-číslo validator). This config is
``config_status=dev`` — a citable-track candidate, not yet validated (pending native-speaker review
+ IAA). All four templates are one authored skeleton family sharing a single fill path; a leak
headline from a single template family is not validated generalization — a second independent
template family is required before this is cited.

Re-identification accounting is **per distinct subject** (KLU-49): the discharge report deliberately
repeats the patient's rodné číslo — once in the identity header and again in the
`Rodné číslo (identifikace pacienta)` line, as real Czech propouštěcí zprávy do — so the gold count
and leak metric must NOT double-count that subject. The harness ``national_id_leakage`` dedups by
``(document, country, normalized value)``; this module emits ``country="CZ"`` on every row so the
metric dispatches to the rodné-číslo validator (not the RO/CNP default).
"""

from __future__ import annotations

import random
import unicodedata
from collections.abc import Iterator

from .cz_generators import (
    gen_iban_cz,
    gen_ico,
    gen_person,
    iban_cz_valid,
    ico_valid,
    rodne_cislo_valid,
)
from .localepack import ChecksummedID, Doc, LocalePack

COUNTRY = "CZ"

HOSPITALS = ["Fakultní nemocnice", "Krajská nemocnice", "Městská nemocnice", "Všeobecná nemocnice"]
COMPANIES = ["Příklad s.r.o.", "TechPlus a.s.", "Nordik Konzult s.r.o.", "MediPéče s.r.o."]
CONDITIONS = [
    "esenciální hypertenze", "diabetes mellitus 2. typu", "zápal plic",
    "chronická gastritida", "ischias", "akutní bronchitida",
]
WARDS = ["Interní oddělení", "Kardiologické oddělení", "Chirurgické oddělení", "Neurologické oddělení"]


def _ascii(s: str) -> str:
    """ASCII-fold Czech diacritics for realistic emails."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two
# entities share a whitespace token (the strict BIOES gate fails loud otherwise).
TEMPLATES = [
    ("clinical", """PROPOUŠTĚCÍ ZPRÁVA

{hospital} — {ward}

Pacient: {patient}
Rodné číslo: {rc} , telefon: {phone}
Datum narození: {dob} , adresa bydliště: {address}

Hlavní diagnóza: {condition} .
Anamnéza: {pacient_word} se {dostavil_word} dne {date} s popsanou symptomatologií.
Doporučení při propuštění: léčba dle schématu, kontrola za 30 dní.

Rodné číslo (identifikace pacienta): {rc_id}
Ošetřující lékař: MUDr. {doctor}
Datum vystavení: {date}"""),

    ("legal", """SMLOUVA O POSKYTOVÁNÍ SLUŽEB
Č. {contractno} ze dne {date}

Smluvní strany:
1. {company} , se sídlem na adrese {address2} , IČO {ico} ,
   bankovní účet IBAN {iban} , zastoupená {doctor} ;
2. {patient} , rodné číslo {rc} , {bytem} na adrese {address} , telefon {phone} ,
   e-mail {email} .

Předmětem smlouvy je poskytování služeb sjednaných stranami.
Tato smlouva byla uzavřena dne {date} ve dvou stejnopisech."""),

    ("legal", """ČESTNÉ PROHLÁŠENÍ

Já, níže podepsaný {patient} , rodné číslo {rc} , {bytem} na adrese {address} ,
telefon {phone} , e-mail {email} , čestně prohlašuji, vědom si trestní odpovědnosti za uvedení
nepravdivých údajů, že uvedené údaje jsou pravdivé.

Datum: {date}
Podpis: ____________"""),

    ("admin", """Komu: {patient}
Adresa: {address}

Věc: spis č. {contractno} / {date}

Vážený/á {patient} , oznamujeme Vám, že Vaše žádost byla zaregistrována.
Pro získání dalších informací nás prosím kontaktujte na telefonu {phone} nebo {email} .

S pozdravem,
{doctor}
{company}
{date}"""),
]


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    patient = gen_person(rng)
    doctor = gen_person(rng)
    m = patient.sex == "M"  # Czech gender agreement for boilerplate (not PII → label "O")
    return {
        "bytem": ("trvale bytem", "O"),
        "pacient_word": ("Pacient" if m else "Pacientka", "O"),
        "dostavil_word": ("dostavil" if m else "dostavila", "O"),
        "ward": (rng.choice(WARDS), "O"),  # not PII — rendered as plain text, no span
        "patient": (f"{patient.first_name} {patient.last_name}", "PERSON"),
        "doctor": (f"{doctor.first_name} {doctor.last_name}", "PERSON"),
        "rc": (patient.rodne_cislo, "NATIONAL_ID"),
        # Real Czech discharge reports repeat the rodné číslo as the patient identifier. Same VALUE
        # as {rc} → the per-subject dedup in national_id_leakage collapses it (KLU-49 guard); it is
        # NOT a second subject and must not inflate the gold count.
        "rc_id": (patient.rodne_cislo, "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),  # DERIVED from the rodné číslo → birthday matches it
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.cz", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "ico": (gen_ico(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} {patient.region}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "contractno": (f"{rng.randint(100, 9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(2018, 2025)}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure CZ document (shared splice/byte-equality/strict-BIOES gate)."""
    return cz_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield n offset-validated faithful-structure CZ documents.

    Each row carries ``country='CZ'`` so the country-dispatched ``national_id_leakage`` metric
    validates the gold IDs with the rodné-číslo validator (the default country is RO).
    """
    for row in cz_skeleton_pack.generate_dataset(n, seed=seed):
        yield {**row, "country": COUNTRY}


def _gen_rc_selftest(rng: random.Random) -> str:
    return gen_person(rng).rodne_cislo


# cz-realskeleton-v1 pack. rodné číslo / IČO / IBAN carry checksums (self-tested).
cz_skeleton_pack = LocalePack(
    language="cs",
    name="Czech (real-skeleton)",
    checksummed_ids=(
        ChecksummedID("rodné číslo", _gen_rc_selftest, rodne_cislo_valid),
        ChecksummedID("IČO", gen_ico, ico_valid),
        ChecksummedID("IBAN", gen_iban_cz, iban_cz_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
)
