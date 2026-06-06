"""si-realskeleton-v1: faithful real-structure Slovenian documents + synthetic PII.

The Slovenian sibling of ``ee_skeletons`` / ``cz_skeletons``: documents that mirror the STRUCTURE and
boilerplate of real Slovenian official document types — a hospital discharge summary
(`Odpustnica / Izvleček iz zdravstvene dokumentacije`), a services agreement
(`Pogodba o opravljanju storitev`), a sworn declaration (`Izjava`), and an administrative decision
letter (`Odločba`) — populated with **synthetic** Slovenian identifiers (checksum-valid EMŠO,
EMŠO-consistent date of birth, davčna številka, Slovenian IBAN, +386 phones, addresses).

Because the skeletons are authored faithful reproductions of *public document structure* (not scraped
real records), there is **no residual real PII by construction** — every identifier is synthetic — so
the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a quality spot-check,
not a personal-data hunt.

Offset-determinism, the byte-equality assert and the strict BIOES gate are inherited unchanged from
the shared ``localepack.fill_document`` (same invariants as RO/PL/IT/SE/CZ/DK/FI/EE/LT). This is a
**decode-bearing** measurement with a RICHER surface than the Baltic family: a missed (un-redacted)
EMŠO deterministically discloses DATE_OF_BIRTH + SEX + **REGION OF BIRTH** (the full date is
recoverable via the ex-YU century convention; the serial encodes sex; the RR field is the region of
birth, like the IT codice fiscale's place; the final digit is a weighted mod-11 check). Scored
zero-shot with ``national_id_leakage`` (``country='SI'`` on every row dispatches to the EMŠO
validator). This config is ``config_status=dev`` — a citable-track candidate, not yet validated
(pending native-speaker review + IAA). All four templates are one authored skeleton family sharing a
single fill path; a leak headline from a single template family is not validated generalization — a
second independent template family is required before this is cited.

Re-identification accounting is **per distinct subject** (KLU-49): the discharge summary deliberately
repeats the patient's EMŠO — once in the identity header and again in the
`EMŠO (identifikator pacienta)` line, as real Slovenian odpustnice do — so the gold count and leak
metric must NOT double-count that subject. The harness ``national_id_leakage`` dedups by
``(document, country, normalized value)``; this module emits ``country="SI"`` on every row so the
metric dispatches to the EMŠO validator (not the RO/CNP default).

COLLISION FOOTGUN (RES-85): every ex-YU country shares the EMŠO/JMBG structure (DDMMYYY RR BBB K), but
the RR region encodes the country and the validator is country-keyed and never auto-detects — the only
national id emitted here is a Slovenian EMŠO (RR=50). The davčna številka (8 digits) is structurally
disjoint (13 vs 8 digits) so it never mis-decodes as a re-id subject (the SE-orgnr lesson from RES-80).
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from .localepack import ChecksummedID, Doc, LocalePack
from .si_generators import (
    emso_valid,
    gen_iban_si,
    gen_person,
    gen_tax_number,
    iban_si_valid,
    tax_number_valid,
)

COUNTRY = "SI"

HOSPITALS = ["Univerzitetni klinični center Ljubljana", "Univerzitetni klinični center Maribor",
             "Splošna bolnišnica Celje", "Splošna bolnišnica Novo mesto"]
COMPANIES = ["Primer d.o.o.", "TechPlus d.d.", "Severni Svetovanje d.o.o.", "MediNega d.o.o."]
CONDITIONS = [
    "esencialna hipertenzija", "sladkorna bolezen tipa 2", "pljučnica",
    "kronični gastritis", "išias", "akutni bronhitis",
]
WARDS = ["Oddelek za interno medicino", "Kardiološki oddelek", "Kirurški oddelek", "Nevrološki oddelek"]


def _ascii(s: str) -> str:
    table = {"č": "c", "š": "s", "ž": "z"}
    for k, v in table.items():
        s = s.replace(k, v).replace(k.upper(), v.upper())
    return s


# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two
# entities share a whitespace token (the strict BIOES gate fails loud otherwise).
TEMPLATES = [
    ("clinical", """ODPUSTNICA / IZVLEČEK IZ ZDRAVSTVENE DOKUMENTACIJE

{hospital} — {ward}

Pacient: {patient}
EMŠO: {emso} , telefon: {phone}
Datum rojstva: {dob} , naslov stalnega prebivališča: {address}

Glavna diagnoza: {condition} .
Anamneza: pacient se je oglasil {date} z opisano simptomatiko.
Priporočila ob odpustu: zdravljenje po shemi, kontrola čez 30 dni.

EMŠO (identifikator pacienta): {emso_id}
Lečeči zdravnik: dr. {doctor}
Datum izdaje: {date}"""),

    ("legal", """POGODBA O OPRAVLJANJU STORITEV
Št. {contractno} , z dne {date}

Pogodbeni stranki:
1. {company} , naslov sedeža {address2} , davčna številka {tax} ,
   bančni račun IBAN {iban} , ki jo zastopa {doctor} ;
2. {patient} , EMŠO {emso} , stanujoč na naslovu {address} , telefon {phone} ,
   e-pošta {email} .

Predmet pogodbe je opravljanje med strankama dogovorjenih storitev.
Ta pogodba je sklenjena {date} v dveh enakih izvodih."""),

    ("legal", """IZJAVA

Spodaj podpisani {patient} , EMŠO {emso} , stanujoč na naslovu {address} ,
telefon {phone} , e-pošta {email} , izjavljam, zavedajoč se odgovornosti za posredovanje
napačnih podatkov, da so navedeni podatki resnični.

Datum: {date}
Podpis: ____________"""),

    ("admin", """Za: {patient}
Naslov: {address}

Zadeva: spis št. {contractno} / {date}

Spoštovani {patient} , obveščamo vas, da je bila vaša vloga registrirana.
Za dodatne informacije nas kontaktirajte na telefon {phone} ali {email} .

S spoštovanjem,
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
        "emso": (patient.emso, "NATIONAL_ID"),
        # Real Slovenian odpustnice repeat the EMŠO as the patient identifier. Same VALUE as {emso}
        # → the per-subject dedup in national_id_leakage collapses it (KLU-49 guard); it is NOT a
        # second subject and must not inflate the gold count.
        "emso_id": (patient.emso, "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),  # DERIVED from the EMŠO → birthday matches it
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.si", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "tax": (gen_tax_number(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} , {patient.region}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "contractno": (f"{rng.randint(100, 9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(2018, 2025)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure SI document (shared splice/byte-equality/strict-BIOES gate)."""
    return si_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield n offset-validated faithful-structure SI documents.

    Each row carries ``country='SI'`` so the country-dispatched ``national_id_leakage`` metric
    validates the gold IDs with the EMŠO validator (the default country is RO).
    """
    for row in si_skeleton_pack.generate_dataset(n, seed=seed):
        yield {**row, "country": COUNTRY}


def _gen_emso_selftest(rng: random.Random) -> str:
    return gen_person(rng).emso


# si-realskeleton-v1 pack. EMŠO/davčna številka/IBAN carry checksums (self-tested).
si_skeleton_pack = LocalePack(
    language="sl",
    name="Slovenian (real-skeleton)",
    checksummed_ids=(
        ChecksummedID("EMŠO", _gen_emso_selftest, emso_valid),
        ChecksummedID("davčna številka", gen_tax_number, tax_number_valid),
        ChecksummedID("IBAN", gen_iban_si, iban_si_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
)
