"""Checksum-valid, coherent Estonian PII generators (localized synthetic — not MT).

Same P0 contract as the Romanian/Polish/Danish/Czech generators: identifiers must carry VALID
checksums and realistic structure (else we teach models the wrong invariants). Pure, seeded, no
LLM/network.

Identifiers:
  - **isikukood** (personal identification code) — 11-digit national id ``GYYMMDDNNNC``. The 1st
    digit G encodes century + sex (1/2 -> 1800s, 3/4 -> 1900s, 5/6 -> 2000s, 7/8 -> 2100s; odd=M,
    even=F), digits 2-7 the birth date YYMMDD (the century from G makes the full year unambiguous),
    NNN a serial, and the 11th digit C an ISO-7064-style **two-pass mod-11** check digit. DOB and
    sex are coherent with the chosen name. The validator (``europriv_bench.national_id`` country
    ``EE``) cross-checks every generated id (one source of truth).
  - **registrikood** — 8-digit company/registry code using the SAME two-pass mod-11 over its first
    7 digits (the EE registry reuses the isikukood algorithm). Commercial companies start with 1.
    Structurally disjoint from an isikukood (8 vs 11 digits) so the leak metric never mis-decodes it.
  - **IBAN (EE)** — 20-char mod-97 IBAN: EE + 2 check + 2-digit bank + 14-digit account.

There is no LLM step; isikukood sex/birth-date are coherent with the chosen Estonian given name.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass

MALE_NAMES = ["Jaan", "Mart", "Andres", "Toomas", "Kristjan", "Rein", "Margus", "Tarmo"]
FEMALE_NAMES = ["Mari", "Kadri", "Liis", "Anu", "Kristiina", "Tiina", "Piret", "Maarja"]
SURNAMES = ["Tamm", "Saar", "Sepp", "Mägi", "Kask", "Kukk", "Rebane", "Ilves"]
# (city, county/maakond) pairs — kept coherent so address city matches its county.
CITIES = [
    ("Tallinn", "Harju maakond"), ("Tartu", "Tartu maakond"),
    ("Narva", "Ida-Viru maakond"), ("Pärnu", "Pärnu maakond"),
    ("Kohtla-Järve", "Ida-Viru maakond"), ("Viljandi", "Viljandi maakond"),
    ("Rakvere", "Lääne-Viru maakond"), ("Kuressaare", "Saare maakond"),
]
STREETS = ["Pärnu maantee", "Tartu maantee", "Narva maantee", "Kesk tänav", "Jaama tänav", "Kooli tänav"]

# Shared Baltic two-pass mod-11 weights (same family as the europriv_bench EE/LT validator).
_W1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 1]
_W2 = [3, 4, 5, 6, 7, 8, 9, 1, 2, 3]
# G (1st digit) -> century base. Mirror of the validator's table (we emit 1900s/2000s).
_GENDER_CENTURY = {1900: {"M": 3, "F": 4}, 2000: {"M": 5, "F": 6}}


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    isikukood: str
    dob: str          # YYYY-MM-DD — DERIVED from the isikukood (stays consistent with it)
    city: str
    county: str
    address: str
    postcode: str     # NNNNN
    phone: str
    iban: str


def _two_pass_check(body: str) -> int:
    """Two-pass ISO-7064-style mod-11 check digit over ``body`` (weights 1..9,1 then 3..9,1,2,3)."""
    check = sum(int(d) * w for d, w in zip(body, _W1)) % 11
    if check == 10:
        check = sum(int(d) * w for d, w in zip(body, _W2)) % 11
        if check == 10:
            check = 0
    return check


def gen_isikukood(rng: random.Random, sex: str, birth_year: int | None = None) -> tuple[str, str]:
    """Valid 11-digit isikukood for a given sex + its derived ISO DOB.

    Returns ``(isikukood, 'YYYY-MM-DD')``. The 1st digit encodes century+sex; the 11th digit is the
    two-pass mod-11 check digit over the first 10. DOB is fully recoverable (century from G).
    """
    if birth_year is None:
        birth_year = rng.randint(1940, 2010)
    century = (birth_year // 100) * 100
    g = _GENDER_CENTURY[century][sex]
    yy = birth_year % 100
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    serial = rng.randint(0, 999)
    body = f"{g}{yy:02d}{month:02d}{day:02d}{serial:03d}"
    code = body + str(_two_pass_check(body))
    return code, f"{birth_year:04d}-{month:02d}-{day:02d}"


def isikukood_valid(value: str) -> bool:
    """True iff an 11-digit isikukood is structurally valid (delegates to the one source of truth)."""
    from europriv_bench.national_id import parse_national_id  # one source of truth
    return parse_national_id(value, "EE").valid


def isikukood_sex(value: str) -> str:
    return "M" if int(value[0]) % 2 == 1 else "F"


def gen_registrikood(rng: random.Random) -> str:
    """Valid Estonian registrikood: 8 digits (commercial code starts with 1), two-pass mod-11."""
    body = "1" + "".join(str(rng.randint(0, 9)) for _ in range(6))
    return body + str(_two_pass_check(body))


def registrikood_valid(value: str) -> bool:
    s = value.replace(" ", "")
    if len(s) != 8 or not s.isdigit():
        return False
    return _two_pass_check(s[:7]) == int(s[7])


def gen_iban_ee(rng: random.Random) -> str:
    """Valid Estonian IBAN (mod-97): EE + 2 check + 16-digit BBAN (2 bank + 14 account)."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(16))
    rearranged = bban + "EE00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"EE{check:02d}{bban}"


def iban_ee_valid(iban: str) -> bool:
    if not iban.startswith("EE") or len(iban) != 20:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def gen_phone_ee(rng: random.Random) -> str:
    """Estonian mobile, +372 NNNN NNNN (no checksum — documented as such)."""
    return f"+372 5{rng.randint(100, 999)} {rng.randint(1000, 9999)}"


def _ascii(s: str) -> str:
    """ASCII-fold Estonian diacritics (õ/ä/ö/ü) for realistic emails."""
    s = s.replace("õ", "o").replace("ä", "a").replace("ö", "o").replace("ü", "u")
    s = s.replace("Õ", "O").replace("Ä", "A").replace("Ö", "O").replace("Ü", "U")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Estonian person: isikukood sex matches the name, DOB derived from the
    isikukood, address city matches its county."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    last = rng.choice(SURNAMES)
    code, dob = gen_isikukood(rng, sex)
    city, county = rng.choice(CITIES)
    return Person(
        first_name=first,
        last_name=last,
        sex=sex,
        isikukood=code,
        dob=dob,  # consistent with the isikukood by construction
        city=city,
        county=county,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {rng.randint(10000, 99999)} {city}",
        postcode=f"{rng.randint(10000, 99999)}",
        phone=gen_phone_ee(rng),
        iban=gen_iban_ee(rng),
    )


__all__ = [
    "Person", "gen_isikukood", "isikukood_valid", "isikukood_sex",
    "gen_registrikood", "registrikood_valid", "gen_iban_ee", "iban_ee_valid", "gen_phone_ee",
    "gen_person", "CITIES",
]
