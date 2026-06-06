"""lt-realskeleton-v1: faithful real-structure Lithuanian documents + synthetic PII.

The Lithuanian sibling of ``ee_skeletons`` / ``dk_skeletons``: documents that mirror the STRUCTURE
and boilerplate of real Lithuanian official document types — a hospital discharge summary
(`Išrašas iš ligos istorijos / Epikrizė`), a services agreement (`Paslaugų teikimo sutartis`), a
sworn declaration (`Patvirtinimas`), and an administrative decision letter (`Sprendimas`) —
populated with **synthetic** Lithuanian identifiers (checksum-valid asmens kodas, asmens-kodas-
consistent date of birth, įmonės kodas, Lithuanian IBAN, +370 phones, addresses), with Lithuanian
gender agreement (the -ienė feminine surname).

Because the skeletons are authored faithful reproductions of *public document structure* (not
scraped real records), there is **no residual real PII by construction** — every identifier is
synthetic — so the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a
quality spot-check, not a personal-data hunt.

Offset-determinism, the byte-equality assert and the strict BIOES gate are inherited unchanged from
the shared ``localepack.fill_document`` (same invariants as RO/PL/IT/SE/CZ/DK/FI/EE). This is a
**decode-bearing** measurement: a missed (un-redacted) asmens kodas deterministically discloses
DATE_OF_BIRTH + SEX (the full date is recoverable — the century comes from the 1st digit; the same
digit's parity gives sex; the final digit is an ISO-7064-style two-pass mod-11 check, IDENTICAL to
the Estonian isikukood). Scored zero-shot with ``national_id_leakage`` (``country='LT'`` on every
row dispatches to the asmens-kodas validator). This config is ``config_status=dev`` — a citable-track
candidate, not yet validated (pending native-speaker review + IAA). All four templates are one
authored skeleton family sharing a single fill path; a leak headline from a single template family is
not validated generalization — a second independent template family is required before this is cited.

Re-identification accounting is **per distinct subject** (KLU-49): the discharge summary deliberately
repeats the patient's asmens kodas — once in the identity header and again in the
`Asmens kodas (paciento identifikatorius)` line, as real Lithuanian epikrizės do — so the gold count
and leak metric must NOT double-count that subject. The harness ``national_id_leakage`` dedups by
``(document, country, normalized value)``; this module emits ``country="LT"`` on every row so the
metric dispatches to the asmens-kodas validator (not the RO/CNP default).

COLLISION FOOTGUN (RES-84): EE/LT/LV share the same id structure (1st-digit century+sex, two-pass
mod-11). The validator is country-keyed and never auto-detects; the only national id emitted here is
the asmens kodas; the įmonės kodas (9 digits) is structurally disjoint (11 vs 9 digits) so it never
mis-decodes as a re-id subject (the SE-orgnr lesson from RES-80).
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from .localepack import ChecksummedID, Doc, LocalePack
from .lt_generators import (
    asmens_kodas_valid,
    gen_iban_lt,
    gen_imones_kodas,
    gen_person,
    iban_lt_valid,
    imones_kodas_valid,
)

COUNTRY = "LT"

HOSPITALS = ["Vilniaus universiteto ligoninė", "Kauno klinikos", "Klaipėdos universitetinė ligoninė",
             "Respublikinė Šiaulių ligoninė"]
COMPANIES = ["Pavyzdys UAB", "TechPlus AB", "Šiaurės Konsultacijos UAB", "MediPriežiūra UAB"]
CONDITIONS = [
    "esminė hipertenzija", "2 tipo cukrinis diabetas", "plaučių uždegimas",
    "lėtinis gastritas", "išialgija", "ūminis bronchitas",
]
WARDS = ["Vidaus ligų skyrius", "Kardiologijos skyrius", "Chirurgijos skyrius", "Neurologijos skyrius"]


def _ascii(s: str) -> str:
    table = {"ą": "a", "č": "c", "ę": "e", "ė": "e", "į": "i", "š": "s",
             "ų": "u", "ū": "u", "ž": "z"}
    for k, v in table.items():
        s = s.replace(k, v).replace(k.upper(), v.upper())
    return s


# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two
# entities share a whitespace token (the strict BIOES gate fails loud otherwise).
TEMPLATES = [
    ("clinical", """IŠRAŠAS IŠ LIGOS ISTORIJOS / EPIKRIZĖ

