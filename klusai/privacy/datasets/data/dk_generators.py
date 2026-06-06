"""Checksum/format-valid, coherent Danish PII generators (localized synthetic — not MT).

Same P0 contract as the Romanian/Polish/Swedish/Czech generators: identifiers must carry VALID
structure (else we teach models the wrong invariants). Pure, seeded, no LLM/network.

Identifiers:
  - **CPR-nummer** — 10-digit national id ``DDMMYY-SSSS``. Digits 1-6 encode the birth date; the
    7th digit (first of the SSSS sequence) encodes the century together with the 2-digit year (the
    CPR-kontoret / Det Centrale Personregister table); the LAST digit encodes sex (odd=M, even=F).
    The historical **mod-11 check was abolished in 2007** (the day's sequence numbers ran out), so a
    valid CPR is **format + century-table + plausible date** — NOT a checksum. We therefore generate
    a 7th digit consistent with the chosen century and a last digit matching the chosen sex; we do
    NOT force mod-11 divisibility (that would emit only pre-2007-style numbers and teach a checksum
    invariant that no longer holds). The validator (``europriv_bench.national_id`` country=``DK``)
    cross-checks every generated id (one source of truth). DOB and sex are coherent with the name.
  - **CVR-nummer** — 8-digit company id with a weighted mod-11 control digit (weights 2,7,6,5,4,3,2).
    Structurally disjoint from a CPR (8 vs 10 digits) so the leak metric never mis-decodes it.
  - **IBAN (DK)** — 18-char mod-97 IBAN: DK + 2 check + 4-digit bank + 10-digit account.

There is no LLM step; CPR sex/birth-date are coherent with the chosen Danish given name.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass

MALE_NAMES = ["Lars", "Peter", "Niels", "Jens", "Henrik", "Søren", "Mads", "Anders"]
FEMALE_NAMES = ["Anne", "Mette", "Hanne", "Kirsten", "Lene", "Karen", "Marie", "Camilla"]
SURNAMES = ["Jensen", "Nielsen", "Hansen", "Pedersen", "Andersen", "Christensen", "Larsen", "Sørensen"]
# (city, region) pairs — kept coherent so address city matches its region.
CITIES = [
    ("København", "Region Hovedstaden"), ("Aarhus", "Region Midtjylland"),
    ("Odense", "Region Syddanmark"), ("Aalborg", "Region Nordjylland"),
    ("Esbjerg", "Region Syddanmark"), ("Randers", "Region Midtjylland"),
    ("Roskilde", "Region Sjælland"), ("Vejle", "Region Syddanmark"),
]
STREETS = ["Hovedgaden", "Kirkevej", "Skolegade", "Nørregade", "Søndergade", "Bredgade"]

_CVR_WEIGHTS = [2, 7, 6, 5, 4, 3, 2]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    cpr: str
    dob: str          # YYYY-MM-DD — DERIVED from the CPR (stays consistent with it)
    city: str
    region: str
    address: str
    postcode: str     # NNNN
    phone: str
    iban: str


def _seventh_digit_for(rng: random.Random, birth_year: int, yy: int) -> int:
    """Pick a 7th digit (first of SSSS) whose CPR-kontoret century band contains ``birth_year``.

    Inverse of the validator's century table:
      1800s → digit 5-8 (requires yy >= 58);  1900s → 0-3 always, or 4/9 when yy >= 37;
      2000s → 4/9 when yy < 37, or 5-8 when yy < 58.
    """
    century = (birth_year // 100) * 100
    if century == 1900:
        choices = [0, 1, 2, 3] + ([4, 9] if yy >= 37 else [])
    elif century == 1800:
        choices = [5, 6, 7, 8]  # only valid when yy >= 58 (enforced by birth-year range)
    else:  # 2000s
        choices = ([4, 9] if yy < 37 else []) + ([5, 6, 7, 8] if yy < 58 else [])
    return rng.choice(choices)


def gen_cpr(rng: random.Random, sex: str, birth_year: int | None = None) -> tuple[str, str]:
    """Valid 10-digit CPR-nummer for a given sex + its derived ISO DOB.

    Returns ``(cpr, 'YYYY-MM-DD')``. The 7th digit is chosen so the CPR-kontoret century table
    recovers the chosen birth year; the last digit parity encodes sex. We emit the printed
    ``DDMMYY-SSSS`` form (hyphen). No mod-11 is applied — that check was abolished in 2007.
    """
    if birth_year is None:
        birth_year = rng.randint(1940, 2010)  # falls in 1900s/2000s bands (yy mapping is unambiguous)
    yy = birth_year % 100
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)  # <=28 -> valid in every month
    c7 = _seventh_digit_for(rng, birth_year, yy)
    mid = rng.randint(0, 9)   # 8th digit (free)
    nine = rng.randint(0, 9)  # 9th digit (free)
    last = rng.randint(0, 9)
    if sex == "M" and last % 2 == 0:
        last = (last + 1) % 10
    elif sex == "F" and last % 2 == 1:
        last = (last + 1) % 10
    cpr = f"{day:02d}{month:02d}{yy:02d}{c7}{mid}{nine}{last}"
    return f"{cpr[:6]}-{cpr[6:]}", f"{birth_year:04d}-{month:02d}-{day:02d}"


def cpr_valid(value: str) -> bool:
    """True iff a 10-digit CPR (hyphen optional) is format + century-table + date valid (no mod-11)."""
    from europriv_bench.national_id import parse_national_id  # one source of truth
    return parse_national_id(value, "DK").valid


def cpr_sex(value: str) -> str:
    s = value.replace("-", "").replace(" ", "")
    return "M" if int(s[9]) % 2 == 1 else "F"


def gen_cvr(rng: random.Random) -> str:
    """Valid Danish CVR-nummer: 8 digits, weighted mod-11 control digit (weights 2,7,6,5,4,3,2)."""
    while True:
        body = [rng.randint(0, 9) for _ in range(7)]
        total = sum(d * w for d, w in zip(body, _CVR_WEIGHTS))
        check = 11 - total % 11
        if check == 11:
            check = 0
        if check != 10:  # remainder forcing check digit 10 is not assignable — redraw
            return "".join(map(str, body)) + str(check)


def cvr_valid(value: str) -> bool:
    s = value.replace(" ", "")
    if len(s) != 8 or not s.isdigit():
        return False
    total = sum(int(d) * w for d, w in zip(s[:7], _CVR_WEIGHTS))
    check = 11 - total % 11
    check = 0 if check == 11 else check
    return check != 10 and check == int(s[7])


def gen_iban_dk(rng: random.Random) -> str:
    """Valid Danish IBAN (mod-97): DK + 2 check + 14-digit BBAN (4 bank + 10 account)."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(14))
    rearranged = bban + "DK00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"DK{check:02d}{bban}"


