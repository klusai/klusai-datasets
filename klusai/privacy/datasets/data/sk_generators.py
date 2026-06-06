"""Checksum-valid, coherent Slovak PII generators (localized synthetic — not MT).

Same P0 contract as the Czech generators — and the SAME identifier: the Slovak **rodné číslo** uses
the IDENTICAL algorithm as the Czech one (SK Zákon č. 301/2000 Z. z. / the shared Czechoslovak Zákon
č. 133/2000 Sb. scheme). So this module **reuses the CZ rodné-číslo generator verbatim**
(``cz_generators.gen_rodne_cislo``) and only supplies Slovak locale content (names, cities, IBAN,
phone). The validator delegates to ``europriv_bench.national_id`` country ``SK`` (one source of
truth) — which itself reuses the CZ decoder tagged as SK.

Identifiers:
  - **rodné číslo** — 10-digit ``YYMMDD/SSSC``; female month +50; the whole 10-digit number is
    divisible by 11. Decode-bearing: discloses SEX + DATE_OF_BIRTH. (Reused from cz_generators.)
  - **IČO** — 8-digit company id (same weighted mod-11 as CZ; reused from cz_generators).
  - **IBAN (SK)** — 24-char mod-97 IBAN: SK + 2 check + 4-digit bank + 16-digit account.

COLLISION FOOTGUN (RES-85): a CZ and an SK rodné číslo are structurally identical — only the row
``country`` tag distinguishes them. The skeleton emits ``country="SK"`` so the leak metric dispatches
to the SK validator; the validator never auto-detects, so an SK number is never mis-decoded as CZ.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass

# Reuse the Czech rodné-číslo + IČO generators verbatim — SK uses the SAME algorithm (no duplicate).
from .cz_generators import gen_ico, gen_rodne_cislo, ico_valid, rodne_cislo_sex

MALE_NAMES = ["Martin", "Peter", "Tomáš", "Marek", "Juraj", "Lukáš", "Michal", "Jozef"]
FEMALE_NAMES = ["Mária", "Anna", "Zuzana", "Katarína", "Lucia", "Jana", "Eva", "Martina"]
# Surnames: masculine / feminine forms (the -ová feminine suffix is real Slovak morphology).
SURNAMES_M = ["Novák", "Horváth", "Kováč", "Varga", "Tóth", "Baláž", "Hudák", "Kollár"]
SURNAMES_F = ["Nováková", "Horváthová", "Kováčová", "Vargová", "Tóthová", "Balážová", "Hudáková", "Kollárová"]
# (city, region/kraj) pairs — kept coherent so address city matches its region.
CITIES = [
    ("Bratislava", "Bratislavský kraj"), ("Košice", "Košický kraj"),
    ("Prešov", "Prešovský kraj"), ("Žilina", "Žilinský kraj"),
    ("Nitra", "Nitriansky kraj"), ("Banská Bystrica", "Banskobystrický kraj"),
    ("Trnava", "Trnavský kraj"), ("Trenčín", "Trenčiansky kraj"),
]
STREETS = ["Hlavná", "Štúrova", "Hviezdoslavova", "Mierová", "Komenského", "Školská"]


@dataclass
class Person:
    first_name: str
    last_name: str
    sex: str          # "M" | "F"
    rodne_cislo: str
    dob: str          # YYYY-MM-DD — DERIVED from the rodné číslo (stays consistent with it)
    city: str
    region: str
    address: str
    postcode: str     # NNN NN
    phone: str
    iban: str


def rodne_cislo_valid(value: str) -> bool:
    """True iff a rodné číslo is valid AS A SLOVAK id (one source of truth — same algorithm as CZ)."""
    from europriv_bench.national_id import parse_national_id
    return parse_national_id(value, "SK").valid


def gen_iban_sk(rng: random.Random) -> str:
    """Valid Slovak IBAN (mod-97): SK + 2 check + 20-digit BBAN (4 bank + 16 account)."""
    bban = "".join(str(rng.randint(0, 9)) for _ in range(20))
    rearranged = bban + "SK00"
    n = int("".join(str(int(c, 36)) for c in rearranged))
    check = 98 - (n % 97)
    return f"SK{check:02d}{bban}"


def iban_sk_valid(iban: str) -> bool:
    if not iban.startswith("SK") or len(iban) != 24:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def gen_phone_sk(rng: random.Random) -> str:
    """Slovak mobile, +421 9NN NNN NNN (no checksum — documented as such)."""
    return f"+421 9{rng.randint(00, 99):02d} {rng.randint(100, 999)} {rng.randint(100, 999)}"


def _ascii(s: str) -> str:
    """ASCII-fold Slovak diacritics for realistic emails."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def gen_person(rng: random.Random) -> Person:
    """A coherent synthetic Slovak person: rodné číslo sex matches the name, DOB derived from the
    rodné číslo, surname morphology agrees with sex, address city matches its region."""
    sex = rng.choice(["M", "F"])
    first = rng.choice(MALE_NAMES if sex == "M" else FEMALE_NAMES)
    last = rng.choice(SURNAMES_M if sex == "M" else SURNAMES_F)
    rc, dob = gen_rodne_cislo(rng, sex)   # the CZ generator — SK uses the SAME algorithm
    city, region = rng.choice(CITIES)
    return Person(
        first_name=first,
        last_name=last,
        sex=sex,
        rodne_cislo=rc,
        dob=dob,  # consistent with the rodné číslo by construction
        city=city,
        region=region,
        address=f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {rng.randint(800, 999)} {rng.randint(10, 99)} {city}",
        postcode=f"{rng.randint(800, 999)} {rng.randint(10, 99)}",
        phone=gen_phone_sk(rng),
        iban=gen_iban_sk(rng),
    )


__all__ = [
    "Person", "gen_rodne_cislo", "rodne_cislo_valid", "rodne_cislo_sex",
    "gen_ico", "ico_valid", "gen_iban_sk", "iban_sk_valid", "gen_phone_sk",
    "gen_person", "CITIES",
]
