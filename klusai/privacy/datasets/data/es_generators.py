"""Checksum-valid, coherent Spanish PII generators (localized synthetic — not MT).

Same P0 contract as RO/PL/EN/IT/DE/FR: identifiers carry VALID checksums where the scheme defines
one. Pure, seeded, no LLM/network.

Identifiers:
  - **DNI / NIF** — 8 digits + a control letter (digits mod 23 indexed into a fixed table). The
    Spanish DNI is **coverage-only** (no embedded DOB/sex/place); we generate a valid value and
    validate it against ``europriv_bench.national_id`` (the single source of truth) so detection
    coverage is exercised, and we never decode/emit any quasi-identifier.
  - **NIE** — foreigner id: prefix letter (X/Y/Z) + 7 digits + control letter (same mod-23 table,
    prefix mapped X→0, Y→1, Z→2). Validated against the same benchmark validator.
  - **IBAN (ES)** — 24-char mod-97 IBAN: ES + 2 check + 4 bank + 4 branch + 2 control + 10 account.

Phone (+34) carries no published checksum and is documented as such.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from europriv_bench.national_id import _DNI_LETTERS, parse_national_id

MALE_NAMES = ["Antonio", "Manuel", "José", "Francisco", "David", "Javier", "Daniel", "Carlos"]
FEMALE_NAMES = ["María", "Carmen", "Ana", "Laura", "Marta", "Lucía", "Paula", "Sara"]
SURNAMES = ["García", "Rodríguez", "González", "Fernández", "López", "Martínez", "Sánchez", "Pérez"]
# (city, comunidad autónoma) — kept coherent so address city matches its region.
CITIES = [
    ("Madrid", "Comunidad de Madrid"), ("Barcelona", "Cataluña"), ("Valencia", "Comunidad Valenciana"),
    ("Sevilla", "Andalucía"), ("Zaragoza", "Aragón"), ("Málaga", "Andalucía"),
    ("Bilbao", "País Vasco"), ("Murcia", "Región de Murcia"),
]
STREETS = ["Calle Mayor", "Calle de Alcalá", "Gran Vía", "Calle Real", "Avenida de la Constitución"]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    dni: str          # 8 digits + control letter (coverage-only national id)
    city: str
    region: str
    address: str
    cp: str           # 5-digit postal code
    phone: str
    iban: str


def gen_dni(rng: random.Random) -> str:
    """Valid DNI: 8 digits + control letter (digits mod 23 → fixed table)."""
    number = rng.randint(0, 99999999)
    return f"{number:08d}{_DNI_LETTERS[number % 23]}"


def dni_valid(dni: str) -> bool:
    """True iff ``dni`` validates against the benchmark's DNI/NIF validator (source of truth)."""
    return parse_national_id(dni, "ES").valid


def gen_nie(rng: random.Random) -> str:
    """Valid NIE (foreigner id): prefix X/Y/Z + 7 digits + control letter."""
    prefix = rng.choice("XYZ")
    pref_digit = {"X": "0", "Y": "1", "Z": "2"}[prefix]
    body = rng.randint(0, 9999999)
    number = int(pref_digit + f"{body:07d}")
    return f"{prefix}{body:07d}{_DNI_LETTERS[number % 23]}"


def nie_valid(nie: str) -> bool:
    return parse_national_id(nie, "ES").valid


def gen_iban_es(rng: random.Random) -> str:
    """Valid Spanish IBAN (mod-97): ES + 2 check + 20-digit BBAN (bank/branch/control/account)."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(20))
    rearranged = bban + "ES00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"ES{check:02d}{bban}"


def iban_es_valid(iban: str) -> bool:
    if not iban.startswith("ES") or len(iban) != 24:
        return False
    rearranged = iban[4:] + iban[:4]
    try:
        return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1
    except ValueError:
        return False


def gen_phone_es(rng: random.Random) -> str:
    """Spanish mobile, +34 6NN NNN NNN (no checksum)."""
    return f"+34 {rng.choice([6, 7])}{rng.randint(10, 99)} {rng.randint(100, 999)} {rng.randint(100, 999)}"


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Spanish person (city matches its región; DNI checksum-valid)."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    city, region = rng.choice(CITIES)
    cp = f"{rng.randint(1000, 52999):05d}"
    return Person(
        first_name=first,
        last_name=rng.choice(SURNAMES),
        sex=sex,
        dni=gen_dni(rng),
        city=city,
        region=region,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {cp} {city}",
        cp=cp,
        phone=gen_phone_es(rng),
        iban=gen_iban_es(rng),
    )


__all__ = [
    "Person", "gen_dni", "dni_valid", "gen_nie", "nie_valid",
    "gen_iban_es", "iban_es_valid", "gen_phone_es", "gen_person", "CITIES",
]
