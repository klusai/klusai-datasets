"""Checksum-valid, coherent Swedish PII generators (localized synthetic — not MT).

Same P0 contract as the Romanian/Polish generators: identifiers must carry VALID checksums and
realistic structure (else we teach models the wrong invariants). Pure, seeded, no LLM/network.

Identifiers:
  - **personnummer** — 10-digit national id ``YYMMDD-NNNC``. Digits 1-6 encode the birth date,
    the 9th digit (last of the NNN birth-number) encodes sex (odd=M, even=F), and the 10th is a
    **Luhn (mod-10)** check digit over the first 9 digits. The separator is ``-`` (``+`` once the
    holder turns 100); we emit the ``-`` form. DOB and sex are coherent with the chosen name.
  - **organisationsnummer** — 10-digit company id, same Luhn check digit; the first digit is the
    legal-form group. Emitted as ``NNNNNN-NNNN``.
  - **IBAN (SE)** — 24-char mod-97 IBAN: SE + 2 check + 3-digit bank + 17-digit account.

There is no LLM step; personnummer sex/birth-date are coherent with the chosen Swedish given name.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass

MALE_NAMES = ["Erik", "Lars", "Karl", "Anders", "Johan", "Per", "Nils", "Gustav"]
FEMALE_NAMES = ["Anna", "Maria", "Margareta", "Elisabeth", "Eva", "Kristina", "Birgitta", "Karin"]
SURNAMES = ["Andersson", "Johansson", "Karlsson", "Nilsson", "Eriksson", "Larsson", "Olsson", "Persson"]
# (city, county/län) pairs — kept coherent so address city matches its region.
CITIES = [
    ("Stockholm", "Stockholms län"), ("Göteborg", "Västra Götalands län"),
    ("Malmö", "Skåne län"), ("Uppsala", "Uppsala län"), ("Västerås", "Västmanlands län"),
    ("Örebro", "Örebro län"), ("Linköping", "Östergötlands län"), ("Lund", "Skåne län"),
]
STREETS = ["Storgatan", "Kungsgatan", "Drottninggatan", "Vasagatan", "Sveavägen", "Nygatan"]

_SE_LUHN_WEIGHTS = [2, 1, 2, 1, 2, 1, 2, 1, 2]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    personnummer: str
    dob: str          # YYYY-MM-DD — DERIVED from the personnummer (stays consistent with it)
    city: str
    county: str
    address: str
    postcode: str     # NNN NN
    phone: str
    iban: str


def _luhn_check_digit(first9: str) -> int:
    """Luhn (mod-10) check digit over a 9-digit body (weights 2,1,2,...)."""
    total = 0
    for d, w in zip(first9, _SE_LUHN_WEIGHTS):
        prod = int(d) * w
        total += prod - 9 if prod > 9 else prod
    return (10 - total % 10) % 10


def gen_personnummer(rng: random.Random, sex: str, birth_year: int | None = None) -> tuple[str, str]:
    """Valid 10-digit personnummer for a given sex + its derived ISO DOB.

    Returns ``(personnummer, 'YYYY-MM-DD')``. The 9th digit (last of NNN) parity encodes sex; the
    10th digit is the Luhn check. We emit the printed ``YYMMDD-NNNC`` form (hyphen separator).
    """
    if birth_year is None:
        birth_year = rng.randint(1940, 2010)
    yy = birth_year % 100
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)  # <=28 -> valid in every month
    serial2 = rng.randint(0, 99)
    sex_digit = rng.randint(0, 9)
    if sex == "M" and sex_digit % 2 == 0:
        sex_digit = (sex_digit + 1) % 10
    elif sex == "F" and sex_digit % 2 == 1:
        sex_digit = (sex_digit + 1) % 10
    body9 = f"{yy:02d}{month:02d}{day:02d}{serial2:02d}{sex_digit}"
    pn = body9 + str(_luhn_check_digit(body9))
    return f"{pn[:6]}-{pn[6:]}", f"{birth_year:04d}-{month:02d}-{day:02d}"


def personnummer_valid(value: str) -> bool:
    """True iff a 10-digit personnummer (hyphen optional) has a valid Luhn check digit."""
    s = value.replace("-", "").replace("+", "").replace(" ", "")
    if len(s) != 10 or not s.isdigit():
        return False
    return _luhn_check_digit(s[:9]) == int(s[9])


def personnummer_sex(value: str) -> str:
    s = value.replace("-", "").replace("+", "").replace(" ", "")
    return "M" if int(s[8]) % 2 == 1 else "F"


def gen_orgnr(rng: random.Random) -> str:
    """Valid Swedish organisationsnummer: 10 digits, Luhn check digit, printed ``NNNNNN-NNNN``.

    By law the THIRD digit of an organisationsnummer is >= 2 (the field where a personnummer carries
    the birth month 01-12). We honour that rule, which also keeps orgnr structurally disjoint from a
    valid personnummer so the leak metric never mis-decodes a company id as a re-id subject.
    """
    d3 = rng.randint(2, 9)
    body9 = (str(rng.randint(0, 9)) + str(rng.randint(0, 9)) + str(d3)
             + "".join(str(rng.randint(0, 9)) for _ in range(6)))
    org = body9 + str(_luhn_check_digit(body9))
    return f"{org[:6]}-{org[6:]}"


def orgnr_valid(value: str) -> bool:
    s = value.replace("-", "").replace(" ", "")
    if len(s) != 10 or not s.isdigit():
        return False
    return _luhn_check_digit(s[:9]) == int(s[9])


def gen_iban_se(rng: random.Random) -> str:
    """Valid Swedish IBAN (mod-97): SE + 2 check + 20-digit BBAN (3 bank + 17 account)."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(20))
    rearranged = bban + "SE00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"SE{check:02d}{bban}"


def iban_se_valid(iban: str) -> bool:
    if not iban.startswith("SE") or len(iban) != 24:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def gen_phone_se(rng: random.Random) -> str:
    """Swedish mobile, +46 7N-NNN NN NN (no checksum — documented as such)."""
    return f"+46 7{rng.randint(0, 9)}-{rng.randint(100, 999)} {rng.randint(10, 99)} {rng.randint(10, 99)}"


def _ascii(s: str) -> str:
    """ASCII-fold Swedish diacritics (å/ä/ö) for realistic emails."""
    s = s.replace("å", "a").replace("ä", "a").replace("ö", "o")
    s = s.replace("Å", "A").replace("Ä", "A").replace("Ö", "O")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Swedish person: personnummer sex matches the name, DOB derived from
    the personnummer, address city matches its county."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    last = rng.choice(SURNAMES)
    pn, dob = gen_personnummer(rng, sex)
    city, county = rng.choice(CITIES)
    return Person(
        first_name=first,
        last_name=last,
        sex=sex,
        personnummer=pn,
        dob=dob,  # consistent with the personnummer by construction
        city=city,
        county=county,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {rng.randint(100, 999)} {rng.randint(10, 99)} {city}",
        postcode=f"{rng.randint(100, 999)} {rng.randint(10, 99)}",
        phone=gen_phone_se(rng),
        iban=gen_iban_se(rng),
    )


__all__ = [
    "Person", "gen_personnummer", "personnummer_valid", "personnummer_sex",
    "gen_orgnr", "orgnr_valid", "gen_iban_se", "iban_se_valid", "gen_phone_se",
    "gen_person", "CITIES",
]
