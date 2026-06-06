"""Swedish generators (RES-80): personnummer must be Luhn-valid, sex/DOB-coherent, and decode
consistently against the europriv_bench personnummer validator (one source of truth)."""

import random

from europriv_bench.national_id import parse_national_id
from klusai.privacy.datasets.data import se_generators as se


def test_personnummer_luhn_valid_and_sex_dob_coherent():
    rng = random.Random(0)
    for _ in range(500):
        p = se.gen_person(rng)
        assert se.personnummer_valid(p.personnummer)
        info = parse_national_id(p.personnummer, "SE")
        assert info.valid
        assert info.extra["sex"] == p.sex  # personnummer sex digit matches the chosen name's sex
        y, m, d = (int(x) for x in p.dob.split("-"))
        assert info.extra["birth_month"] == m and info.extra["birth_day"] == d


def test_known_skatteverket_test_vector():
    # 800101-812X with Luhn check 9 → 8001018129 (a documented Skatteverket-style example).
    assert se.personnummer_valid("8001018129")
    assert se._luhn_check_digit("800101812") == 9


def test_personnummer_rejects_bad_checksum():
    rng = random.Random(1)
    pn = se.gen_person(rng).personnummer.replace("-", "")
    bad = pn[:-1] + str((int(pn[-1]) + 1) % 10)
    assert not se.personnummer_valid(bad)
    assert not parse_national_id(bad, "SE").valid


def test_orgnr_and_iban_valid():
    rng = random.Random(2)
    for _ in range(200):
        assert se.orgnr_valid(se.gen_orgnr(rng))
        assert se.iban_se_valid(se.gen_iban_se(rng))


def test_generation_is_deterministic():
    a = [se.gen_person(random.Random(7)).personnummer]
    b = [se.gen_person(random.Random(7)).personnummer]
    assert a == b
