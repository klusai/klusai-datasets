"""Danish generators (RES-83): CPR-nummer must be format/century-valid, sex/DOB-coherent, and decode
consistently against the europriv_bench CPR validator (one source of truth). The mod-11 check was
abolished in 2007, so we validate format + the century table, NOT a checksum."""

import random

from europriv_bench.national_id import parse_national_id
from klusai.privacy.datasets.data import dk_generators as dk


def test_cpr_format_valid_and_sex_dob_coherent():
    rng = random.Random(0)
    for _ in range(500):
        p = dk.gen_person(rng)
        assert dk.cpr_valid(p.cpr)
        info = parse_national_id(p.cpr, "DK")
        assert info.valid
        assert info.extra["sex"] == p.sex          # last-digit parity matches the chosen name's sex
        assert info.extra["birth_date"] == p.dob   # century recovered from the 7th-digit/YY table


def test_cpr_no_mod11_required():
    # Most generated post-2007-style CPRs are NOT mod-11-divisible; they must still validate.
    rng = random.Random(5)
    weights = (4, 3, 2, 7, 6, 5, 4, 3, 2, 1)
    non_mod11 = 0
    for _ in range(200):
        cpr = dk.gen_person(rng).cpr.replace("-", "")
        assert dk.cpr_valid(cpr)
        if sum(int(d) * w for d, w in zip(cpr, weights)) % 11 != 0:
            non_mod11 += 1
    assert non_mod11 > 0, "generator only emits mod-11-valid CPRs — would teach an abolished invariant"


def test_cvr_and_iban_valid():
    rng = random.Random(2)
    for _ in range(200):
        assert dk.cvr_valid(dk.gen_cvr(rng))
        assert dk.iban_dk_valid(dk.gen_iban_dk(rng))


def test_cvr_and_iban_disjoint_from_cpr():
    # A CVR (8 digits) / IBAN must never mis-decode as a valid DK CPR (re-id collision footgun).
    rng = random.Random(3)
    for _ in range(200):
        assert not parse_national_id(dk.gen_cvr(rng), "DK").valid
        assert not parse_national_id(dk.gen_iban_dk(rng), "DK").valid


def test_generation_is_deterministic():
    assert dk.gen_person(random.Random(7)).cpr == dk.gen_person(random.Random(7)).cpr
