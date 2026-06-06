"""Czech generators (RES-80): rodné číslo must be mod-11-valid, sex/DOB-coherent, and decode
consistently against the europriv_bench rodné-číslo validator (one source of truth)."""

import random

from europriv_bench.national_id import parse_national_id
from klusai.privacy.datasets.data import cz_generators as cz


def test_rodne_cislo_mod11_valid_and_sex_dob_coherent():
    rng = random.Random(0)
    for _ in range(500):
        p = cz.gen_person(rng)
        assert cz.rodne_cislo_valid(p.rodne_cislo)
        digits = p.rodne_cislo.replace("/", "")
        assert int(digits) % 11 == 0  # the whole 10-digit number is divisible by 11
        info = parse_national_id(p.rodne_cislo, "CZ")
        assert info.valid
        assert info.extra["sex"] == p.sex          # female month +50 matches the chosen name's sex
        assert info.extra["birth_date"] == p.dob   # DOB fully recoverable (modern 10-digit form)


def test_female_month_offset_plus_50():
    rng = random.Random(3)
    seen_female = False
    for _ in range(500):
        p = cz.gen_person(rng)
        mm = int(p.rodne_cislo.replace("/", "")[2:4])
        if p.sex == "F":
            seen_female = True
            assert 51 <= mm <= 62  # female births carry month +50
        else:
            assert 1 <= mm <= 12
    assert seen_female


def test_rodne_cislo_rejects_bad_checksum():
    rng = random.Random(1)
    rc = cz.gen_person(rng).rodne_cislo.replace("/", "")
    bad = rc[:-1] + str((int(rc[-1]) + 1) % 10)
    assert not cz.rodne_cislo_valid(bad)
    assert not parse_national_id(bad, "CZ").valid


def test_ico_and_iban_valid():
    rng = random.Random(2)
    for _ in range(200):
        assert cz.ico_valid(cz.gen_ico(rng))
        assert cz.iban_cz_valid(cz.gen_iban_cz(rng))


def test_generation_is_deterministic():
    a = cz.gen_person(random.Random(7)).rodne_cislo
    b = cz.gen_person(random.Random(7)).rodne_cislo
    assert a == b
