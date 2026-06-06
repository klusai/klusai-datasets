"""sk-realskeleton-v1: faithful real-structure Slovak documents + synthetic PII.

The Slovak sibling of ``cz_skeletons`` — and the SAME identifier: the Slovak **rodné číslo** uses the
IDENTICAL algorithm as the Czech one (SK Zákon č. 301/2000 Z. z. / the shared Czechoslovak Zákon č.
133/2000 Sb. scheme). Documents mirror the STRUCTURE and boilerplate of real Slovak official document
types — a hospital discharge summary (`Prepúšťacia správa`), a services agreement
(`Zmluva o poskytovaní služieb`), a sworn declaration (`Čestné vyhlásenie`), and an administrative
decision letter (`Rozhodnutie`) — populated with **synthetic** Slovak identifiers (checksum-valid
rodné číslo, rodné-číslo-consistent date of birth, IČO, Slovak IBAN, +421 phones, addresses), with
Slovak gender agreement (the -ová feminine surname).

Because the skeletons are authored faithful reproductions of *public document structure* (not scraped
real records), there is **no residual real PII by construction** — every identifier is synthetic — so
the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a quality spot-check.

Offset-determinism, the byte-equality assert and the strict BIOES gate are inherited unchanged from
the shared ``localepack.fill_document`` (same invariants as RO/PL/IT/SE/CZ/DK/FI/EE/LT). This is a
**decode-bearing** measurement: a missed (un-redacted) rodné číslo deterministically discloses
DATE_OF_BIRTH + SEX (the modern 10-digit form is fully date-recoverable; female month +50; YY-century
convention). Scored zero-shot with ``national_id_leakage`` (``country='SK'`` on every row dispatches to
the SK rodné-číslo validator — which reuses the CZ decoder, tagged SK). This config is
``config_status=dev`` — a citable-track candidate, not yet validated (pending native-speaker review +
IAA). All four templates are one authored skeleton family sharing a single fill path; a leak headline
from a single template family is not validated generalization — a second independent template family is
required before this is cited.

Re-identification accounting is **per distinct subject** (KLU-49): the discharge summary deliberately
repeats the patient's rodné číslo — once in the identity header and again in the
`Rodné číslo (identifikátor pacienta)` line — so the gold count and leak metric must NOT double-count
that subject. The harness ``national_id_leakage`` dedups by ``(document, country, normalized value)``;
this module emits ``country="SK"`` on every row so the metric dispatches to the SK validator.

COLLISION FOOTGUN (RES-85): a CZ and an SK rodné číslo are structurally IDENTICAL — only the row
``country`` tag distinguishes them. The validator is country-keyed and never auto-detects, so an SK
number is decoded as SK (never mis-dispatched as CZ, or vice-versa). The only national id emitted here
is the rodné číslo; the IČO (8 digits) is structurally disjoint (10 vs 8 digits) so it never
mis-decodes as a re-id subject (the SE-orgnr lesson from RES-80).
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from .localepack import ChecksummedID, Doc, LocalePack
from .sk_generators import (
    gen_iban_sk,
    gen_ico,
    gen_person,
    iban_sk_valid,
    ico_valid,
    rodne_cislo_valid,
)

COUNTRY = "SK"

HOSPITALS = ["Univerzitná nemocnica Bratislava", "Univerzitná nemocnica L. Pasteura Košice",
             "Fakultná nemocnica Trnava", "Fakultná nemocnica Žilina"]
COMPANIES = ["Príklad s.r.o.", "TechPlus a.s.", "Severné Poradenstvo s.r.o.", "MediStarostlivosť s.r.o."]
CONDITIONS = [
    "esenciálna hypertenzia", "diabetes mellitus 2. typu", "zápal pľúc",
    "chronická gastritída", "ischias", "akútna bronchitída",
]
WARDS = ["Interné oddelenie", "Kardiologické oddelenie", "Chirurgické oddelenie", "Neurologické oddelenie"]


def _ascii(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two
# entities share a whitespace token (the strict BIOES gate fails loud otherwise).
TEMPLATES = [
    ("clinical", """PREPÚŠŤACIA SPRÁVA

{hospital} — {ward}

Pacient: {patient}
Rodné číslo: {rc} , telefón: {phone}
Dátum narodenia: {dob} , adresa trvalého pobytu: {address}

Hlavná diagnóza: {condition} .
Anamnéza: pacient sa dostavil {date} s opísanou symptomatikou.
Odporúčania pri prepustení: liečba podľa schémy, kontrola o 30 dní.

Rodné číslo (identifikátor pacienta): {rc_id}
Ošetrujúci lekár: dr. {doctor}
Dátum vydania: {date}"""),

    ("legal", """ZMLUVA O POSKYTOVANÍ SLUŽIEB
Č. {contractno} , zo dňa {date}

Zmluvné strany:
1. {company} , adresa sídla {address2} , IČO {ico} ,
   bankový účet IBAN {iban} , zastúpená {doctor} ;
2. {patient} , rodné číslo {rc} , bytom na adrese {address} , telefón {phone} ,
   e-mail {email} .

Predmetom zmluvy je poskytovanie zmluvnými stranami dohodnutých služieb.
Táto zmluva je uzavretá {date} v dvoch rovnopisoch."""),

    ("legal", """ČESTNÉ VYHLÁSENIE

Dolu podpísaný {patient} , rodné číslo {rc} , bytom na adrese {address} ,
telefón {phone} , e-mail {email} , vyhlasujem, vedomý si zodpovednosti za uvedenie nepravdivých
údajov, že uvedené údaje sú pravdivé.

Dátum: {date}
Podpis: ____________"""),

    ("admin", """Pre: {patient}
Adresa: {address}

Vec: spis č. {contractno} / {date}

Vážený {patient} , oznamujeme Vám, že Vaša žiadosť bola zaregistrovaná.
Pre ďalšie informácie nás kontaktujte na telefónnom čísle {phone} alebo {email} .

S pozdravom,
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
        "rc": (patient.rodne_cislo, "NATIONAL_ID"),
        # The discharge summary repeats the rodné číslo as the patient identifier. Same VALUE as {rc}
        # → the per-subject dedup in national_id_leakage collapses it (KLU-49 guard); it is NOT a
        # second subject and must not inflate the gold count.
        "rc_id": (patient.rodne_cislo, "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),  # DERIVED from the rodné číslo → birthday matches it
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.sk", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "ico": (gen_ico(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} , {patient.region}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "contractno": (f"{rng.randint(100, 9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(2018, 2025)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure SK document (shared splice/byte-equality/strict-BIOES gate)."""
    return sk_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield n offset-validated faithful-structure SK documents.

    Each row carries ``country='SK'`` so the country-dispatched ``national_id_leakage`` metric
    validates the gold IDs with the SK rodné-číslo validator (the default country is RO).
    """
    for row in sk_skeleton_pack.generate_dataset(n, seed=seed):
        yield {**row, "country": COUNTRY}


def _gen_rc_selftest(rng: random.Random) -> str:
    return gen_person(rng).rodne_cislo


# sk-realskeleton-v1 pack. rodné číslo/IČO/IBAN carry checksums (self-tested against the SK validator).
sk_skeleton_pack = LocalePack(
    language="sk",
    name="Slovak (real-skeleton)",
    checksummed_ids=(
        ChecksummedID("rodné číslo", _gen_rc_selftest, rodne_cislo_valid),
        ChecksummedID("IČO", gen_ico, ico_valid),
        ChecksummedID("IBAN", gen_iban_sk, iban_sk_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
)
