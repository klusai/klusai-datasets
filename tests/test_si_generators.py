"""Slovenian generators (RES-85): EMŠO must be checksum-valid, sex/DOB/region-coherent, and decode
consistently against the europriv_bench EMŠO validator (one source of truth). EMŠO is a RICHER
decode-bearing surface than the Baltic family — it also discloses REGION OF BIRTH (RR)."""

import random

from europriv_bench.national_id import parse_national_id
from klusai.privacy.datasets.data import si_generators as si


def test_emso_valid_and_sex_dob_region_coherent():
    rng = random.Random(0)
    for _ in range(500):
        p = si.gen_person(rng)
        assert si.emso_valid(p.emso)
        info = parse_national_id(p.emso, "SI")
        assert info.valid
        assert info.extra["sex"] == p.sex             # serial encodes sex; matches the chosen name
        assert info.extra["birth_date"] == p.dob      # ex-YU century convention → full DOB recovered
        assert info.extra["region_code"] == "50"      # Slovenia
        # The richer surface: a missed EMŠO discloses DOB + SEX + REGION_OF_BIRTH (3 QIs).
        assert info.disclosed_quasi_identifiers() == {"DATE_OF_BIRTH", "SEX", "REGION_OF_BIRTH"}


def test_emso_check_digit_rejection():
    rng = random.Random(5)
    for _ in range(200):
        emso = si.gen_person(rng).emso
        bad = emso[:-1] + str((int(emso[-1]) + 1) % 10)
        assert not si.emso_valid(bad)                 # a wrong check digit must fail the mod-11


def test_tax_number_and_iban_valid():
    rng = random.Random(2)
    for _ in range(200):
        assert si.tax_number_valid(si.gen_tax_number(rng))
        assert si.iban_si_valid(si.gen_iban_si(rng))


def test_tax_number_and_iban_disjoint_from_emso():
    # A davčna številka (8 digits) / IBAN must never mis-decode as a valid SI EMŠO (re-id collision
    # footgun — the ex-YU family shares structure; the SE-orgnr lesson from RES-80).
    rng = random.Random(3)
    for _ in range(200):
        assert not parse_national_id(si.gen_tax_number(rng), "SI").valid
        assert not parse_national_id(si.gen_iban_si(rng), "SI").valid


def test_generation_is_deterministic():
    assert si.gen_person(random.Random(7)).emso == si.gen_person(random.Random(7)).emso
