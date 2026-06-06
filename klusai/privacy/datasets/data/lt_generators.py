"""Checksum-valid, coherent Lithuanian PII generators (localized synthetic — not MT).

Same P0 contract as the Romanian/Estonian/Danish/Czech generators: identifiers must carry VALID
checksums and realistic structure (else we teach models the wrong invariants). Pure, seeded, no
LLM/network.

Identifiers:
  - **asmens kodas** (personal code) — 11-digit national id ``GYYMMDDNNNC``, the SAME family as the
    Estonian isikukood: the 1st digit G encodes century + sex (1/2 -> 1800s, 3/4 -> 1900s, 5/6 ->
    2000s; odd=M, even=F), digits 2-7 the birth date YYMMDD (century from G -> full year), NNN a
    serial, and the 11th digit C an ISO-7064-style **two-pass mod-11** check digit (RST 1185-91 —
    python-stdnum's lt.asmens reuses ee.ik.calc_check_digit verbatim). DOB and sex are coherent with
    the chosen name. The validator (``europriv_bench.national_id`` country ``LT``) cross-checks every
    generated id (one source of truth).
  - **įmonės kodas** — 9-digit company code with its OWN single-pass weighted mod-11 (a different
    scheme from the personal-code two-pass). Structurally disjoint from an asmens kodas (9 vs 11
    digits) so the leak metric never mis-decodes it.
  - **IBAN (LT)** — 20-char mod-97 IBAN: LT + 2 check + 5-digit bank + 11-digit account.

There is no LLM step; asmens kodas sex/birth-date are coherent with the chosen Lithuanian given name.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass

MALE_NAMES = ["Jonas", "Petras", "Tomas", "Andrius", "Mantas", "Darius", "Marius", "Vytautas"]
FEMALE_NAMES = ["Greta", "Rūta", "Eglė", "Aistė", "Gabija", "Ieva", "Monika", "Laura"]
# Surnames: masculine / feminine forms (the -ienė/-aitė feminine suffixes are real Lithuanian morphology).
SURNAMES_M = ["Kazlauskas", "Petrauskas", "Jankauskas", "Stankevičius", "Vasiliauskas", "Žukauskas",
              "Butkus", "Paulauskas"]
SURNAMES_F = ["Kazlauskienė", "Petrauskienė", "Jankauskienė", "Stankevičienė", "Vasiliauskienė",
              "Žukauskienė", "Butkienė", "Paulauskienė"]
# (city, county/apskritis) pairs — kept coherent so address city matches its county.
CITIES = [
    ("Vilnius", "Vilniaus apskritis"), ("Kaunas", "Kauno apskritis"),
    ("Klaipėda", "Klaipėdos apskritis"), ("Šiauliai", "Šiaulių apskritis"),
    ("Panevėžys", "Panevėžio apskritis"), ("Alytus", "Alytaus apskritis"),
    ("Marijampolė", "Marijampolės apskritis"), ("Mažeikiai", "Telšių apskritis"),
]
STREETS = ["Gedimino prospektas", "Vilniaus gatvė", "Laisvės alėja", "Taikos prospektas",
           "Kęstučio gatvė", "Savanorių prospektas"]

# Shared Baltic two-pass mod-11 weights (same family as the europriv_bench EE/LT validator).
_W1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 1]
_W2 = [3, 4, 5, 6, 7, 8, 9, 1, 2, 3]
_GENDER_CENTURY = {1900: {"M": 3, "F": 4}, 2000: {"M": 5, "F": 6}}

# įmonės kodas (company code) single-pass mod-11 weights (1..9 then 1..2 on the redraw pass).
_IMK_W1 = [1, 2, 3, 4, 5, 6, 7, 8]
_IMK_W2 = [3, 4, 5, 6, 7, 8, 9, 1]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    asmens_kodas: str
    dob: str          # YYYY-MM-DD — DERIVED from the asmens kodas (stays consistent with it)
    city: str
    county: str
    address: str
    postcode: str     # "LT-NNNNN"
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


def gen_asmens_kodas(rng: random.Random, sex: str, birth_year: int | None = None) -> tuple[str, str]:
    """Valid 11-digit asmens kodas for a given sex + its derived ISO DOB.

    Returns ``(asmens_kodas, 'YYYY-MM-DD')``. The 1st digit encodes century+sex; the 11th digit is the
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


