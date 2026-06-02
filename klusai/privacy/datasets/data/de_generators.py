"""Checksum-valid, coherent German PII generators (localized synthetic — not MT).

Same P0 contract as RO/PL/EN/IT: identifiers carry VALID checksums where the scheme defines one.
Pure, seeded, no LLM/network.

Identifiers:
  - **Steuer-IdNr** — 11-digit German tax id with a mod-11/mod-10 ("ISO 7064 MOD 11,10") check digit.
    Coverage-only quasi-identifier-wise (carries no DOB/sex), but it HAS a checksum, so we generate a
    checksum-valid value and self-test it.
  - **IBAN (DE)** — 22-char mod-97 IBAN: DE + 2 check + 8-digit BLZ + 10-digit account.
  - **USt-IdNr** — VAT number "DE" + 9 digits (mod-11/mod-10 check on the 9 digits).

Phone (+49) carries no published checksum and is documented as such.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

MALE_NAMES = ["Lukas", "Maximilian", "Paul", "Leon", "Felix", "Jonas", "Tim", "Niklas"]
FEMALE_NAMES = ["Marie", "Sophie", "Anna", "Lena", "Laura", "Julia", "Hannah", "Lea"]
SURNAMES = ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker"]
# (city, Bundesland) — kept coherent so address city matches its state.
CITIES = [
    ("Berlin", "Berlin"), ("München", "Bayern"), ("Hamburg", "Hamburg"),
    ("Köln", "Nordrhein-Westfalen"), ("Frankfurt", "Hessen"), ("Stuttgart", "Baden-Württemberg"),
    ("Dresden", "Sachsen"), ("Hannover", "Niedersachsen"),
]
STREETS = ["Hauptstraße", "Bahnhofstraße", "Schillerstraße", "Goethestraße", "Lindenstraße"]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    steuer_id: str
    city: str
    state: str
    address: str
    plz: str          # 5-digit postal code
    phone: str
    iban: str


def _iso7064_mod11_10(body: str) -> int:
    """ISO 7064 MOD 11,10 check digit for a numeric ``body`` (German tax-id / USt-IdNr scheme)."""
    p = 10
    for ch in body:
        s = (int(ch) + p) % 10
        s = s if s != 0 else 10
        p = (2 * s) % 11
    return (11 - p) % 10


def gen_steuer_id(rng: random.Random) -> str:
    """Valid 11-digit Steuer-IdNr (mod-11/mod-10 check digit on the leading 10 digits)."""
    body = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(9)]  # first digit non-zero
    check = _iso7064_mod11_10("".join(map(str, body)))
    return "".join(map(str, body)) + str(check)


def steuer_id_valid(value: str) -> bool:
    if not value.isdigit() or len(value) != 11 or value[0] == "0":
        return False
    return _iso7064_mod11_10(value[:10]) == int(value[10])


def gen_ust_idnr(rng: random.Random) -> str:
    """German VAT number: 'DE' + 9 digits with a mod-11/mod-10 check digit."""
    body = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(7)]
    check = _iso7064_mod11_10("".join(map(str, body)))
    return "DE" + "".join(map(str, body)) + str(check)


def ust_idnr_valid(value: str) -> bool:
    if not value.startswith("DE") or len(value) != 11 or not value[2:].isdigit():
        return False
    return _iso7064_mod11_10(value[2:10]) == int(value[10])


def gen_iban_de(rng: random.Random) -> str:
    """Valid German IBAN (mod-97): DE + 2 check + 8-digit BLZ + 10-digit account."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(18))
    rearranged = bban + "DE00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"DE{check:02d}{bban}"


def iban_de_valid(iban: str) -> bool:
    if not iban.startswith("DE") or len(iban) != 22:
        return False
    rearranged = iban[4:] + iban[:4]
    try:
        return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1
    except ValueError:
        return False


def gen_phone_de(rng: random.Random) -> str:
    """German mobile, +49 1NN NNNNNNN (no checksum)."""
    return f"+49 1{rng.randint(50, 79)} {rng.randint(1000000, 9999999)}"


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic German person (city matches state; ids are checksum-valid)."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    city, state = rng.choice(CITIES)
    plz = f"{rng.randint(10000, 99999)}"
    return Person(
        first_name=first,
        last_name=rng.choice(SURNAMES),
        sex=sex,
        steuer_id=gen_steuer_id(rng),
        city=city,
        state=state,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {plz} {city}",
        plz=plz,
        phone=gen_phone_de(rng),
        iban=gen_iban_de(rng),
    )


__all__ = [
    "Person", "gen_steuer_id", "steuer_id_valid", "gen_ust_idnr", "ust_idnr_valid",
    "gen_iban_de", "iban_de_valid", "gen_phone_de", "gen_person", "CITIES",
]
