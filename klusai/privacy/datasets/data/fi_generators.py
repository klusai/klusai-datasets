"""Checksum/format-valid, coherent Finnish PII generators (localized synthetic — not MT).

Same P0 contract as the Romanian/Polish/Swedish/Czech generators: identifiers must carry VALID
checksums/control characters and realistic structure (else we teach models the wrong invariants).
Pure, seeded, no LLM/network.

Identifiers:
  - **henkilötunnus** — 11-char national id ``DDMMYYCZZZQ``. Digits 1-6 encode the birth date; ``C``
    is the century marker (``+`` 1800s; ``-``/``Y``/``X``/``W``/``V``/``U`` 1900s; ``A``-``F``
    2000s — the 2023 DVV separator reform); ``ZZZ`` is the individual number (002-899, odd=M,
    even=F); ``Q`` is the control character = ``int(DDMMYYZZZ) % 31`` indexed into the 31-char map
    ``"0123456789ABCDEFHJKLMNPRSTUVWXY"``. DOB and sex are coherent with the chosen Finnish name.
    The validator (``europriv_bench.national_id`` country=``FI``) cross-checks every generated id
    (one source of truth).
  - **Y-tunnus** — 7-digit + weighted-mod-11 check business id, printed ``NNNNNNN-C``.
  - **IBAN (FI)** — 18-char mod-97 IBAN: FI + 2 check + 14-digit BBAN.

There is no LLM step; henkilötunnus sex/birth-date are coherent with the chosen Finnish given name.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass

MALE_NAMES = ["Juhani", "Mikael", "Matti", "Antero", "Tapani", "Ville", "Mika", "Pekka"]
FEMALE_NAMES = ["Maria", "Anneli", "Johanna", "Kaarina", "Marjatta", "Liisa", "Hanna", "Sofia"]
SURNAMES = ["Korhonen", "Virtanen", "Mäkinen", "Nieminen", "Mäkelä", "Hämäläinen", "Laine", "Heikkinen"]
# (city, region/maakunta) pairs — kept coherent so address city matches its region.
CITIES = [
    ("Helsinki", "Uusimaa"), ("Espoo", "Uusimaa"), ("Tampere", "Pirkanmaa"),
    ("Vantaa", "Uusimaa"), ("Oulu", "Pohjois-Pohjanmaa"), ("Turku", "Varsinais-Suomi"),
    ("Jyväskylä", "Keski-Suomi"), ("Kuopio", "Pohjois-Savo"),
]
STREETS = ["Mannerheimintie", "Aleksanterinkatu", "Hämeenkatu", "Kauppakatu", "Koulukatu", "Kirkkokatu"]

# Control-character map: index = int(DDMMYYZZZ) % 31. Letters G/I/O/Q/Z omitted (ambiguity).
_FI_CONTROL_MAP = "0123456789ABCDEFHJKLMNPRSTUVWXY"
# Century markers we EMIT (the canonical pre-2023 ones — '-' for 1900s, 'A' for 2000s); the
# validator additionally accepts the 2023-reform separators (Y/X/W/V/U, B-F).
_FI_MARKER = {1900: "-", 2000: "A"}
_YTUNNUS_WEIGHTS = [7, 9, 10, 5, 8, 4, 2]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    hetu: str
    dob: str          # YYYY-MM-DD — DERIVED from the henkilötunnus (stays consistent with it)
    city: str
    region: str
    address: str
    postcode: str     # NNNNN
    phone: str
    iban: str


def _control_char(ddmmyyzzz: str) -> str:
    return _FI_CONTROL_MAP[int(ddmmyyzzz) % 31]


def gen_hetu(rng: random.Random, sex: str, birth_year: int | None = None) -> tuple[str, str]:
    """Valid 11-char henkilötunnus for a given sex + its derived ISO DOB.

    Returns ``(hetu, 'YYYY-MM-DD')``. The century marker is set from the birth year; the individual
    number ``ZZZ`` parity encodes sex; ``Q`` is the mod-31 control character over ``DDMMYYZZZ``.
    """
    if birth_year is None:
        birth_year = rng.randint(1940, 2010)
    yy = birth_year % 100
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)  # <=28 -> valid in every month
    century = (birth_year // 100) * 100
    marker = _FI_MARKER[century]
    # Individual number 002-899 with the right parity for sex.
    zzz = rng.randint(2, 899)
    if sex == "M" and zzz % 2 == 0:
        zzz += 1
    elif sex == "F" and zzz % 2 == 1:
        zzz += 1
    date_digits = f"{day:02d}{month:02d}{yy:02d}"
    individual = f"{zzz:03d}"
    control = _control_char(date_digits + individual)
    return f"{date_digits}{marker}{individual}{control}", f"{birth_year:04d}-{month:02d}-{day:02d}"


def hetu_valid(value: str) -> bool:
    """True iff a henkilötunnus is format + century-marker + mod-31-control + date valid."""
    from europriv_bench.national_id import parse_national_id  # one source of truth
    return parse_national_id(value, "FI").valid


def hetu_sex(value: str) -> str:
    return "M" if int(value[7:10]) % 2 == 1 else "F"


def gen_ytunnus(rng: random.Random) -> str:
    """Valid Finnish Y-tunnus (business id): 7 digits + weighted mod-11 check, printed ``NNNNNNN-C``."""
    while True:
        body = [rng.randint(0, 9) for _ in range(7)]
        total = sum(d * w for d, w in zip(body, _YTUNNUS_WEIGHTS))
        rem = total % 11
        if rem == 1:
            continue  # remainder 1 has no valid check digit (DVV rule) — redraw
        check = 0 if rem == 0 else 11 - rem
        return "".join(map(str, body)) + "-" + str(check)


def ytunnus_valid(value: str) -> bool:
    s = value.replace("-", "")
    if len(s) != 8 or not s.isdigit():
        return False
    total = sum(int(d) * w for d, w in zip(s[:7], _YTUNNUS_WEIGHTS))
    rem = total % 11
    if rem == 1:
        return False
    check = 0 if rem == 0 else 11 - rem
    return check == int(s[7])


def gen_iban_fi(rng: random.Random) -> str:
    """Valid Finnish IBAN (mod-97): FI + 2 check + 14-digit BBAN."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(14))
    rearranged = bban + "FI00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"FI{check:02d}{bban}"


