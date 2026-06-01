"""pl-realskeleton-v1: faithful real-structure Polish documents + synthetic PII.

The Polish sibling of ``ro_skeletons`` (``ro-realskeleton-v1``): documents that mirror the
STRUCTURE and boilerplate of real Polish official document types — a hospital discharge card
(`KARTA INFORMACYJNA LECZENIA SZPITALNEGO`), a services contract (`UMOWA O ŚWIADCZENIE USŁUG`),
a declaration on own responsibility (`OŚWIADCZENIE`), and an administrative letter — populated
with **synthetic** Polish identifiers (checksum-valid PESEL, PESEL-consistent date of birth,
NIP, Polish IBAN, +48 phones, addresses), with Polish gender agreement.

Because the skeletons are authored faithful reproductions of *public document structure* (not
scraped real records), there is **no residual real PII by construction** — every identifier is
synthetic — so the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a
quality spot-check, not a personal-data hunt.

Offset-determinism, the byte-equality assert and the strict BIOES gate are inherited unchanged
from the shared ``localepack.fill_document`` (same invariants as RO). This is the **second
decode-bearing track** (PESEL/PL) replicating the RO/CNP protection measurement: scored with
``national_id_leakage`` (a missed PESEL deterministically discloses DATE_OF_BIRTH + SEX).

Re-identification accounting is **per distinct subject** (KLU-49): the discharge-card template
deliberately repeats the patient's PESEL — once in the identity header and again in the
`Identyfikator pacjenta (PESEL)` line, exactly as real Polish discharge cards do — so the gold
count and leak metric must NOT double-count that subject. The harness ``national_id_leakage``
dedups by ``(document, country, normalized value)``; this module emits ``country="PL"`` on every
row so the metric dispatches to the PESEL validator (not the RO/CNP default).
"""

from __future__ import annotations

import random
import unicodedata
from collections.abc import Iterator

