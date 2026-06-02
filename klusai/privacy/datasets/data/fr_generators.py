"""Checksum-valid, coherent French PII generators (localized synthetic — not MT).

Same P0 contract as RO/PL/EN/IT/DE: identifiers carry VALID checksums where the scheme defines one.
Pure, seeded, no LLM/network.

Identifiers:
  - **NIR** (numéro de sécurité sociale / INSEE) — 15-digit national id ``S YY MM DD CCC OOO K``:
    sex digit (1=M, 2=F), 2-digit year, 2-digit month, department + commune codes, order number, and
    a 2-digit control key ``K = 97 − (N mod 97)`` over the 13-digit body. The NIR encodes sex + birth
    year/month (decode-bearing); here the generated NIR's sex is kept coherent with the chosen name.
  - **SIREN** — 9-digit company id with a Luhn (mod-10) check.
  - **IBAN (FR)** — 27-char mod-97 IBAN: FR + 2 check + 10-digit bank/branch + 11-char account + 2 RIB.

Phone (+33) carries no published checksum and is documented as such.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

MALE_NAMES = ["Lucas", "Hugo", "Louis", "Gabriel", "Jules", "Arthur", "Nathan", "Léo"]
FEMALE_NAMES = ["Emma", "Jade", "Louise", "Alice", "Chloé", "Léa", "Manon", "Camille"]
SURNAMES = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand"]
# (city, région) — kept coherent so address city matches its region.
CITIES = [
    ("Paris", "Île-de-France"), ("Marseille", "Provence-Alpes-Côte d'Azur"),
    ("Lyon", "Auvergne-Rhône-Alpes"), ("Toulouse", "Occitanie"), ("Nice", "Provence-Alpes-Côte d'Azur"),
    ("Nantes", "Pays de la Loire"), ("Strasbourg", "Grand Est"), ("Bordeaux", "Nouvelle-Aquitaine"),
]
STREETS = ["Rue de la Paix", "Avenue des Champs", "Rue Victor Hugo", "Boulevard Voltaire", "Rue Gambetta"]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    nir: str          # 15-digit numéro de sécurité sociale (with control key)
    city: str
    region: str
    address: str
    code_postal: str  # 5-digit postal code
    phone: str
    iban: str


def _nir_key(body13: str) -> int:
    """Control key for a NIR: 97 − (13-digit body mod 97)."""
    return 97 - (int(body13) % 97)


def gen_nir(rng: random.Random, sex: str | None = None) -> str:
    """Valid 15-digit NIR; sex digit (1=M, 2=F) coherent, encoding a plausible birth year/month."""
    if sex is None:
        sex = rng.choice(["M", "F"])
    s = "1" if sex == "M" else "2"
    yy = rng.randint(40, 99)
    mm = rng.randint(1, 12)
    dept = rng.randint(1, 95)
    commune = rng.randint(1, 999)
    order = rng.randint(1, 999)
    body = f"{s}{yy:02d}{mm:02d}{dept:02d}{commune:03d}{order:03d}"
    return body + f"{_nir_key(body):02d}"


def nir_valid(nir: str) -> bool:
    """True iff NIR is 15 digits with a valid control key and a plausible month field."""
    if not nir.isdigit() or len(nir) != 15:
        return False
    if not 1 <= int(nir[3:5]) <= 12:
        return False
    return _nir_key(nir[:13]) == int(nir[13:15])


def nir_sex(nir: str) -> str:
    return "M" if nir[0] == "1" else "F"


def _luhn_check_digit(body: str) -> int:
    total = 0
    for i, ch in enumerate(reversed(body)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10


def luhn_valid(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def gen_siren(rng: random.Random) -> str:
    """Valid 9-digit SIREN with a Luhn (mod-10) check."""
    body = "".join(str(rng.randint(0, 9)) for _ in range(8))
    return body + str(_luhn_check_digit(body))


def siren_valid(siren: str) -> bool:
    return siren.isdigit() and len(siren) == 9 and luhn_valid(siren)


def gen_iban_fr(rng: random.Random) -> str:
    """Valid French IBAN (mod-97): FR + 2 check + 23-char BBAN (bank/branch + account + RIB key)."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(23))
    rearranged = bban + "FR00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"FR{check:02d}{bban}"


def iban_fr_valid(iban: str) -> bool:
    if not iban.startswith("FR") or len(iban) != 27:
        return False
    rearranged = iban[4:] + iban[:4]
    try:
        return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1
    except ValueError:
        return False


def gen_phone_fr(rng: random.Random) -> str:
    """French mobile, +33 6 NN NN NN NN (no checksum)."""
    return f"+33 {rng.choice([6, 7])} {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)}"


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic French person (NIR sex matches the name; city matches its region)."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    city, region = rng.choice(CITIES)
    cp = f"{rng.randint(1000, 95999):05d}"
    return Person(
        first_name=first,
        last_name=rng.choice(SURNAMES),
        sex=sex,
        nir=gen_nir(rng, sex),
        city=city,
        region=region,
        address=f"{rng.randint(1, 200)} {rng.choice(STREETS)}, {cp} {city}",
        code_postal=cp,
        phone=gen_phone_fr(rng),
        iban=gen_iban_fr(rng),
    )


__all__ = [
    "Person", "gen_nir", "nir_valid", "nir_sex", "gen_siren", "siren_valid",
    "gen_iban_fr", "iban_fr_valid", "gen_phone_fr", "gen_person", "CITIES",
]