def asmens_kodas_valid(value: str) -> bool:
    """True iff an 11-digit asmens kodas is structurally valid (delegates to the one source of truth)."""
    from europriv_bench.national_id import parse_national_id  # one source of truth
    return parse_national_id(value, "LT").valid


def asmens_kodas_sex(value: str) -> str:
    return "M" if int(value[0]) % 2 == 1 else "F"


def gen_imones_kodas(rng: random.Random) -> str:
    """Valid Lithuanian įmonės kodas: 9 digits, single-pass weighted mod-11 (with the standard redraw)."""
    while True:
        body = [rng.randint(0, 9) for _ in range(8)]
        check = sum(d * w for d, w in zip(body, _IMK_W1)) % 11
        if check == 10:
            check = sum(d * w for d, w in zip(body, _IMK_W2)) % 11
            if check == 10:
                check = 0
        return "".join(map(str, body)) + str(check)


def imones_kodas_valid(value: str) -> bool:
    s = value.replace(" ", "")
    if len(s) != 9 or not s.isdigit():
        return False
    body = [int(d) for d in s[:8]]
    check = sum(d * w for d, w in zip(body, _IMK_W1)) % 11
    if check == 10:
        check = sum(d * w for d, w in zip(body, _IMK_W2)) % 11
        if check == 10:
            check = 0
    return check == int(s[8])


def gen_iban_lt(rng: random.Random) -> str:
    """Valid Lithuanian IBAN (mod-97): LT + 2 check + 16-digit BBAN (5 bank + 11 account)."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(16))
    rearranged = bban + "LT00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"LT{check:02d}{bban}"


def iban_lt_valid(iban: str) -> bool:
    if not iban.startswith("LT") or len(iban) != 20:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def gen_phone_lt(rng: random.Random) -> str:
    """Lithuanian mobile, +370 6NN NNNNN (no checksum — documented as such)."""
    return f"+370 6{rng.randint(10, 99)} {rng.randint(10000, 99999)}"


def _ascii(s: str) -> str:
    """ASCII-fold Lithuanian diacritics for realistic emails."""
    table = {"ą": "a", "č": "c", "ę": "e", "ė": "e", "į": "i", "š": "s",
             "ų": "u", "ū": "u", "ž": "z"}
    for k, v in table.items():
        s = s.replace(k, v).replace(k.upper(), v.upper())
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Lithuanian person: asmens kodas sex matches the name, DOB derived from the
    asmens kodas, surname morphology agrees with sex, address city matches its county."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    last = rng.choice(SURNAMES_M if sex == "M" else SURNAMES_F)
    code, dob = gen_asmens_kodas(rng, sex)
    city, county = rng.choice(CITIES)
    return Person(
        first_name=first,
        last_name=last,
        sex=sex,
        asmens_kodas=code,
        dob=dob,  # consistent with the asmens kodas by construction
        city=city,
        county=county,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, LT-{rng.randint(10000, 99999)} {city}",
        postcode=f"LT-{rng.randint(10000, 99999)}",
        phone=gen_phone_lt(rng),
        iban=gen_iban_lt(rng),
    )


__all__ = [
    "Person", "gen_asmens_kodas", "asmens_kodas_valid", "asmens_kodas_sex",
    "gen_imones_kodas", "imones_kodas_valid", "gen_iban_lt", "iban_lt_valid", "gen_phone_lt",
    "gen_person", "CITIES",
]
