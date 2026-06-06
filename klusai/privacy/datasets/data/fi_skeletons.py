"""fi-realskeleton-v1: faithful real-structure Finnish documents + synthetic PII.

The Finnish sibling of ``se_skeletons`` / ``cz_skeletons``: documents that mirror the STRUCTURE and
boilerplate of real Finnish official document types — a hospital discharge summary (`Hoitopalaute /
Epikriisi`), a services agreement (`Sopimus palveluista`), a sworn declaration (`Kunnian ja omantunnon
kautta annettu vakuutus`), and an administrative decision letter (`Päätös`) — populated with
**synthetic** Finnish identifiers (checksum-valid henkilötunnus, henkilötunnus-consistent date of
birth, Y-tunnus, Finnish IBAN, +358 phones, addresses).

Because the skeletons are authored faithful reproductions of *public document structure* (not
scraped real records), there is **no residual real PII by construction** — every identifier is
synthetic — so the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a
quality spot-check, not a personal-data hunt.

Offset-determinism, the byte-equality assert and the strict BIOES gate are inherited unchanged from
the shared ``localepack.fill_document`` (same invariants as RO/PL/IT/SE/CZ). This is a **decode-
bearing** measurement: a missed (un-redacted) henkilötunnus deterministically discloses
DATE_OF_BIRTH + SEX (the full date is recoverable — the century comes from the marker; the
individual-number parity gives sex). The control character is the ISO-7064-style mod-31 char over
``DDMMYYZZZ``. Scored zero-shot with ``national_id_leakage`` (``country='FI'`` on every row
dispatches to the henkilötunnus validator). This config is ``config_status=dev`` — a citable-track
candidate, not yet validated (pending native-speaker review + IAA). All four templates are one
authored skeleton family sharing a single fill path; a leak headline from a single template family
is not validated generalization — a second independent template family is required before this is
cited.

Re-identification accounting is **per distinct subject** (KLU-49): the discharge summary deliberately
repeats the patient's henkilötunnus — once in the identity header and again in the
`Henkilötunnus (potilaan tunniste)` line, as real Finnish epikriisit do — so the gold count and leak
metric must NOT double-count that subject. The harness ``national_id_leakage`` dedups by
``(document, country, normalized value)``; this module emits ``country="FI"`` on every row so the
metric dispatches to the henkilötunnus validator (not the RO/CNP default).
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from .fi_generators import (
    gen_iban_fi,
    gen_person,
    gen_ytunnus,
    hetu_valid,
    iban_fi_valid,
    ytunnus_valid,
)
from .localepack import ChecksummedID, Doc, LocalePack

COUNTRY = "FI"

HOSPITALS = ["Helsingin yliopistollinen sairaala", "Tampereen yliopistollinen sairaala",
             "Turun yliopistollinen sairaala", "Oulun yliopistollinen sairaala"]
COMPANIES = ["Esimerkki Oy", "TechPlus Oy", "Pohjoinen Konsultti Oy", "MediHoito Oy"]
CONDITIONS = [
    "essentiaalinen verenpainetauti", "tyypin 2 diabetes", "keuhkokuume",
    "krooninen gastriitti", "iskias", "akuutti keuhkoputkentulehdus",
]
WARDS = ["Sisätautien osasto", "Kardiologian osasto", "Kirurgian osasto", "Neurologian osasto"]


def _ascii(s: str) -> str:
    s = s.replace("ä", "a").replace("ö", "o").replace("å", "a")
    return s.replace("Ä", "A").replace("Ö", "O").replace("Å", "A")


# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two
# entities share a whitespace token (the strict BIOES gate fails loud otherwise).
TEMPLATES = [
    ("clinical", """HOITOPALAUTE / EPIKRIISI

{hospital} — {ward}

Potilas: {patient}
Henkilötunnus: {hetu} , puhelin: {phone}
Syntymäaika: {dob} , kotiosoite: {address}

Päädiagnoosi: {condition} .
Esitiedot: potilas hakeutui hoitoon {date} kuvatuin oirein.
Suositukset kotiutuksessa: hoito ohjeen mukaan, kontrolli 30 päivän kuluttua.

Henkilötunnus (potilaan tunniste): {hetu_id}
Vastaava lääkäri: LL {doctor}
Antopäivä: {date}"""),

    ("legal", """SOPIMUS PALVELUISTA
Nro {contractno} , päivätty {date}

Sopimusosapuolet:
1. {company} , kotipaikka osoitteessa {address2} , Y-tunnus {ytunnus} ,
   pankkitili IBAN {iban} , edustajana {doctor} ;
2. {patient} , henkilötunnus {hetu} , asuu osoitteessa {address} , puhelin {phone} ,
   sähköposti {email} .

Sopimuksen kohteena on osapuolten sopimien palveluiden tuottaminen.
Tämä sopimus on laadittu {date} kahtena samansisältöisenä kappaleena."""),

    ("legal", """VAKUUTUS KUNNIAN JA OMANTUNNON KAUTTA

Minä, allekirjoittanut {patient} , henkilötunnus {hetu} , asuu osoitteessa {address} ,
puhelin {phone} , sähköposti {email} , vakuutan kunnian ja omantunnon kautta, tietoisena
väärän vakuutuksen rangaistavuudesta, että annetut tiedot ovat oikeita.

Päiväys: {date}
Allekirjoitus: ____________"""),

    ("admin", """Vastaanottaja: {patient}
Osoite: {address}

Asia: asia nro {contractno} / {date}

Hyvä {patient} , ilmoitamme, että hakemuksenne on rekisteröity.
Lisätietoja varten ottakaa yhteyttä numeroon {phone} tai {email} .

Ystävällisin terveisin,
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
        "hetu": (patient.hetu, "NATIONAL_ID"),
        # Real Finnish epikriisit repeat the henkilötunnus as the patient identifier. Same VALUE as
        # {hetu} → the per-subject dedup in national_id_leakage collapses it (KLU-49 guard); it is
        # NOT a second subject and must not inflate the gold count.
        "hetu_id": (patient.hetu, "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),  # DERIVED from the henkilötunnus → birthday matches it
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.fi", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "ytunnus": (gen_ytunnus(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} , {patient.region}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "contractno": (f"{rng.randint(100, 9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(2018, 2025)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure FI document (shared splice/byte-equality/strict-BIOES gate)."""
    return fi_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield n offset-validated faithful-structure FI documents.

    Each row carries ``country='FI'`` so the country-dispatched ``national_id_leakage`` metric
    validates the gold IDs with the henkilötunnus validator (the default country is RO).
    """
    for row in fi_skeleton_pack.generate_dataset(n, seed=seed):
        yield {**row, "country": COUNTRY}


def _gen_hetu_selftest(rng: random.Random) -> str:
    return gen_person(rng).hetu


# fi-realskeleton-v1 pack. henkilötunnus/Y-tunnus/IBAN carry checksums/control chars (self-tested).
fi_skeleton_pack = LocalePack(
    language="fi",
    name="Finnish (real-skeleton)",
    checksummed_ids=(
        ChecksummedID("henkilötunnus", _gen_hetu_selftest, hetu_valid),
        ChecksummedID("Y-tunnus", gen_ytunnus, ytunnus_valid),
        ChecksummedID("IBAN", gen_iban_fi, iban_fi_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
)
