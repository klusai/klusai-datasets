"""Checksum-valid, coherent Polish PII generators (localized synthetic — not MT).

Same P0 contract as the Romanian generators: identifiers must carry VALID checksums and realistic
structure (else we teach models the wrong invariants). Pure, seeded, no LLM/network.

Identifiers:
  - **PESEL** — 11-digit national id. Digits 1-6 encode the birth date (the month field is offset by
    century: +0 for 1900s, +20 for 2000s, +80/+40/+60 for 1800s/2100s/2200s), digits 7-10 a serial,
    digit 10 the sex (odd=M, even=F), digit 11 a weighted-mod-10 checksum.
  - **NIP** — 10-digit taxpayer id with a weighted mod-11 control digit (control 10 is invalid → resampled).
  - **REGON-9** — 9-digit statistical id with a weighted mod-11 control digit.
  - **IBAN (PL)** — 28-char mod-97 IBAN: PL + 2 check + 8-digit bank/branch + 16-digit account.

There is no LLM step; PESEL sex/birth-date are coherent with the chosen Polish given name.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass

MALE_NAMES = ["Jan", "Piotr", "Krzysztof", "Tomasz", "Paweł", "Marcin", "Michał", "Andrzej"]
FEMALE_NAMES = ["Anna", "Katarzyna", "Maria", "Agnieszka", "Magdalena", "Joanna", "Barbara", "Ewa"]
# Surnames: masculine / feminine forms (the -ski/-ska agreement is real Polish morphology).
SURNAMES_M = ["Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kowalczyk", "Lewandowski", "Zieliński", "Szymański"]
SURNAMES_F = ["Nowak", "Kowalska", "Wiśniewska", "Wójcik", "Kowalczyk", "Lewandowska", "Zielińska", "Szymańska"]
# (city, voivodeship) pairs — kept coherent so address city matches its region.
CITIES = [
    ("Warszawa", "mazowieckie"), ("Kraków", "małopolskie"), ("Łódź", "łódzkie"),
    ("Wrocław", "dolnośląskie"), ("Poznań", "wielkopolskie"), ("Gdańsk", "pomorskie"),
    ("Szczecin", "zachodniopomorskie"), ("Lublin", "lubelskie"),
]
STREETS = ["ul. Marszałkowska", "ul. Długa", "al. Jerozolimskie", "ul. Floriańska", "ul. Piotrkowska"]

_PESEL_WEIGHTS = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
_NIP_WEIGHTS = [6, 5, 7, 2, 3, 4, 5, 6, 7]
_REGON9_WEIGHTS = [8, 9, 2, 3, 4, 5, 6, 7]
# Month-field century offsets for PESEL (HG-equivalent encoding).
_PESEL_CENTURY_OFFSET = {1800: 80, 1900: 0, 2000: 20, 2100: 40, 2200: 60}


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    pesel: str
    dob: str          # DD.MM.YYYY — DERIVED from the PESEL (stays consistent with it)
    city: str
    voivodeship: str
    address: str
    postcode: str     # NN-NNN
    phone: str
    iban: str


def _pesel_check_digit(first10: str) -> int:
    total = sum(int(d) * w for d, w in zip(first10, _PESEL_WEIGHTS))
    return (10 - total % 10) % 10


def gen_pesel(rng: random.Random, sex: str, birth_year: int | None = None) -> str:
    """Valid PESEL for a given sex, encoding a plausible (never future) birth date."""
    if birth_year is None:
        birth_year = rng.randint(1940, 2010)
    century = (birth_year // 100) * 100
    offset = _PESEL_CENTURY_OFFSET[century]
    yy = birth_year % 100
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)  # ≤28 → valid in every month
    serial = rng.randint(0, 99)
    # 10th digit (index 9) carries sex: odd=M, even=F.
    sex_digit = rng.randint(0, 9)
    if sex == "M" and sex_digit % 2 == 0:
        sex_digit = (sex_digit + 1) % 10
    elif sex == "F" and sex_digit % 2 == 1:
        sex_digit = (sex_digit + 1) % 10
    base = f"{yy:02d}{month + offset:02d}{day:02d}{serial:03d}{sex_digit}"
    return base + str(_pesel_check_digit(base))


def parse_pesel_dob(pesel: str) -> str:
    """Decode the birth date from a PESEL → 'DD.MM.YYYY' (inverse of the month-offset encoding)."""
    yy, mm_raw, dd = int(pesel[0:2]), int(pesel[2:4]), int(pesel[4:6])
    for century, offset in _PESEL_CENTURY_OFFSET.items():
        if offset <= mm_raw < offset + 13:
            month = mm_raw - offset
            year = century + yy
            return f"{dd:02d}.{month:02d}.{year:04d}"
    raise ValueError(f"unparseable PESEL month field: {pesel!r}")


def pesel_valid(pesel: str) -> bool:
    """True iff PESEL is 11 digits with a valid month field, plausible day, and valid checksum."""
    if not pesel.isdigit() or len(pesel) != 11:
        return False
    mm_raw, dd = int(pesel[2:4]), int(pesel[4:6])
    if not any(off <= mm_raw < off + 13 for off in _PESEL_CENTURY_OFFSET.values()):
        return False
    month = mm_raw - next(off for off in _PESEL_CENTURY_OFFSET.values() if off <= mm_raw < off + 13)
    if not (1 <= month <= 12 and 1 <= dd <= 31):
        return False
    return _pesel_check_digit(pesel[:10]) == int(pesel[10])


def pesel_sex(pesel: str) -> str:
    return "M" if int(pesel[9]) % 2 == 1 else "F"


def gen_nip(rng: random.Random) -> str:
    """Valid NIP (taxpayer id): 10 digits, weighted mod-11 control digit (control 10 resampled)."""
    while True:
        body = [rng.randint(0, 9) for _ in range(9)]
        control = sum(d * w for d, w in zip(body, _NIP_WEIGHTS)) % 11
        if control != 10:
            return "".join(map(str, body)) + str(control)


def nip_valid(nip: str) -> bool:
    if not nip.isdigit() or len(nip) != 10:
        return False
    control = sum(int(d) * w for d, w in zip(nip[:9], _NIP_WEIGHTS)) % 11
    return control != 10 and control == int(nip[9])


def gen_regon9(rng: random.Random) -> str:
    """Valid 9-digit REGON: weighted mod-11 control digit (control 10 → 0)."""
    body = [rng.randint(0, 9) for _ in range(8)]
    control = sum(d * w for d, w in zip(body, _REGON9_WEIGHTS)) % 11
    control = 0 if control == 10 else control
    return "".join(map(str, body)) + str(control)


def regon9_valid(regon: str) -> bool:
    if not regon.isdigit() or len(regon) != 9:
        return False
    control = sum(int(d) * w for d, w in zip(regon[:8], _REGON9_WEIGHTS)) % 11
    control = 0 if control == 10 else control
    return control == int(regon[8])


def gen_iban_pl(rng: random.Random) -> str:
    """Valid Polish IBAN (mod-97): PL + 2 check + 24-digit BBAN (8 bank/branch + 16 account)."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(24))
    rearranged = bban + "PL00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"PL{check:02d}{bban}"