from .localepack import ChecksummedID, Doc, LocalePack
from .pl_generators import (
    CITIES,
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

COUNTRY = "PL"

HOSPITALS = ["Szpital Wojewódzki", "Szpital Miejski", "Szpital Kliniczny", "Szpital Specjalistyczny"]
COMPANIES = ["Przykład Sp. z o.o.", "TechPlus S.A.", "BiuroRach Sp. z o.o.", "MediCare Sp. z o.o."]
CONDITIONS = [
    "nadciśnienie tętnicze samoistne", "cukrzyca typu 2", "zapalenie płuc",
    "przewlekłe zapalenie żołądka", "rwa kulszowa", "ostre zapalenie oskrzeli",
]
WARDS = ["Oddział Chorób Wewnętrznych", "Oddział Kardiologii", "Oddział Chirurgii Ogólnej", "Oddział Neurologii"]


def _ascii(s: str) -> str:
    """ASCII-fold Polish diacritics (ł handled explicitly) for realistic emails."""
    s = s.replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two
# entities share a whitespace token (the strict BIOES gate fails loud otherwise).
TEMPLATES = [
    ("clinical", """KARTA INFORMACYJNA LECZENIA SZPITALNEGO

{hospital} — {ward}

Pacjent: {patient}
PESEL: {pesel} , telefon: {phone}
Data urodzenia: {dob} , adres zamieszkania: {address}

Rozpoznanie zasadnicze: {condition} .
Wywiad: {pacjent_word} zgłosił się w dniu {date} z opisaną symptomatologią.
Zalecenia przy wypisie: leczenie zgodnie ze schematem, kontrola za 30 dni.

Identyfikator pacjenta (PESEL): {pesel_id}
Lekarz prowadzący: dr {doctor}
Data wystawienia: {date}"""),

    ("legal", """UMOWA O ŚWIADCZENIE USŁUG
Nr {contractno} z dnia {date}

Strony umowy:
1. {company} , z siedzibą pod adresem {address2} , NIP {nip} , REGON {regon} ,
   rachunek IBAN {iban} , reprezentowana przez {doctor} ;
2. {patient} , PESEL {pesel} , {zamieszkaly} pod adresem {address} , telefon {phone} ,
   e-mail {email} .

Przedmiotem umowy jest świadczenie usług uzgodnionych przez strony.
Niniejszą umowę zawarto w dniu {date} , w dwóch jednobrzmiących egzemplarzach."""),

    ("legal", """OŚWIADCZENIE

Ja, {nizej} {patient} , PESEL {pesel} , legitymujący się dowodem osobistym {dowod} ,
{zamieszkaly} pod adresem {address} , telefon {phone} , e-mail {email} , oświadczam zgodnie
z prawdą, świadomy odpowiedzialności karnej za składanie fałszywych oświadczeń, że podane
dane są prawdziwe.

Data: {date}
Podpis: ____________"""),

    ("admin", """Do: {patient}
Adres: {address}

Dot.: sprawy nr {contractno} / {date}

{salutation} {patient} , informujemy, że Pana/Pani wniosek został zarejestrowany.
W celu uzyskania dodatkowych informacji prosimy o kontakt pod numerem {phone} lub {email} .

Z poważaniem,
{doctor}
{company}
{date}"""),
]


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    patient = gen_person(rng)
    doctor = gen_person(rng)
    _, voiv = rng.choice(CITIES)
    m = patient.sex == "M"  # Polish gender agreement for boilerplate (not PII → label "O")
    return {
        "nizej": ("niżej podpisany" if m else "niżej podpisana", "O"),
        "zamieszkaly": ("zamieszkały" if m else "zamieszkała", "O"),
        "salutation": ("Szanowny Panie" if m else "Szanowna Pani", "O"),
        "pacjent_word": ("Pacjent" if m else "Pacjentka", "O"),
        "ward": (rng.choice(WARDS), "O"),  # not PII — rendered as plain text, no span
        "patient": (f"{patient.first_name} {patient.last_name}", "PERSON"),
        "doctor": (f"{doctor.first_name} {doctor.last_name}", "PERSON"),
        "pesel": (patient.pesel, "NATIONAL_ID"),
        # Real Polish discharge cards repeat the PESEL as the patient identifier. Same VALUE as
        # {pesel} → the per-subject dedup in national_id_leakage collapses it (KLU-49 guard); it is
        # NOT a second subject and must not inflate the gold count.
        "pesel_id": (patient.pesel, "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),  # DERIVED from the PESEL → birthday matches the PESEL
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.pl", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "nip": (gen_nip(rng), "COMPANY_ID"),
        "regon": (gen_regon9(rng), "COMPANY_ID"),
        "dowod": (gen_dowod(rng), "NATIONAL_ID"),  # dowód osobisty — no checksum (see no_checksum_ids)
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} w {voiv}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "contractno": (f"{rng.randint(100, 9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(2018, 2025)}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure PL document (shared splice/byte-equality/strict-BIOES gate)."""
    return pl_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield n offset-validated faithful-structure PL documents.

    Each row carries ``country='PL'`` so the country-dispatched ``national_id_leakage`` metric
    validates the gold IDs with the PESEL validator (the default country is RO).
    """
    for row in pl_skeleton_pack.generate_dataset(n, seed=seed):
        yield {**row, "country": COUNTRY}


def _gen_pesel_selftest(rng: random.Random) -> str:
    return gen_person(rng).pesel


# pl-realskeleton-v1 pack. PESEL/NIP/REGON/IBAN carry checksums (self-tested); the dowód osobisty
# carries no published checksum so it is documented under ``no_checksum_ids`` rather than faked.
pl_skeleton_pack = LocalePack(
    language="pl",
    name="Polish (real-skeleton)",
    checksummed_ids=(
        ChecksummedID("PESEL", _gen_pesel_selftest, pesel_valid),
        ChecksummedID("NIP", gen_nip, nip_valid),
        ChecksummedID("REGON9", gen_regon9, regon9_valid),
        ChecksummedID("IBAN", gen_iban_pl, iban_pl_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
    no_checksum_ids=("dowód osobisty",),  # Polish ID-card number carries no published checksum
)