{hospital} — {ward}

Pacientas: {patient}
Asmens kodas: {ak} , telefonas: {phone}
Gimimo data: {dob} , gyvenamosios vietos adresas: {address}

Pagrindinė diagnozė: {condition} .
Anamnezė: pacientas kreipėsi {date} su aprašyta simptomatika.
Rekomendacijos išrašant: gydymas pagal schemą, kontrolė po 30 dienų.

Asmens kodas (paciento identifikatorius): {ak_id}
Gydantis gydytojas: dr. {doctor}
Išdavimo data: {date}"""),

    ("legal", """PASLAUGŲ TEIKIMO SUTARTIS
Nr. {contractno} , data {date}

Sutarties šalys:
1. {company} , registruotos buveinės adresas {address2} , įmonės kodas {imk} ,
   banko sąskaita IBAN {iban} , atstovaujama {doctor} ;
2. {patient} , asmens kodas {ak} , gyvenantis adresu {address} , telefonas {phone} ,
   el. paštas {email} .

Sutarties dalykas yra šalių sutartų paslaugų teikimas.
Ši sutartis sudaryta {date} dviem vienodais egzemplioriais."""),

    ("legal", """PATVIRTINIMAS

Aš, žemiau pasirašęs {patient} , asmens kodas {ak} , gyvenantis adresu {address} ,
telefonas {phone} , el. paštas {email} , patvirtinu, suvokdamas atsakomybę už klaidingų duomenų
pateikimą, kad pateikti duomenys yra teisingi.

Data: {date}
Parašas: ____________"""),

    ("admin", """Kam: {patient}
Adresas: {address}

Tema: byla nr. {contractno} / {date}

Gerbiamasis {patient} , pranešame, kad Jūsų prašymas užregistruotas.
Dėl papildomos informacijos prašome susisiekti telefonu {phone} arba {email} .

Pagarbiai,
{doctor}
{company}
{date}"""),
]


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    patient = gen_person(rng)
    doctor = gen_person(rng)
    return {
        "ward": (rng.choice(WARDS), "O"),  # not PII — rendered as plain text, no span
        "patient": (f"{patient.first_name} {patient.last_name}", "PERSON"),
        "doctor": (f"{doctor.first_name} {doctor.last_name}", "PERSON"),
        "ak": (patient.asmens_kodas, "NATIONAL_ID"),
        # Real Lithuanian epikrizės repeat the asmens kodas as the patient identifier. Same VALUE as
        # {ak} → the per-subject dedup in national_id_leakage collapses it (KLU-49 guard); it is NOT
        # a second subject and must not inflate the gold count.
        "ak_id": (patient.asmens_kodas, "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),  # DERIVED from the asmens kodas → birthday matches it
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.lt", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "imk": (gen_imones_kodas(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} , {patient.county}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "contractno": (f"{rng.randint(100, 9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(2018, 2025)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure LT document (shared splice/byte-equality/strict-BIOES gate)."""
    return lt_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield n offset-validated faithful-structure LT documents.

    Each row carries ``country='LT'`` so the country-dispatched ``national_id_leakage`` metric
    validates the gold IDs with the asmens-kodas validator (the default country is RO).
    """
    for row in lt_skeleton_pack.generate_dataset(n, seed=seed):
        yield {**row, "country": COUNTRY}


def _gen_ak_selftest(rng: random.Random) -> str:
    return gen_person(rng).asmens_kodas


# lt-realskeleton-v1 pack. asmens kodas/įmonės kodas/IBAN carry checksums (self-tested).
lt_skeleton_pack = LocalePack(
    language="lt",
    name="Lithuanian (real-skeleton)",
    checksummed_ids=(
        ChecksummedID("asmens kodas", _gen_ak_selftest, asmens_kodas_valid),
        ChecksummedID("įmonės kodas", gen_imones_kodas, imones_kodas_valid),
        ChecksummedID("IBAN", gen_iban_lt, iban_lt_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
)