def iban_fi_valid(iban: str) -> bool:
    if not iban.startswith("FI") or len(iban) != 18:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def gen_phone_fi(rng: random.Random) -> str:
    """Finnish mobile, +358 4N NNN NNNN (no checksum — documented as such)."""
    return f"+358 4{rng.randint(0, 9)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}"


def _ascii(s: str) -> str:
    """ASCII-fold Finnish diacritics (ä/ö/å) for realistic emails."""
    s = s.replace("ä", "a").replace("ö", "o").replace("å", "a")
    s = s.replace("Ä", "A").replace("Ö", "O").replace("Å", "A")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Finnish person: henkilötunnus sex matches the name, DOB derived from
    the henkilötunnus, address city matches its region."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    last = rng.choice(SURNAMES)
    hetu, dob = gen_hetu(rng, sex)
    city, region = rng.choice(CITIES)
    return Person(
        first_name=first,
        last_name=last,
        sex=sex,
        hetu=hetu,
        dob=dob,  # consistent with the henkilötunnus by construction
        city=city,
        region=region,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {rng.randint(10000, 99999)} {city}",
        postcode=f"{rng.randint(10000, 99999)}",
        phone=gen_phone_fi(rng),
        iban=gen_iban_fi(rng),
    )


__all__ = [
    "Person", "gen_hetu", "hetu_valid", "hetu_sex",
    "gen_ytunnus", "ytunnus_valid", "gen_iban_fi", "iban_fi_valid", "gen_phone_fi",
    "gen_person", "CITIES",
]
