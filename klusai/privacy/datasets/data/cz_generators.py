"""Checksum-valid, coherent Czech PII generators (localized synthetic — not MT).

Same P0 contract as the Romanian/Polish generators: identifiers must carry VALID checksums and
realistic structure (else we teach models the wrong invariants). Pure, seeded, no LLM/network.

Identifiers:
  - **rodné číslo** (birth number) — 10-digit national id ``YYMMDD/SSSC``. Digits 1-6 encode the
    birth date with the month carrying sex (female = month +50), the serial SSS separates births on
    the same day, and the 10th digit C is chosen so the **whole 10-digit number is divisible by 11**
    (mod-11). DOB and sex are coherent with the chosen name. We emit the modern post-1954 10-digit
    form (always with a check digit); century follows the YY>=54 -> 19YY, YY<=53 -> 20YY convention.
  - **IČO** — 8-digit company id with a weighted mod-11 control digit.
  - **IBAN (CZ)** — 24-char mod-97 IBAN: CZ + 2 check + 4-digit bank + 16-digit account.

There is no LLM step; rodné číslo sex/birth-date are coherent with the chosen Czech given name.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass

MALE_NAMES = ["Jan", "Petr", "Jakub", "Tomáš", "Martin", "Pavel", "Josef", "Lukáš"]
FEMALE_NAMES = ["Jana", "Eva", "Hana", "Anna", "Marie", "Lucie", "Tereza", "Kateřina"]
# Surnames: masculine / feminine forms (the -ová feminine suffix is real Czech morphology).
SURNAMES_M = ["Novák", "Svoboda", "Novotný", "Dvořák", "Černý", "Procházka", "Kučera", "Veselý"]
SURNAMES_F = ["Nováková", "Svobodová", "Novotná", "Dvořáková", "Černá", "Procházková", "Kučerová", "Veselá"]
# (city, region/kraj) pairs — kept coherent so address city matches its region.
CITIES = [
    ("Praha", "Hlavní město Praha"), ("Brno", "Jihomoravský kraj"),
    ("Ostrava", "Moravskoslezský kraj"), ("Plzeň", "Plzeňský kraj"),
    ("Liberec", "Liberecký kraj"), ("Olomouc", "Olomoucký kraj"),
    ("České Budějovice", "Jihočeský kraj"), ("Hradec Králové", "Královéhradecký kraj"),
]
STREETS = ["Hlavní", "Nádražní", "Masarykova", "Komenského", "Husova", "Školní"]

_ICO_WEIGHTS = [8, 7, 6, 5, 4, 3, 2]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    rodne_cislo: str
    dob: str          # YYYY-MM-DD — DERIVED from the rodné číslo (stays consistent with it)
    city: str
    region: str
    address: str
    postcode: str     # NNN NN
    phone: str
    iban: str


def gen_rodne_cislo(rng: random.Random, sex: str, birth_year: int | None = None) -> tuple[str, str]:
    """Valid 10-digit rodné číslo for a given sex + its derived ISO DOB.

    Returns ``(rodne_cislo, 'YYYY-MM-DD')``. Female births carry month +50; the check digit is
    chosen so the whole 10-digit number is divisible by 11 (post-1954 modern form). The printed
    form uses a ``/`` before the serial (``YYMMDD/SSSC``).
    """
    if birth_year is None:
        birth_year = rng.randint(1955, 2010)  # modern 10-digit form (>= 1954)
    yy = birth_year % 100
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    mm_field = month + 50 if sex == "F" else month
    # Pick a serial whose mod-11 check digit closes cleanly (avoid the historical remainder-10 case).
    while True:
        serial = rng.randint(1, 999)
        first9 = f"{yy:02d}{mm_field:02d}{day:02d}{serial:03d}"
        # The WHOLE 10-digit number must be divisible by 11: choose c so (first9*10 + c) % 11 == 0.
        check = (11 - (int(first9) * 10) % 11) % 11
        if check != 10:  # remainder-10 would force the historical c=0 special case — skip for clean gen
            rc = first9 + str(check)
            return f"{rc[:6]}/{rc[6:]}", f"{birth_year:04d}-{month:02d}-{day:02d}"


def rodne_cislo_valid(value: str) -> bool:
    """True iff a 10-digit rodné číslo (``/`` optional) is divisible by 11 (modern post-1954 form)."""
    s = value.replace("/", "").replace(" ", "")
    if len(s) != 10 or not s.isdigit():
        return False
    return int(s) % 11 == 0 or (int(s[:9]) % 11 == 10 and s[9] == "0")


def rodne_cislo_sex(value: str) -> str:
    s = value.replace("/", "").replace(" ", "")
    mm = int(s[2:4])
    return "F" if (51 <= mm <= 62 or 71 <= mm <= 82) else "M"


def gen_ico(rng: random.Random) -> str:
    """Valid Czech IČO: 8 digits, weighted mod-11 control digit."""
    while True:
        body = [rng.randint(0, 9) for _ in range(7)]
        total = sum(d * w for d, w in zip(body, _ICO_WEIGHTS))
        check = (11 - total % 11) % 10
        return "".join(map(str, body)) + str(check)


def ico_valid(value: str) -> bool:
    s = value.replace(" ", "")
    if len(s) != 8 or not s.isdigit():
        return False
    total = sum(int(d) * w for d, w in zip(s[:7], _ICO_WEIGHTS))
    return (11 - total % 11) % 10 == int(s[7])


def gen_iban_cz(rng: random.Random) -> str:
    """Valid Czech IBAN (mod-97): CZ + 2 check + 20-digit BBAN (4 bank + 16 account)."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(20))
    rearranged = bban + "CZ00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"CZ{check:02d}{bban}"


def iban_cz_valid(iban: str) -> bool:
    if not iban.startswith("CZ") or len(iban) != 24:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def gen_phone_cz(rng: random.Random) -> str:
    """Czech mobile, +420 NNN NNN NNN (no checksum — documented as such)."""
    return f"+420 {rng.randint(601, 799)} {rng.randint(100, 999)} {rng.randint(100, 999)}"


def _ascii(s: str) -> str:
    """ASCII-fold Czech diacritics for realistic emails."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Czech person: rodné číslo sex matches the name, DOB derived from the
    rodné číslo, surname morphology agrees with sex, address city matches its region."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    last = rng.choice(SURNAMES_M if sex == "M" else SURNAMES_F)
    rc, dob = gen_rodne_cislo(rng, sex)
    city, region = rng.choice(CITIES)
    return Person(
        first_name=first,
        last_name=last,
        sex=sex,
        rodne_cislo=rc,
        dob=dob,  # consistent with the rodné číslo by construction
        city=city,
        region=region,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {rng.randint(100, 799)} {rng.randint(10, 99)} {city}",
        postcode=f"{rng.randint(100, 799)} {rng.randint(10, 99)}",
        phone=gen_phone_cz(rng),
        iban=gen_iban_cz(rng),
    )


__all__ = [
    "Person", "gen_rodne_cislo", "rodne_cislo_valid", "rodne_cislo_sex",
    "gen_ico", "ico_valid", "gen_iban_cz", "iban_cz_valid", "gen_phone_cz",
    "gen_person", "CITIES",
]
