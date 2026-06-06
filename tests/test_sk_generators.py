"""Slovak generators (RES-85): rodné číslo must be checksum-valid, sex/DOB-coherent, and decode
consistently against the europriv_bench SK validator (one source of truth). SK uses the SAME algorithm
as CZ — the generator reuses the CZ rodné-číslo generator verbatim; only the country tag differs."""

import random

from europriv_bench.national_id import parse_national_id
from klusai.privacy.datasets.data import sk_generators as sk


def test_rodne_cislo_valid_and_sex_dob_coherent():
    rng = random.Random(0)
    for _ in range(500):
        p = sk.gen_person(rng)
        assert sk.rodne_cislo_valid(p.rodne_cislo)
        info = parse_national_id(p.rodne_cislo, "SK")
        assert info.valid and info.country == "SK"
        assert info.extra["sex"] == p.sex            # month +50 for female matches the chosen name
        assert info.extra["birth_date"] == p.dob     # full DOB recovered (modern 10-digit form)
        assert info.disclosed_quasi_identifiers() == {"DATE_OF_BIRTH", "SEX"}


def test_rodne_cislo_check_digit_rejection():
    rng = random.Random(5)
    for _ in range(200):
        rc = sk.gen_person(rng).rodne_cislo.replace("/", "")
        bad = rc[:-1] + str((int(rc[-1]) + 1) % 10)
        assert not sk.rodne_cislo_valid(bad)         # break the mod-11 divisibility


def test_sk_and_cz_are_the_same_algorithm_distinguished_only_by_country():
    # COLLISION FOOTGUN: an SK rodné číslo is structurally identical to a CZ one — only the country
    # tag decides the dispatch. The same number validates under both; the registry never auto-detects.
    rng = random.Random(11)
    for _ in range(200):
        rc = sk.gen_person(rng).rodne_cislo
        assert parse_national_id(rc, "SK").valid
        assert parse_national_id(rc, "CZ").valid     # same digits, same algorithm
        assert parse_national_id(rc, "SK").country == "SK"
        assert parse_national_id(rc, "CZ").country == "CZ"


def test_ico_and_iban_valid_and_disjoint_from_rodne_cislo():
    rng = random.Random(2)
    for _ in range(200):
        assert sk.ico_valid(sk.gen_ico(rng))
        assert sk.iban_sk_valid(sk.gen_iban_sk(rng))
        # IČO (8 digits) must never mis-decode as a valid SK rodné číslo (re-id collision footgun).
        assert not parse_national_id(sk.gen_ico(rng), "SK").valid


def test_generation_is_deterministic():
    assert sk.gen_person(random.Random(7)).rodne_cislo == sk.gen_person(random.Random(7)).rodne_cislo
