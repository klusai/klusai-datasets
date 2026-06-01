"""PL generators must produce checksum-valid, coherent identifiers (deterministic / seeded)."""

import random

from klusai.privacy.datasets.data import pl_generators as pl


def test_generated_identifiers_pass_their_checksums():
    rng = random.Random(0)
    for _ in range(300):
        p = pl.gen_person(rng)
        assert pl.pesel_valid(p.pesel)
        assert pl.nip_valid(pl.gen_nip(rng))
        assert pl.regon9_valid(pl.gen_regon9(rng))
        assert pl.iban_pl_valid(pl.gen_iban_pl(rng))


def test_pesel_is_coherent():
    rng = random.Random(1)
    for _ in range(200):
        p = pl.gen_person(rng)
        assert pl.pesel_sex(p.pesel) == p.sex            # PESEL sex digit matches the chosen name
        d, m, y = p.dob.split(".")                       # DOB decoded FROM the PESEL
        assert 1940 <= int(y) <= 2010
        assert 1 <= int(m) <= 12 and 1 <= int(d) <= 31
        assert p.city in p.address                       # address city consistent


def test_known_reference_pesel_validates():
    # 44051401359 is a widely-cited structurally-valid PESEL.
    assert pl.pesel_valid("44051401359")


def test_nip_validator_rejects_tampered_checksum():
    rng = random.Random(5)
    nip = pl.gen_nip(rng)
    assert pl.nip_valid(nip)
    # flip the control digit → must be rejected
    tampered = nip[:-1] + str((int(nip[-1]) + 1) % 10)
    assert not pl.nip_valid(tampered)


def test_iban_validator_rejects_tampered_checksum():
    rng = random.Random(6)
    iban = pl.gen_iban_pl(rng)
    assert pl.iban_pl_valid(iban)
    tampered = iban[:4] + str((int(iban[4]) + 1) % 10) + iban[5:]
    assert not pl.iban_pl_valid(tampered)


def test_seeded_generation_is_deterministic():
    assert pl.gen_person(random.Random(42)).pesel == pl.gen_person(random.Random(42)).pesel
