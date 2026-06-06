"""dk-realskeleton-v1: faithful real-structure Danish documents + synthetic PII.

The Danish sibling of ``se_skeletons`` / ``cz_skeletons``: documents that mirror the STRUCTURE and
boilerplate of real Danish official document types — a hospital discharge summary (`Udskrivningsbrev
/ Epikrise`), a services agreement (`Aftale om tjenesteydelser`), a sworn declaration (`Erklæring
på tro og love`), and an administrative decision letter (`Afgørelse`) — populated with **synthetic**
Danish identifiers (format/century-valid CPR-nummer, CPR-consistent date of birth, CVR-nummer,
Danish IBAN, +45 phones, addresses).

Because the skeletons are authored faithful reproductions of *public document structure* (not
scraped real records), there is **no residual real PII by construction** — every identifier is
synthetic — so the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a
quality spot-check, not a personal-data hunt.

Offset-determinism, the byte-equality assert and the strict BIOES gate are inherited unchanged from
the shared ``localepack.fill_document`` (same invariants as RO/PL/IT/SE/CZ). This is a **decode-
bearing** measurement: a missed (un-redacted) CPR-nummer deterministically discloses DATE_OF_BIRTH +
SEX (the full date is recoverable — the century comes from the 7th-digit/YY CPR-kontoret table; the
last-digit parity gives sex). NOTE: the historical mod-11 check was abolished in 2007, so a valid
CPR is format + century-table + plausible date, NOT a checksum. Scored zero-shot with
``national_id_leakage`` (``country='DK'`` on every row dispatches to the CPR validator). This config
is ``config_status=dev`` — a citable-track candidate, not yet validated (pending native-speaker
review + IAA). All four templates are one authored skeleton family sharing a single fill path; a
leak headline from a single template family is not validated generalization — a second independent
template family is required before this is cited.

Re-identification accounting is **per distinct subject** (KLU-49): the discharge summary deliberately
repeats the patient's CPR-nummer — once in the identity header and again in the
`CPR-nummer (patientidentitet)` line, as real Danish epikriser do — so the gold count and leak metric
must NOT double-count that subject. The harness ``national_id_leakage`` dedups by ``(document,
country, normalized value)``; this module emits ``country="DK"`` on every row so the metric
dispatches to the CPR validator (not the RO/CNP default).
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from .dk_generators import (
    cpr_valid,
    cvr_valid,
    gen_cvr,
    gen_iban_dk,
    gen_person,
    iban_dk_valid,
)
from .localepack import ChecksummedID, Doc, LocalePack

COUNTRY = "DK"

HOSPITALS = ["Rigshospitalet", "Aarhus Universitetshospital", "Odense Universitetshospital",
             "Aalborg Universitetshospital"]
COMPANIES = ["Eksempel A/S", "TechPlus A/S", "Nordisk Konsulent ApS", "MediPleje ApS"]
CONDITIONS = [
    "essentiel hypertension", "type 2-diabetes", "lungebetændelse",
    "kronisk gastritis", "iskias", "akut bronkitis",
]
WARDS = ["Medicinsk afdeling", "Kardiologisk afdeling", "Kirurgisk afdeling", "Neurologisk afdeling"]


def _ascii(s: str) -> str:
    s = s.replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
    return s.replace("Æ", "Ae").replace("Ø", "Oe").replace("Å", "Aa")


# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two
# entities share a whitespace token (the strict BIOES gate fails loud otherwise).
TEMPLATES = [
    ("clinical", """UDSKRIVNINGSBREV / EPIKRISE

{hospital} — {ward}

Patient: {patient}
CPR-nummer: {cpr} , telefon: {phone}
Fødselsdato: {dob} , bopælsadresse: {address}

Hoveddiagnose: {condition} .
Anamnese: patienten henvendte sig den {date} med beskrevet symptomatologi.
Anbefalinger ved udskrivning: behandling efter skema, kontrol om 30 dage.

CPR-nummer (patientidentitet): {cpr_id}
Ansvarlig læge: dr. {doctor}
Udstedelsesdato: {date}"""),

    ("legal", """AFTALE OM TJENESTEYDELSER
Nr. {contractno} af den {date}

Aftaleparter:
1. {company} , med hjemsted på adressen {address2} , CVR-nummer {cvr} ,
   bankkonto IBAN {iban} , repræsenteret af {doctor} ;
2. {patient} , CPR-nummer {cpr} , bosat på adressen {address} , telefon {phone} ,
   e-mail {email} .

Aftalens genstand er levering af de tjenesteydelser, som parterne har aftalt.
Denne aftale er udfærdiget den {date} i to enslydende eksemplarer."""),

    ("legal", """ERKLÆRING PÅ TRO OG LOVE

Jeg, undertegnede {patient} , CPR-nummer {cpr} , bosat på adressen {address} ,
telefon {phone} , e-mail {email} , erklærer på tro og love, bevidst om strafansvaret for afgivelse
af urigtige oplysninger, at de afgivne oplysninger er korrekte.

Dato: {date}
Underskrift: ____________"""),

    ("admin", """Til: {patient}
Adresse: {address}

Vedr.: sag nr. {contractno} / {date}

Kære {patient} , vi meddeler, at Deres ansøgning er blevet registreret.
For yderligere oplysninger bedes De kontakte os på telefon {phone} eller {email} .

Med venlig hilsen,
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
        "cpr": (patient.cpr, "NATIONAL_ID"),
        # Real Danish epikriser repeat the CPR-nummer as the patient identifier. Same VALUE as {cpr}
        # → the per-subject dedup in national_id_leakage collapses it (KLU-49 guard); it is NOT a
        # second subject and must not inflate the gold count.
        "cpr_id": (patient.cpr, "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),  # DERIVED from the CPR → birthday matches it
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.dk", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "cvr": (gen_cvr(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} , {patient.region}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "contractno": (f"{rng.randint(100, 9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(2018, 2025)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure DK document (shared splice/byte-equality/strict-BIOES gate)."""
    return dk_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield n offset-validated faithful-structure DK documents.

    Each row carries ``country='DK'`` so the country-dispatched ``national_id_leakage`` metric
    validates the gold IDs with the CPR validator (the default country is RO).
    """
    for row in dk_skeleton_pack.generate_dataset(n, seed=seed):
        yield {**row, "country": COUNTRY}


def _gen_cpr_selftest(rng: random.Random) -> str:
    return gen_person(rng).cpr


# dk-realskeleton-v1 pack. CPR (format/century)/CVR/IBAN carry checksums/format rules (self-tested).
dk_skeleton_pack = LocalePack(
    language="da",
    name="Danish (real-skeleton)",
    checksummed_ids=(
        ChecksummedID("CPR-nummer", _gen_cpr_selftest, cpr_valid),
        ChecksummedID("CVR-nummer", gen_cvr, cvr_valid),
        ChecksummedID("IBAN", gen_iban_dk, iban_dk_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
)
