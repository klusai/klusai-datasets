"""Finnish generators (RES-83): henkilötunnus must be control-char-valid, sex/DOB-coherent, and decode
consistently against the europriv_bench henkilötunnus validator (one source of truth)."""

import random

from europriv_bench.national_id import parse_national_id
from klusai.privacy.datasets.data import fi_generators as fi


def test_henkilotunnus_valid_and_sex_dob_coherent():
    rng = random.Random(0)
    for _ in range(500):
        p = fi.gen_person(rng)
        assert fi.hetu_valid(p.hetu)
        info = parse_national_id(p.hetu, "FI")
        assert info.valid
        assert info.extra["sex"] == p.sex          # individual-number parity matches the name's sex
        assert info.extra["birth_date"] == p.dob   # century recovered from the marker


def test_known_dvv_control_char_vector():
    # DVV canonical example: 131052-308T (13 Oct 1952). The control char is the mod-31 map char.
    assert fi.hetu_valid("131052-308T")
    assert fi._control_char("131052308") == "T"


def test_henkilotunnus_rejects_bad_control_char():
    rng = random.Random(1)
    h = fi.gen_person(rng).hetu
    bad = h[:-1] + ("U" if h[-1] != "U" else "V")
    assert not fi.hetu_valid(bad)
    assert not parse_national_id(bad, "FI").valid


def test_ytunnus_and_iban_valid():
    rng = random.Random(2)
    for _ in range(200):
        assert fi.ytunnus_valid(fi.gen_ytunnus(rng))
        assert fi.iban_fi_valid(fi.gen_iban_fi(rng))


def test_ytunnus_and_iban_disjoint_from_henkilotunnus():
    # A Y-tunnus / IBAN must never mis-decode as a valid FI henkilötunnus (re-id collision footgun).
    rng = random.Random(3)
    for _ in range(200):
        assert not parse_national_id(fi.gen_ytunnus(rng), "FI").valid
        assert not parse_national_id(fi.gen_iban_fi(rng), "FI").valid


def test_generation_is_deterministic():
    assert fi.gen_person(random.Random(7)).hetu == fi.gen_person(random.Random(7)).hetu
