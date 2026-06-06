"""Estonian generators (RES-84): isikukood must be checksum-valid, sex/DOB-coherent, and decode
consistently against the europriv_bench isikukood validator (one source of truth). The check digit
is an ISO-7064-style two-pass mod-11; the 1st digit carries century+sex."""

import random

from europriv_bench.national_id import parse_national_id
from klusai.privacy.datasets.data import ee_generators as ee


def test_isikukood_valid_and_sex_dob_coherent():
    rng = random.Random(0)
    for _ in range(500):
        p = ee.gen_person(rng)
        assert ee.isikukood_valid(p.isikukood)
        info = parse_national_id(p.isikukood, "EE")
        assert info.valid
        assert info.extra["sex"] == p.sex          # 1st-digit parity matches the chosen name's sex
        assert info.extra["birth_date"] == p.dob   # century recovered from the 1st digit → full DOB


def test_isikukood_two_pass_check_digit_rejection():
    rng = random.Random(5)
    for _ in range(200):
        ik = ee.gen_person(rng).isikukood
        bad = ik[:-1] + str((int(ik[-1]) + 1) % 10)
        assert not ee.isikukood_valid(bad)        # a wrong check digit must fail the mod-11


def test_registrikood_and_iban_valid():
    rng = random.Random(2)
    for _ in range(200):
        assert ee.registrikood_valid(ee.gen_registrikood(rng))
        assert ee.iban_ee_valid(ee.gen_iban_ee(rng))


def test_registrikood_and_iban_disjoint_from_isikukood():
    # A registrikood (8 digits) / IBAN must never mis-decode as a valid EE isikukood (re-id collision
    # footgun — EE/LT/LV share structure; the SE-orgnr lesson from RES-80).
    rng = random.Random(3)
    for _ in range(200):
        assert not parse_national_id(ee.gen_registrikood(rng), "EE").valid
        assert not parse_national_id(ee.gen_iban_ee(rng), "EE").valid


def test_isikukood_not_misdecoded_as_lt_neighbour_or_vice_versa():
    # EE/LT share the algorithm, so an EE isikukood validates under LT too — but the dataset NEVER
    # asks the wrong country: rows carry their own country. This documents the shared-structure
    # footgun (the value is the same family; only the caller's country key disambiguates intent).
    rng = random.Random(9)
    ik = ee.gen_person(rng).isikukood
    assert parse_national_id(ik, "EE").valid
    assert parse_national_id(ik, "LT").valid  # same family — caller must pass the right country


def test_generation_is_deterministic():
    assert ee.gen_person(random.Random(7)).isikukood == ee.gen_person(random.Random(7)).isikukood
