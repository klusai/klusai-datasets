"""se-realskeleton-v1: faithful real-structure Swedish documents + synthetic PII.

The Swedish sibling of ``ro_skeletons`` / ``pl_skeletons``: documents that mirror the STRUCTURE
and boilerplate of real Swedish official document types — a patient discharge note
(`Epikris / Utskrivningsmeddelande`), a services agreement (`Avtal om tjänster`), a declaration
(`Försäkran på heder och samvete`), and an administrative decision letter (`Beslut`) — populated
with **synthetic** Swedish identifiers (checksum-valid personnummer, personnummer-consistent date
of birth, organisationsnummer, Swedish IBAN, +46 phones, addresses).

Because the skeletons are authored faithful reproductions of *public document structure* (not
scraped real records), there is **no residual real PII by construction** — every identifier is
synthetic — so the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a
quality spot-check, not a personal-data hunt.

Offset-determinism, the byte-equality assert and the strict BIOES gate are inherited unchanged
from the shared ``localepack.fill_document`` (same invariants as RO/PL/IT). This is a **decode-
bearing** measurement: a missed (un-redacted) personnummer deterministically discloses SEX +
DATE_OF_BIRTH (birth month + day; the 2-digit year's century is carried only by the printed
separator, like the IT codice-fiscale 2-digit year). Scored zero-shot with ``national_id_leakage``
(``country='SE'`` on every row dispatches to the personnummer validator). This config is
``config_status=dev`` — a citable-track candidate, not yet validated (pending native-speaker review
+ IAA). All four templates are one authored skeleton family sharing a single fill path; a leak
headline from a single template family is not validated generalization — a second independent
template family is required before this is cited.

Re-identification accounting is **per distinct subject** (KLU-49): the discharge note deliberately
repeats the patient's personnummer — once in the identity header and again in the
`Personnummer (patientidentitet)` line, exactly as real Swedish epikris notes do — so the gold
count and leak metric must NOT double-count that subject. The harness ``national_id_leakage`` dedups
by ``(document, country, normalized value)``; this module emits ``country="SE"`` on every row so the
metric dispatches to the personnummer validator (not the RO/CNP default).
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from .localepack import ChecksummedID, Doc, LocalePack
from .se_generators import (
    CITIES,
    gen_iban_se,
    gen_orgnr,
    gen_person,
    iban_se_valid,
    orgnr_valid,
    personnummer_valid,
)

COUNTRY = "SE"

HOSPITALS = ["Karolinska Universitetssjukhuset", "Sahlgrenska Universitetssjukhuset",
             "Akademiska sjukhuset", "Universitetssjukhuset"]
COMPANIES = ["Exempel AB", "TechPlus AB", "Nordisk Konsult AB", "MediVård AB"]
CONDITIONS = [
    "essentiell hypertoni", "diabetes mellitus typ 2", "lunginflammation",
    "kronisk gastrit", "ischias", "akut bronkit",
]
WARDS = ["Medicinkliniken", "Kardiologiska kliniken", "Kirurgkliniken", "Neurologiska kliniken"]


def _ascii(s: str) -> str:
    return s.replace("å", "a").replace("ä", "a").replace("ö", "o").replace("Å", "A").replace("Ä", "A").replace("Ö", "O")


# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two
# entities share a whitespace token (the strict BIOES gate fails loud otherwise).
TEMPLATES = [
    ("clinical", """EPIKRIS / UTSKRIVNINGSMEDDELANDE

{hospital} — {ward}

Patient: {patient}
Personnummer: {pnr} , telefon: {phone}
Födelsedatum: {dob} , bostadsadress: {address}

Huvuddiagnos: {condition} .
Anamnes: patienten sökte vård den {date} med beskriven symptomatologi.
Rekommendationer vid utskrivning: behandling enligt schema, återbesök om 30 dagar.

Personnummer (patientidentitet): {pnr_id}
Ansvarig läkare: dr {doctor}
Utfärdandedatum: {date}"""),

    ("legal", """AVTAL OM TJÄNSTER
Nr {contractno} av den {date}

Avtalsparter:
1. {company} , med säte på adressen {address2} , organisationsnummer {orgnr} ,
   bankkonto IBAN {iban} , företrätt av {doctor} ;
2. {patient} , personnummer {pnr} , bosatt på adressen {address} , telefon {phone} ,
   e-post {email} .

Föremålet för avtalet är tillhandahållande av de tjänster som parterna kommit överens om.
Detta avtal har upprättats den {date} i två likalydande exemplar."""),

    ("legal", """FÖRSÄKRAN PÅ HEDER OCH SAMVETE

Jag, undertecknad {patient} , personnummer {pnr} , bosatt på adressen {address} ,
telefon {phone} , e-post {email} , försäkrar på heder och samvete, medveten om straffansvaret
för osann försäkran, att de uppgifter som lämnats är riktiga.

Datum: {date}
Underskrift: ____________"""),

    ("admin", """Till: {patient}
Adress: {address}

Ang.: ärende nr {contractno} / {date}

Hej {patient} , vi meddelar att Er ansökan har registrerats.
För ytterligare information vänligen kontakta oss på telefon {phone} eller {email} .

Med vänlig hälsning,
{doctor}
{company}
{date}"""),
]


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    patient = gen_person(rng)
    doctor = gen_person(rng)
    _, county = rng.choice(CITIES)
    return {
        "ward": (rng.choice(WARDS), "O"),  # not PII — rendered as plain text, no span
        "patient": (f"{patient.first_name} {patient.last_name}", "PERSON"),
        "doctor": (f"{doctor.first_name} {doctor.last_name}", "PERSON"),
        "pnr": (patient.personnummer, "NATIONAL_ID"),
        # Real Swedish epikris notes repeat the personnummer as the patient identifier. Same VALUE
        # as {pnr} → the per-subject dedup in national_id_leakage collapses it (KLU-49 guard); it is
        # NOT a second subject and must not inflate the gold count.
        "pnr_id": (patient.personnummer, "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),  # DERIVED from the personnummer → birthday matches it
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.se", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "orgnr": (gen_orgnr(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} i {county}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "contractno": (f"{rng.randint(100, 9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(2018, 2025)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure SE document (shared splice/byte-equality/strict-BIOES gate)."""
    return se_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield n offset-validated faithful-structure SE documents.

    Each row carries ``country='SE'`` so the country-dispatched ``national_id_leakage`` metric
    validates the gold IDs with the personnummer validator (the default country is RO).
    """
    for row in se_skeleton_pack.generate_dataset(n, seed=seed):
        yield {**row, "country": COUNTRY}


def _gen_pnr_selftest(rng: random.Random) -> str:
    return gen_person(rng).personnummer


# se-realskeleton-v1 pack. personnummer/orgnr/IBAN carry checksums (self-tested).
se_skeleton_pack = LocalePack(
    language="sv",
    name="Swedish (real-skeleton)",
    checksummed_ids=(
        ChecksummedID("personnummer", _gen_pnr_selftest, personnummer_valid),
        ChecksummedID("organisationsnummer", gen_orgnr, orgnr_valid),
        ChecksummedID("IBAN", gen_iban_se, iban_se_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
)
