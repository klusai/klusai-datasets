"""Checksum-valid, coherent Slovenian PII generators (localized synthetic — not MT).

Same P0 contract as the Romanian/Estonian/Czech generators: identifiers must carry VALID checksums
and realistic structure (else we teach models the wrong invariants). Pure, seeded, no LLM/network.

Identifiers:
  - **EMŠO** (Enotna matična številka občana) — 13-digit ex-YU JMBG ``DDMMYYY RR BBB K``. Digits 1-7
    are the birth date with YYY = last THREE year digits (ex-YU century convention: YYY>800 -> 1900s,
    else 2000s -> full year recoverable); RR is the political REGION of birth (50 = Slovenia, the only
    code used pre-2024); BBB is a serial that encodes SEX (000-499 male / 500-999 female); K is a
    weighted mod-11 check digit over the 12-digit body (weights 7,6,5,4,3,2 twice; control = 11 −
    (Σ mod 11), with 10/11 → 0). The validator (``europriv_bench.national_id`` country ``SI``)
    cross-checks every generated id (one source of truth). EMŠO is a RICHER decode-bearing surface
    than the Baltic family — it also discloses REGION OF BIRTH, like the IT codice fiscale's place.
  - **davčna številka** (tax number) — 8-digit id: 7 random digits + a weighted mod-11 control digit
    (weights 8,7,6,5,4,3,2). Structurally disjoint from an EMŠO (8 vs 13 digits) so the leak metric
    never mis-decodes it.
  - **IBAN (SI)** — 19-char mod-97 IBAN: SI + 2 check + 5-digit bank/branch + 8-digit account + 2
    national check digits (we just fill the 15-digit BBAN and compute the IBAN mod-97).

There is no LLM step; EMŠO sex/birth-date/region are coherent with the chosen Slovenian given name.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass

MALE_NAMES = ["Luka", "Marko", "Janez", "Matej", "Nejc", "Žiga", "Andrej", "Aleš"]
FEMALE_NAMES = ["Ana", "Maja", "Nina", "Eva", "Sara", "Mojca", "Petra", "Špela"]
# Surnames: shared (Slovenian surnames are not gender-inflected like Czech -ová).
SURNAMES = ["Novak", "Horvat", "Kovačič", "Krajnc", "Zupančič", "Potočnik", "Kovač", "Mlakar"]
# (city, statistical region/statistična regija) pairs — kept coherent so address city matches region.
CITIES = [
    ("Ljubljana", "Osrednjeslovenska regija"), ("Maribor", "Podravska regija"),
    ("Celje", "Savinjska regija"), ("Kranj", "Gorenjska regija"),
    ("Koper", "Obalno-kraška regija"), ("Novo mesto", "Jugovzhodna Slovenija"),
    ("Velenje", "Savinjska regija"), ("Nova Gorica", "Goriška regija"),
]
STREETS = ["Slovenska cesta", "Trubarjeva cesta", "Dunajska cesta", "Celovška cesta",
           "Tržaška cesta", "Prešernova cesta"]

# EMŠO RR region of birth: 50 = Slovenia (the only Slovenian code used until 2024).
_REGION_SI = "50"
# davčna številka (tax number) weighted mod-11 control-digit weights.
_TAX_WEIGHTS = [8, 7, 6, 5, 4, 3, 2]
# EMŠO mod-11 weights (7,6,5,4,3,2 repeated twice) — mirror of the europriv_bench SI validator.
_EMSO_WEIGHTS = [7, 6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    emso: str
    dob: str          # YYYY-MM-DD — DERIVED from the EMŠO (stays consistent with it)
    region: str       # statistical region (coherent with the address city)
    city: str
    address: str
    postcode: str     # SI-NNNN
    phone: str
    iban: str
    tax_number: str


def _emso_check_digit(body12: str) -> int:
    """EMŠO/JMBG mod-11 check digit for the 12-digit body (m = 11 − Σw·d mod 11; 10/11 → 0)."""
    m = 11 - (sum(int(d) * w for d, w in zip(body12, _EMSO_WEIGHTS)) % 11)
    return 0 if m >= 10 else m


def gen_emso(rng: random.Random, sex: str, birth_year: int | None = None) -> tuple[str, str]:
    """Valid 13-digit EMŠO for a given sex + its derived ISO DOB.

    Returns ``(emso, 'YYYY-MM-DD')``. RR is fixed to 50 (Slovenia); the serial BBB encodes sex
    (000-499 male / 500-999 female); the 13th digit is the mod-11 check over the 12-digit body.
    DOB is fully recoverable (the ex-YU century convention makes YYY unambiguous for 1940-2010).
    """
    if birth_year is None:
        birth_year = rng.randint(1940, 2010)
    yyy = birth_year % 1000               # last THREE year digits
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    # Serial encodes sex; avoid the all-zero serial when male so the example stays realistic (000 is
    # valid but rarely emitted). Female 500-999, male 1-499.
    serial = rng.randint(1, 499) if sex == "M" else rng.randint(500, 999)
    body = f"{day:02d}{month:02d}{yyy:03d}{_REGION_SI}{serial:03d}"
    code = body + str(_emso_check_digit(body))
    return code, f"{birth_year:04d}-{month:02d}-{day:02d}"


def emso_valid(value: str) -> bool:
    """True iff a 13-digit EMŠO is structurally valid (delegates to the one source of truth)."""
    from europriv_bench.national_id import parse_national_id  # one source of truth
    return parse_national_id(value, "SI").valid


def emso_sex(value: str) -> str:
    return "M" if int(value[9:12]) < 500 else "F"


def gen_tax_number(rng: random.Random) -> str:
    """Valid Slovenian davčna številka: 7 digits + weighted mod-11 control digit (8..2)."""
    while True:
        body = [rng.randint(0, 9) for _ in range(7)]
        total = sum(d * w for d, w in zip(body, _TAX_WEIGHTS))
        rem = total % 11
        check = 11 - rem
        if check == 10:           # remainder 1 → no valid control digit; redraw (documented)
            continue
        if check == 11:
            check = 0
        return "".join(map(str, body)) + str(check)


def tax_number_valid(value: str) -> bool:
    s = value.replace(" ", "")
    if len(s) != 8 or not s.isdigit():
        return False
    total = sum(int(d) * w for d, w in zip(s[:7], _TAX_WEIGHTS))
    rem = total % 11
    check = 11 - rem
    if check == 10:
        return False
    if check == 11:
        check = 0
    return check == int(s[7])


def gen_iban_si(rng: random.Random) -> str:
    """Valid Slovenian IBAN (mod-97): SI + 2 check + 15-digit BBAN."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(15))
    rearranged = bban + "SI00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"SI{check:02d}{bban}"


