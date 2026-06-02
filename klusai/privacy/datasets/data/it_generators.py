"""Checksum-valid, coherent Italian PII generators (localized synthetic — not MT).

Same P0 contract as the RO/PL/EN generators: identifiers must carry VALID checksums / structure
(else we teach models the wrong invariants). Pure, seeded, no LLM/network.

Identifiers:
  - **codice fiscale** — 16-char alphanumeric national id. **Decode-bearing**: a valid CF discloses
    DATE_OF_BIRTH + SEX + PLACE_OF_BIRTH. We build it from a (surname/name consonant code, birth
    date, sex, Belfiore comune code) and append the mod-26 control letter computed by the SAME
    algorithm the benchmark uses. The generator imports the benchmark validator
    (``europriv_bench.national_id``) as the single source of truth, so a generated CF is guaranteed
    to validate AND decode consistently against the leakage metric. The deep omocodia/Belfiore
    *decode* rigor lives in KLU-105; here the generator emits canonical (non-omocode) checksum-valid
    CFs whose decoded sex/DOB are coherent with the chosen person.
  - **partita IVA** — 11-digit VAT number with a Luhn-style (odd/even) mod-10 check digit.
  - **IBAN (IT)** — 27-char mod-97 IBAN: IT + 2 check + 1 CIN letter + 5 ABI + 5 CAB + 12 account.

There is no LLM step; the codice fiscale's sex/birth-date are coherent with the chosen Italian name.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass

from europriv_bench.national_id import (
    _CF_MONTHS,
    _cf_control_letter,
    parse_national_id,
)

MALE_NAMES = ["Giuseppe", "Marco", "Francesco", "Alessandro", "Andrea", "Luca", "Matteo", "Davide"]
FEMALE_NAMES = ["Giulia", "Maria", "Francesca", "Sara", "Chiara", "Anna", "Martina", "Elena"]
SURNAMES = ["Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo", "Greco"]
# (city, region) pairs — kept coherent so address city matches its region. The Belfiore code is the
# comune-of-birth code embedded in the codice fiscale (here the city's own code, kept consistent).
CITIES = [
    ("Roma", "Lazio", "H501"), ("Milano", "Lombardia", "F205"), ("Napoli", "Campania", "F839"),
    ("Torino", "Piemonte", "L219"), ("Palermo", "Sicilia", "G273"), ("Genova", "Liguria", "D969"),
    ("Bologna", "Emilia-Romagna", "A944"), ("Firenze", "Toscana", "D612"),
]
STREETS = ["Via Roma", "Via Garibaldi", "Corso Vittorio Emanuele", "Via Dante", "Via Mazzini"]

# Inverse of europriv_bench's month-letter table (1..12 → letter) for CF construction.
_CF_MONTH_LETTER = {v: k for k, v in _CF_MONTHS.items()}
_VOWELS = "AEIOU"
_PIVA_WEIGHTS_ODD = 1   # odd positions (1-indexed) added as-is
# month-day count (leap-agnostic; CF year is 2-digit so the validator allows Feb 29).
_MONTH_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    codice_fiscale: str
    dob: str          # DD/MM/YY — the 2-digit year that the CF actually encodes
    city: str
    region: str
    address: str
    cap: str          # postal code (CAP), 5 digits
    phone: str
    iban: str


def _consonant_code(name: str, is_surname: bool) -> str:
    """3-char codice-fiscale name code: consonants first, then vowels, padded with X.

    Surname and name use the same consonants-then-vowels rule (the name's >3-consonant special case
    — 1st/3rd/4th — is applied for names). Output is always 3 uppercase letters.
    """
    s = "".join(c for c in name.upper() if c.isalpha())
    consonants = [c for c in s if c not in _VOWELS]
    vowels = [c for c in s if c in _VOWELS]
    if not is_surname and len(consonants) >= 4:
        # Name rule: take 1st, 3rd, 4th consonant.
        picked = [consonants[0], consonants[2], consonants[3]]
    else:
        picked = consonants[:3]
    code = "".join(picked) + "".join(vowels)
    return (code + "XXX")[:3]


def gen_codice_fiscale(
    rng: random.Random,
    surname: str,
    name: str,
    sex: str,
    belfiore: str,
    birth_year_2digit: int | None = None,
) -> str:
    """Build a canonical checksum-valid codice fiscale, decode-coherent with the given person.

    The control letter is computed via ``europriv_bench.national_id._cf_control_letter`` (single
    source of truth), so the result is guaranteed to pass the benchmark validator and decode to the
    same sex / birth month-day / Belfiore place we put in.
    """
    if birth_year_2digit is None:
        birth_year_2digit = rng.randint(40, 99)  # plausible 2-digit year
    month = rng.randint(1, 12)
    day = rng.randint(1, _MONTH_DAYS[month - 1])
    month_letter = _CF_MONTH_LETTER[month]
    day_field = day + 40 if sex == "F" else day
    first15 = (
        _consonant_code(surname, is_surname=True)
        + _consonant_code(name, is_surname=False)
        + f"{birth_year_2digit:02d}"
        + month_letter
        + f"{day_field:02d}"
        + belfiore
    )
    return first15 + _cf_control_letter(first15)


def codice_fiscale_valid(cf: str) -> bool:
    """True iff ``cf`` validates against the benchmark's codice-fiscale validator (source of truth)."""
    return parse_national_id(cf, "IT").valid


