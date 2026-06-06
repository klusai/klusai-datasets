"""ee-realskeleton-v1: faithful real-structure Estonian documents + synthetic PII.

The Estonian sibling of ``dk_skeletons`` / ``cz_skeletons``: documents that mirror the STRUCTURE and
boilerplate of real Estonian official document types — a hospital discharge summary
(`Epikriis / Haigusloo väljavõte`), a services agreement (`Teenuste osutamise leping`), a sworn
declaration (`Kinnitus`), and an administrative decision letter (`Otsus`) — populated with
**synthetic** Estonian identifiers (checksum-valid isikukood, isikukood-consistent date of birth,
registrikood, Estonian IBAN, +372 phones, addresses).

Because the skeletons are authored faithful reproductions of *public document structure* (not
scraped real records), there is **no residual real PII by construction** — every identifier is
synthetic — so the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a
quality spot-check, not a personal-data hunt.

Offset-determinism, the byte-equality assert and the strict BIOES gate are inherited unchanged from
the shared ``localepack.fill_document`` (same invariants as RO/PL/IT/SE/CZ/DK/FI). This is a
**decode-bearing** measurement: a missed (un-redacted) isikukood deterministically discloses
DATE_OF_BIRTH + SEX (the full date is recoverable — the century comes from the 1st digit; the same
digit's parity gives sex; the final digit is an ISO-7064-style two-pass mod-11 check). Scored
zero-shot with ``national_id_leakage`` (``country='EE'`` on every row dispatches to the isikukood
validator). This config is ``config_status=dev`` — a citable-track candidate, not yet validated
(pending native-speaker review + IAA). All four templates are one authored skeleton family sharing a
single fill path; a leak headline from a single template family is not validated generalization — a
second independent template family is required before this is cited.

Re-identification accounting is **per distinct subject** (KLU-49): the discharge summary deliberately
repeats the patient's isikukood — once in the identity header and again in the
`Isikukood (patsiendi identifikaator)` line, as real Estonian epikriisid do — so the gold count and
leak metric must NOT double-count that subject. The harness ``national_id_leakage`` dedups by
``(document, country, normalized value)``; this module emits ``country="EE"`` on every row so the
metric dispatches to the isikukood validator (not the RO/CNP default).

COLLISION FOOTGUN (RES-84): EE/LT/LV share the same id structure (1st-digit century+sex, two-pass
mod-11). The validator is country-keyed and never auto-detects, and the only national id emitted
here is the isikukood; the registrikood (8 digits) is structurally disjoint (11 vs 8 digits) so it
never mis-decodes as a re-id subject (the SE-orgnr lesson from RES-80).
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from .ee_generators import (
    gen_iban_ee,
    gen_person,
    gen_registrikood,
    iban_ee_valid,
    isikukood_valid,
    registrikood_valid,
)
from .localepack import ChecksummedID, Doc, LocalePack

COUNTRY = "EE"

HOSPITALS = ["Põhja-Eesti Regionaalhaigla", "Tartu Ülikooli Kliinikum", "Ida-Tallinna Keskhaigla",
             "Lääne-Tallinna Keskhaigla"]
COMPANIES = ["Näide OÜ", "TechPlus AS", "Põhjala Konsultatsioonid OÜ", "MediHoole OÜ"]
CONDITIONS = [
    "essentsiaalne hüpertensioon", "2. tüüpi diabeet", "kopsupõletik",
    "krooniline gastriit", "ishias", "äge bronhiit",
]
WARDS = ["Sisehaiguste osakond", "Kardioloogia osakond", "Kirurgia osakond", "Neuroloogia osakond"]


def _ascii(s: str) -> str:
    s = s.replace("õ", "o").replace("ä", "a").replace("ö", "o").replace("ü", "u")
    return s.replace("Õ", "O").replace("Ä", "A").replace("Ö", "O").replace("Ü", "U")


# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two
# entities share a whitespace token (the strict BIOES gate fails loud otherwise).
TEMPLATES = [
    ("clinical", """EPIKRIIS / HAIGUSLOO VÄLJAVÕTE

{hospital} — {ward}

Patsient: {patient}
Isikukood: {ik} , telefon: {phone}
Sünniaeg: {dob} , elukoha aadress: {address}

Põhidiagnoos: {condition} .
Anamnees: patsient pöördus {date} kirjeldatud sümptomaatikaga.
Soovitused väljakirjutamisel: ravi vastavalt skeemile, kontroll 30 päeva pärast.

Isikukood (patsiendi identifikaator): {ik_id}
Raviarst: dr. {doctor}
Väljaandmise kuupäev: {date}"""),

    ("legal", """TEENUSTE OSUTAMISE LEPING
Nr. {contractno} kuupäevaga {date}

Lepingupooled:
1. {company} , asukohaga aadressil {address2} , registrikood {regcode} ,
   pangakonto IBAN {iban} , esindajaks {doctor} ;
2. {patient} , isikukood {ik} , elukohaga aadressil {address} , telefon {phone} ,
   e-post {email} .

Lepingu esemeks on poolte kokku lepitud teenuste osutamine.
Käesolev leping on koostatud {date} kahes identses eksemplaris."""),

    ("legal", """KINNITUS

Mina, allakirjutanu {patient} , isikukood {ik} , elukohaga aadressil {address} ,
telefon {phone} , e-post {email} , kinnitan, teadlikuna valeandmete esitamise eest ette nähtud
vastutusest, et esitatud andmed on õiged.

Kuupäev: {date}
Allkiri: ____________"""),

    ("admin", """Kellele: {patient}
Aadress: {address}

Teema: toimik nr. {contractno} / {date}

Lugupeetud {patient} , teatame, et Teie taotlus on registreeritud.
Lisateabe saamiseks palume võtta meiega ühendust telefonil {phone} või {email} .

Lugupidamisega,
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
        "ik": (patient.isikukood, "NATIONAL_ID"),
        # Real Estonian epikriisid repeat the isikukood as the patient identifier. Same VALUE as {ik}
        # → the per-subject dedup in national_id_leakage collapses it (KLU-49 guard); it is NOT a
        # second subject and must not inflate the gold count.
        "ik_id": (patient.isikukood, "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),  # DERIVED from the isikukood → birthday matches it
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.ee", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "regcode": (gen_registrikood(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} , {patient.county}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "contractno": (f"{rng.randint(100, 9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(2018, 2025)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure EE document (shared splice/byte-equality/strict-BIOES gate)."""
    return ee_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield n offset-validated faithful-structure EE documents.

    Each row carries ``country='EE'`` so the country-dispatched ``national_id_leakage`` metric
    validates the gold IDs with the isikukood validator (the default country is RO).
    """
    for row in ee_skeleton_pack.generate_dataset(n, seed=seed):
        yield {**row, "country": COUNTRY}


def _gen_ik_selftest(rng: random.Random) -> str:
    return gen_person(rng).isikukood


# ee-realskeleton-v1 pack. isikukood/registrikood/IBAN carry checksums (self-tested).
ee_skeleton_pack = LocalePack(
    language="et",
    name="Estonian (real-skeleton)",
    checksummed_ids=(
        ChecksummedID("isikukood", _gen_ik_selftest, isikukood_valid),
        ChecksummedID("registrikood", gen_registrikood, registrikood_valid),
        ChecksummedID("IBAN", gen_iban_ee, iban_ee_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
)