def iban_si_valid(iban: str) -> bool:
    if not iban.startswith("SI") or len(iban) != 19:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def gen_phone_si(rng: random.Random) -> str:
    """Slovenian mobile, +386 NN NNN NNN (no checksum — documented as such)."""
    return f"+386 {rng.choice([31, 40, 41, 51, 64, 70])} {rng.randint(100, 999)} {rng.randint(100, 999)}"


def _ascii(s: str) -> str:
    """ASCII-fold Slovenian diacritics (č/š/ž) for realistic emails."""
    table = {"č": "c", "š": "s", "ž": "z"}
    for k, v in table.items():
        s = s.replace(k, v).replace(k.upper(), v.upper())
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Slovenian person: EMŠO sex matches the name, DOB + region derived from /
    consistent with the EMŠO, address city matches its statistical region."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    last = rng.choice(SURNAMES)
    code, dob = gen_emso(rng, sex)
    city, region = rng.choice(CITIES)
    return Person(
        first_name=first,
        last_name=last,
        sex=sex,
        emso=code,
        dob=dob,  # consistent with the EMŠO by construction
        region=region,
        city=city,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, SI-{rng.randint(1000, 9999)} {city}",
        postcode=f"SI-{rng.randint(1000, 9999)}",
        phone=gen_phone_si(rng),
        iban=gen_iban_si(rng),
        tax_number=gen_tax_number(rng),
    )


__all__ = [
    "Person", "gen_emso", "emso_valid", "emso_sex",
    "gen_tax_number", "tax_number_valid", "gen_iban_si", "iban_si_valid", "gen_phone_si",
    "gen_person", "CITIES",
]