_PIVA_EVEN_DOUBLE = {0: 0, 1: 2, 2: 4, 3: 6, 4: 8, 5: 1, 6: 3, 7: 5, 8: 7, 9: 9}


def gen_partita_iva(rng: random.Random) -> str:
    """Valid partita IVA: 11 digits with a Luhn-style mod-10 check digit.

    Odd-position (1-indexed) digits are summed as-is; even-position digits are doubled with a
    carry-fold table; the check digit makes the total a multiple of 10.
    """
    body = [rng.randint(0, 9) for _ in range(10)]
    total = 0
    for i, d in enumerate(body):
        if i % 2 == 0:            # 1-indexed odd position
            total += d
        else:                     # 1-indexed even position → doubled & folded
            total += _PIVA_EVEN_DOUBLE[d]
    check = (10 - total % 10) % 10
    return "".join(map(str, body)) + str(check)


def partita_iva_valid(piva: str) -> bool:
    if not piva.isdigit() or len(piva) != 11:
        return False
    total = 0
    for i, ch in enumerate(piva[:10]):
        d = int(ch)
        total += d if i % 2 == 0 else _PIVA_EVEN_DOUBLE[d]
    return (10 - total % 10) % 10 == int(piva[10])


def gen_iban_it(rng: random.Random) -> str:
    """Valid Italian IBAN (mod-97): IT + 2 check + 1 CIN letter + 5 ABI + 5 CAB + 12 account."""
    cin = rng.choice(string.ascii_uppercase)
    bban = cin + "".join(str(rng.randint(0, 9)) for _ in range(22))
    rearranged = bban + "IT00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"IT{check:02d}{bban}"


def iban_it_valid(iban: str) -> bool:
    if not iban.startswith("IT") or len(iban) != 27:
        return False
    rearranged = iban[4:] + iban[:4]
    try:
        return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1
    except ValueError:
        return False


def gen_phone_it(rng: random.Random) -> str:
    """Italian mobile, +39 3NN NNNNNNN (no checksum — documented as such)."""
    return f"+39 3{rng.randint(10, 99)} {rng.randint(1000000, 9999999)}"


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Italian person: CF sex/DOB match the chosen name, Belfiore matches the
    birth city, address city matches its region."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    last = rng.choice(SURNAMES)
    city, region, belfiore = rng.choice(CITIES)
    cf = gen_codice_fiscale(rng, last, first, sex, belfiore)
    info = parse_national_id(cf, "IT")  # decode the CF we just built → keep DOB consistent with it
    dob = f"{info.extra['birth_day']:02d}/{info.extra['birth_month']:02d}/{info.extra['birth_year_2digit']}"
    cap = f"{rng.randint(10, 98):02d}{rng.randint(100, 199)}"
    return Person(
        first_name=first,
        last_name=last,
        sex=sex,
        codice_fiscale=cf,
        dob=dob,
        city=city,
        region=region,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {cap} {city}",
        cap=cap,
        phone=gen_phone_it(rng),
        iban=gen_iban_it(rng),
    )


__all__ = [
    "Person", "gen_codice_fiscale", "codice_fiscale_valid",
    "gen_partita_iva", "partita_iva_valid", "gen_iban_it", "iban_it_valid",
    "gen_phone_it", "gen_person", "CITIES",
]