def iban_pl_valid(iban: str) -> bool:
    if not iban.startswith("PL") or len(iban) != 28:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def gen_phone_pl(rng: random.Random) -> str:
    """Polish mobile, +48 NNN NNN NNN (no checksum — documented as such)."""
    return f"+48 {rng.randint(500, 899)} {rng.randint(100, 999)} {rng.randint(100, 999)}"


def gen_dowod(rng: random.Random) -> str:
    """Polish ID-card number 'dowód osobisty' format: 3 letters + 6 digits (no public checksum)."""
    letters = "".join(rng.choice(string.ascii_uppercase) for _ in range(3))
    return f"{letters} {rng.randint(100000, 999999)}"


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Polish person: PESEL sex matches the name, DOB derived from the PESEL,
    surname morphology agrees with sex, address city matches its voivodeship."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    last = rng.choice(SURNAMES_M if sex == "M" else SURNAMES_F)
    pesel = gen_pesel(rng, sex)
    city, voiv = rng.choice(CITIES)
    return Person(
        first_name=first,
        last_name=last,
        sex=sex,
        pesel=pesel,
        dob=parse_pesel_dob(pesel),  # consistent with the PESEL by construction
        city=city,
        voivodeship=voiv,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {rng.randint(0, 99):02d}-{rng.randint(0, 999):03d} {city}",
        postcode=f"{rng.randint(0, 99):02d}-{rng.randint(0, 999):03d}",
        phone=gen_phone_pl(rng),
        iban=gen_iban_pl(rng),
    )


__all__ = [
    "Person", "gen_pesel", "parse_pesel_dob", "pesel_valid", "pesel_sex",
    "gen_nip", "nip_valid", "gen_regon9", "regon9_valid",
    "gen_iban_pl", "iban_pl_valid", "gen_phone_pl", "gen_dowod", "gen_person",
    "CITIES",
]
