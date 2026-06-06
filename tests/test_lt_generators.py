"""Lithuanian generators (RES-84): asmens kodas must be checksum-valid, sex/DOB-coherent, and decode
consistently against the europriv_bench asmens-kodas validator (one source of truth). The check digit
is an ISO-7064-style two-pass mod-11 IDENTICAL to the Estonian isikukood; the 1st digit carries
century+sex."""

import random

from europriv_bench.national_id import parse_national_id
from klusai.privacy.datasets.data import lt_generators as lt


def test_asmens_kodas_valid_and_sex_dob_coherent():
    rng = random.Random(0)
    for _ in range(500):
        p = lt.gen_person(rng)
        assert lt.asmens_kodas_valid(p.asmens_kodas)
        info = parse_national_id(p.asmens_kodas, "LT")
        assert info.valid
        assert info.extra["sex"] == p.sex          # 1st-digit parity matches the chosen name's sex
        assert info.extra["birth_date"] == p.dob   # century recovered from the 1st digit → full DOB


def test_asmens_kodas_two_pass_check_digit_rejection():
    rng = random.Random(5)
    for _ in range(200):
        ak = lt.gen_person(rng).asmens_kodas
        bad = ak[:-1] + str((int(ak[-1]) + 1) % 10)
        assert not lt.asmens_kodas_valid(bad)     # a wrong check digit must fail the mod-11


def test_imones_kodas_and_iban_valid():
    rng = random.Random(2)
    for _ in range(200):
        assert lt.imones_kodas_valid(lt.gen_imones_kodas(rng))
        assert lt.iban_lt_valid(lt.gen_iban_lt(rng))


def test_imones_kodas_and_iban_disjoint_from_asmens_kodas():
    # An įmonės kodas (9 digits) / IBAN must never mis-decode as a valid LT asmens kodas (re-id
    # collision footgun — EE/LT/LV share structure; the SE-orgnr lesson from RES-80).
    rng = random.Random(3)
    for _ in range(200):
        assert not parse_national_id(lt.gen_imones_kodas(rng), "LT").valid
        assert not parse_national_id(lt.gen_iban_lt(rng), "LT").valid


def test_generation_is_deterministic():
    assert lt.gen_person(random.Random(7)).asmens_kodas == lt.gen_person(random.Random(7)).asmens_kodas
