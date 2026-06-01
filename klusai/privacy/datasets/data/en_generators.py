"""Checksum-valid (where a checksum exists), coherent English/UK PII generators.

Same P0 contract as RO/PL: identifiers must be structurally correct, and where the id type defines a
checksum the generated value MUST pass it. English-locale identifiers are a mix:

  - **IBAN (GB)** — mod-97 checked (the genuine checksum here).
  - **payment card number** — 16-digit Luhn-valid (ACCOUNT_ID).
  - **NINO** (UK National Insurance number) — format-valid only (prefix rules + 6 digits + suffix
    A–D); the scheme defines NO arithmetic checksum, so we generate a valid *format* and do NOT fake
    a checksum self-test for it.
  - **SSN** (US) — format-valid only (area/group/serial ranges, no '000'/'666'/9xx area); again NO
    checksum exists, so it is documented under ``no_checksum_ids``, not the self-test.
  - **phone** — UK mobile +44 7xxx xxxxxx (no checksum).

Coherence: a person's name sex is independent of these ids (English ids do not encode sex/DOB), but
city/region pairs are kept consistent.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass

MALE_NAMES = ["James", "Oliver", "William", "Harry", "George", "Jack", "Thomas", "Charlie"]
FEMALE_NAMES = ["Olivia", "Emily", "Sophie", "Charlotte", "Emma", "Grace", "Amelia", "Jessica"]
SURNAMES = ["Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Johnson", "Davies"]
# (city, region) — kept coherent so address city matches its region.
CITIES = [
    ("London", "Greater London"), ("Manchester", "Greater Manchester"), ("Birmingham", "West Midlands"),
    ("Leeds", "West Yorkshire"), ("Bristol", "South West"), ("Edinburgh", "Scotland"),
    ("Cardiff", "Wales"), ("Liverpool", "Merseyside"),
]
STREETS = ["High Street", "Station Road", "Church Lane", "Victoria Road", "Kings Road"]

# NINO prefixes that are administratively valid (exclude D, F, I, Q, U, V as first/second letter and
# the special-use prefixes BG, GB, NK, KN, TN, NT, ZZ).
_NINO_LETTERS = "ABCEGHJKLMNOPRSTWXYZ"
_NINO_INVALID_PREFIX = {"BG", "GB", "NK", "KN", "TN", "NT", "ZZ"}


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    nino: str
    ssn: str
    city: str
    region: str
    address: str
    postcode: str
    phone: str
    iban: str
    card: str


def _luhn_check_digit(body: str) -> int:
    """Luhn control digit for the given numeric body (card-style)."""
    digits = [int(c) for c in body]
    # Double every second digit from the right of the FINAL number; body has no check digit yet, so
    # the check digit is at an even position from the right → double digits at odd indices from right of body.
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:  # positions that get doubled once the check digit is appended
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10


def luhn_valid(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 2:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def gen_card(rng: random.Random) -> str:
    """16-digit Luhn-valid payment card number, grouped 'NNNN NNNN NNNN NNNN'."""
    body = "".join(str(rng.randint(0, 9)) for _ in range(15))
    full = body + str(_luhn_check_digit(body))
    return f"{full[0:4]} {full[4:8]} {full[8:12]} {full[12:16]}"


def card_valid(card: str) -> bool:
    return luhn_valid(card.replace(" ", ""))


def gen_iban_gb(rng: random.Random) -> str:
    """Valid UK IBAN (mod-97): GB + 2 check + 4-letter bank + 6-digit sort + 8-digit account."""
    bank = "".join(rng.choice(string.ascii_uppercase) for _ in range(4))
    bban = bank + "".join(str(rng.randint(0, 9)) for _ in range(14))
    rearranged = bban + "GB00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"GB{check:02d}{bban}"


def iban_gb_valid(iban: str) -> bool:
    if not iban.startswith("GB") or len(iban) != 22:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def gen_nino(rng: random.Random) -> str:
    """UK National Insurance number: 2 prefix letters + 6 digits + suffix A–D. Format-valid only."""
    while True:
        prefix = rng.choice(_NINO_LETTERS) + rng.choice(_NINO_LETTERS)
        if prefix not in _NINO_INVALID_PREFIX:
            break
    digits = "".join(str(rng.randint(0, 9)) for _ in range(6))
    suffix = rng.choice("ABCD")
    return f"{prefix} {digits[0:2]} {digits[2:4]} {digits[4:6]} {suffix}"


def nino_format_valid(nino: str) -> bool:
    compact = nino.replace(" ", "")
    if len(compact) != 9:
        return False
    prefix, body, suffix = compact[:2], compact[2:8], compact[8]
    return (
        prefix[0] in _NINO_LETTERS and prefix[1] in _NINO_LETTERS
        and prefix not in _NINO_INVALID_PREFIX
        and body.isdigit() and suffix in "ABCD"
    )


def gen_ssn(rng: random.Random) -> str:
    """US Social Security Number, format-valid only (no '000'/'666'/9xx area, no '00' group, no '0000' serial)."""
    while True:
        area = rng.randint(1, 899)
        if area != 666:
            break
    group = rng.randint(1, 99)
    serial = rng.randint(1, 9999)
    return f"{area:03d}-{group:02d}-{serial:04d}"


def ssn_format_valid(ssn: str) -> bool:
    parts = ssn.split("-")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return False
    area, group, serial = (int(p) for p in parts)
    return 1 <= area <= 899 and area != 666 and 1 <= group <= 99 and 1 <= serial <= 9999


def gen_phone_gb(rng: random.Random) -> str:
    """UK mobile, +44 7xxx xxxxxx (no checksum)."""
    return f"+44 7{rng.randint(100, 999)} {rng.randint(100000, 999999)}"


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic English/UK person (city matches region; ids are independent format-valid)."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    city, region = rng.choice(CITIES)
    postcode = f"{rng.choice(['EC', 'SW', 'M', 'B', 'LS', 'BS', 'EH', 'CF', 'L'])}{rng.randint(1, 9)} {rng.randint(1, 9)}{rng.choice(string.ascii_uppercase)}{rng.choice(string.ascii_uppercase)}"
    return Person(
        first_name=first,
        last_name=rng.choice(SURNAMES),
        sex=sex,
        nino=gen_nino(rng),
        ssn=gen_ssn(rng),
        city=city,
        region=region,
        address=f"{rng.randint(1, 200)} {rng.choice(STREETS)}, {city} {postcode}",
        postcode=postcode,
        phone=gen_phone_gb(rng),
        iban=gen_iban_gb(rng),
        card=gen_card(rng),
    )


__all__ = [
    "Person", "luhn_valid", "gen_card", "card_valid", "gen_iban_gb", "iban_gb_valid",
    "gen_nino", "nino_format_valid", "gen_ssn", "ssn_format_valid", "gen_phone_gb", "gen_person",
    "CITIES",
]
