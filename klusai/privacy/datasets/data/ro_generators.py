"""Checksum-valid, coherent Romanian PII generators (localized synthetic — not MT).

The panel review's P0: generated identifiers must have VALID checksums (else we teach models the
wrong invariants and a checksum-aware competitor looks artificially better), realistic
distributions, and cross-field coherence (a person's CNP county must match their address county,
CNP sex must match the chosen name). These are pure, seeded (deterministic) generators with no
LLM/network — they produce the PII values that get spliced into document skeletons downstream.

CNP checksum is computed via `europriv_bench.national_id` (single source of truth) so generated
CNPs decode consistently in the `cnp_leakage` metric.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass

from europriv_bench.national_id import check_digit, validate_cnp

# (CNP county code, plate prefix, county name) — a curated, correct subset.
COUNTIES = [
    ("12", "CJ", "Cluj"), ("35", "TM", "Timiș"), ("22", "IS", "Iași"),
    ("08", "BV", "Brașov"), ("13", "CT", "Constanța"), ("40", "B", "București"),
    ("05", "BH", "Bihor"), ("16", "DJ", "Dolj"), ("29", "PH", "Prahova"), ("32", "SB", "Sibiu"),
]
MALE_NAMES = ["Andrei", "Mihai", "Ștefan", "Ionuț", "Cătălin", "Bogdan", "Vlad", "Cristian"]
FEMALE_NAMES = ["Maria", "Elena", "Ioana", "Andreea", "Gabriela", "Raluca", "Ștefania", "Alina"]
SURNAMES = ["Popescu", "Ionescu", "Pop", "Dumitru", "Stoica", "Munteanu", "Constantin", "Radu"]
STREETS = ["Strada Victoriei", "Bulevardul Unirii", "Strada Mihai Eminescu", "Calea Dorobanți"]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    cnp: str
    county: str       # name
    address: str
    postcode: str
    phone: str
    iban: str


def gen_cnp(rng: random.Random, county_code: str, sex: str) -> str:
    """Valid CNP for a given county + sex (1900s/2000s births)."""
    s = rng.choice([1, 5]) if sex == "M" else rng.choice([2, 6])  # century+sex digit
    year = rng.randint(0, 99)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    seq = rng.randint(1, 999)
    base = f"{s}{year:02d}{month:02d}{day:02d}{county_code}{seq:03d}"
    return base + str(check_digit(base))


def gen_iban_ro(rng: random.Random) -> str:
    """Valid Romanian IBAN (mod-97): RO + 2 check + 4-letter bank + 16 alnum BBAN."""
    bank = "".join(rng.choice(string.ascii_uppercase) for _ in range(4))
    bban = bank + "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(16))
    # check digits: move country+00 to the end, convert letters→numbers, 98 - (n mod 97)
    rearranged = bban + "RO00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"RO{check:02d}{bban}"


def gen_cui(rng: random.Random) -> str:
    """Valid Romanian CUI (fiscal code) with its mod-11 control digit."""
    key = [7, 5, 3, 2, 1, 7, 5, 3, 2]
    digits = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(rng.randint(4, 7))]
    weights = key[-len(digits):]
    total = sum(d * w for d, w in zip(digits, weights)) * 10
    control = total % 11
    control = 0 if control == 10 else control
    return "".join(map(str, digits)) + str(control)


def gen_plate(rng: random.Random, prefix: str) -> str:
    """County-coded auto plate, e.g. 'CJ 12 ABC' (Bucharest 'B' uses 3 digits)."""
    digits = rng.randint(10, 999) if prefix == "B" else rng.randint(10, 99)
    letters = "".join(rng.choice(string.ascii_uppercase) for _ in range(3))
    return f"{prefix} {digits:02d} {letters}"


def gen_phone(rng: random.Random) -> str:
    """Romanian mobile, +40 7xx xxx xxx."""
    return f"+40 7{rng.randint(0, 9)}{rng.randint(0, 9)} {rng.randint(100, 999)} {rng.randint(100, 999)}"


# Romanian ID-card series: 2 uppercase letters (county-linked) + 6 digits, e.g. "RX 123456".
CI_SERIES = ["RX", "RD", "RK", "RR", "RT", "RZ", "KX", "KT", "DP", "DR", "TZ", "ZS", "MX", "CJ", "BV"]


def gen_ci(rng: random.Random) -> str:
    """Romanian identity-card seria + număr (e.g. 'RX 123456')."""
    return f"{rng.choice(CI_SERIES)} {rng.randint(100000, 999999)}"


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic person: CNP county == address county, CNP sex == name sex."""
    code, _plate, county = rng.choice(COUNTIES)
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    return Person(
        first_name=first,
        last_name=rng.choice(SURNAMES),
        sex=sex,
        cnp=gen_cnp(rng, code, sex),
        county=county,
        address=f"{rng.choice(STREETS)} nr. {rng.randint(1, 200)}, {county}",
        postcode=f"{rng.randint(100000, 999999)}",
        phone=gen_phone(rng),
        iban=gen_iban_ro(rng),
    )


def iban_ro_valid(iban: str) -> bool:
    """Validate a Romanian IBAN via mod-97 (for tests / round-trip checks)."""
    if not iban.startswith("RO") or len(iban) != 24:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def cui_valid(cui: str) -> bool:
    """Validate a Romanian CUI control digit."""
    if not cui.isdigit() or not (4 <= len(cui) <= 10):
        return False
    key = [7, 5, 3, 2, 1, 7, 5, 3, 2]
    body, control = cui[:-1], int(cui[-1])
    weights = key[-len(body):]
    total = sum(int(d) * w for d, w in zip(body, weights)) * 10
    rem = total % 11
    return (0 if rem == 10 else rem) == control


# CNP validity re-exported via europriv_bench.national_id.validate_cnp (single source of truth).
__all__ = [
    "Person", "gen_cnp", "gen_iban_ro", "gen_cui", "gen_plate", "gen_phone", "gen_person",
    "iban_ro_valid", "cui_valid", "validate_cnp", "COUNTIES",
]
