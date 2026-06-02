"""Checksum-valid, coherent Dutch PII generators (localized synthetic — not MT).

Same P0 contract as RO/PL/EN/IT/DE/FR/ES: identifiers carry VALID checksums where the scheme defines
one. Pure, seeded, no LLM/network.

Identifiers:
  - **BSN** (burgerservicenummer) — 9-digit national id validated by the "11-test": the weighted sum
    ``9·d1 + 8·d2 + … + 2·d8 − 1·d9`` must be a non-zero multiple of 11. Coverage-only
    quasi-identifier-wise (no DOB/sex), but it HAS a checksum, so we generate valid values and
    self-test them.
  - **KvK-nummer** — 8-digit Chamber-of-Commerce number (no public checksum → documented, not faked).
  - **IBAN (NL)** — 18-char mod-97 IBAN: NL + 2 check + 4-letter bank code + 10-digit account.

Phone (+31) carries no published checksum and is documented as such.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass

MALE_NAMES = ["Daan", "Sem", "Lucas", "Finn", "Levi", "Bram", "Thomas", "Jesse"]
FEMALE_NAMES = ["Emma", "Julia", "Mila", "Tess", "Sophie", "Anna", "Eva", "Lotte"]
# Dutch surnames including tussenvoegsel ("van", "de") — kept as one surname token.
SURNAMES = ["de Jong", "Jansen", "de Vries", "van den Berg", "van Dijk", "Bakker", "Visser", "Smit"]
# (city, provincie) — kept coherent so address city matches its province.
CITIES = [
    ("Amsterdam", "Noord-Holland"), ("Rotterdam", "Zuid-Holland"), ("Den Haag", "Zuid-Holland"),
    ("Utrecht", "Utrecht"), ("Eindhoven", "Noord-Brabant"), ("Groningen", "Groningen"),
    ("Tilburg", "Noord-Brabant"), ("Nijmegen", "Gelderland"),
]
STREETS = ["Hoofdstraat", "Kerkstraat", "Dorpsstraat", "Schoolstraat", "Stationsstraat"]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    bsn: str
    city: str
    province: str
    address: str
    postcode: str     # NNNN AA
    phone: str
    iban: str


def _bsn_weighted_sum(digits: str) -> int:
    """11-test weighted sum: weights 9,8,7,6,5,4,3,2 for d1..d8 and −1 for d9."""
    weights = [9, 8, 7, 6, 5, 4, 3, 2, -1]
    return sum(int(d) * w for d, w in zip(digits, weights))


def gen_bsn(rng: random.Random) -> str:
    """Valid 9-digit BSN (passes the 11-test: weighted sum a non-zero multiple of 11)."""
    while True:
        digits = "".join(str(rng.randint(0, 9)) for _ in range(9))
        total = _bsn_weighted_sum(digits)
        if total != 0 and total % 11 == 0:
            return digits


def bsn_valid(bsn: str) -> bool:
    if not bsn.isdigit() or len(bsn) != 9:
        return False
    total = _bsn_weighted_sum(bsn)
    return total != 0 and total % 11 == 0


def gen_kvk(rng: random.Random) -> str:
    """Dutch Chamber-of-Commerce number: 8 digits (no public checksum)."""
    return f"{rng.randint(10000000, 99999999)}"


def gen_iban_nl(rng: random.Random) -> str:
    """Valid Dutch IBAN (mod-97): NL + 2 check + 4-letter bank code + 10-digit account."""
    bank = "".join(rng.choice(string.ascii_uppercase) for _ in range(4))
    bban = bank + "".join(str(rng.randint(0, 9)) for _ in range(10))
    rearranged = bban + "NL00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"NL{check:02d}{bban}"


def iban_nl_valid(iban: str) -> bool:
    if not iban.startswith("NL") or len(iban) != 18:
        return False
    rearranged = iban[4:] + iban[:4]
    try:
        return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1
    except ValueError:
        return False


def gen_phone_nl(rng: random.Random) -> str:
    """Dutch mobile, +31 6 NNNNNNNN (no checksum)."""
    return f"+31 6 {rng.randint(10000000, 99999999)}"


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Dutch person (city matches its province; BSN checksum-valid)."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    city, province = rng.choice(CITIES)
    postcode = f"{rng.randint(1000, 9999)} {rng.choice(string.ascii_uppercase)}{rng.choice(string.ascii_uppercase)}"
    return Person(
        first_name=first,
        last_name=rng.choice(SURNAMES),
        sex=sex,
        bsn=gen_bsn(rng),
        city=city,
        province=province,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {postcode} {city}",
        postcode=postcode,
        phone=gen_phone_nl(rng),
        iban=gen_iban_nl(rng),
    )


__all__ = [
    "Person", "gen_bsn", "bsn_valid", "gen_kvk", "gen_iban_nl", "iban_nl_valid",
    "gen_phone_nl", "gen_person", "CITIES",
]