def iban_dk_valid(iban: str) -> bool:
    if not iban.startswith("DK") or len(iban) != 18:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def gen_phone_dk(rng: random.Random) -> str:
    """Danish phone, +45 NN NN NN NN (no checksum — documented as such)."""
    return f"+45 {rng.randint(20, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)}"


def _ascii(s: str) -> str:
    """ASCII-fold Danish diacritics (æ/ø/å) for realistic emails."""
    s = s.replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
    s = s.replace("Æ", "Ae").replace("Ø", "Oe").replace("Å", "Aa")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Danish person: CPR sex matches the name, DOB derived from the CPR,
    address city matches its region."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    last = rng.choice(SURNAMES)
    cpr, dob = gen_cpr(rng, sex)
    city, region = rng.choice(CITIES)
    return Person(
        first_name=first,
        last_name=last,
        sex=sex,
        cpr=cpr,
        dob=dob,  # consistent with the CPR by construction
        city=city,
        region=region,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {rng.randint(1000, 9999)} {city}",
        postcode=f"{rng.randint(1000, 9999)}",
        phone=gen_phone_dk(rng),
        iban=gen_iban_dk(rng),
    )


__all__ = [
    "Person", "gen_cpr", "cpr_valid", "cpr_sex",
    "gen_cvr", "cvr_valid", "gen_iban_dk", "iban_dk_valid", "gen_phone_dk",
    "gen_person", "CITIES",
]
