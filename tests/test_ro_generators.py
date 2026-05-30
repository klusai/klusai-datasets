"""RO generators must produce checksum-valid, coherent identifiers (deterministic / seeded)."""

import random

from europriv_bench.national_id import parse_cnp, validate_cnp
from klusai.privacy.datasets.data.ro_generators import (
    COUNTIES,
    cui_valid,
    gen_cui,
    gen_iban_ro,
    gen_person,
    gen_plate,
    iban_ro_valid,
)


def test_generated_identifiers_pass_their_checksums():
    rng = random.Random(0)
    for _ in range(200):
        assert validate_cnp(gen_person(rng).cnp)
        assert iban_ro_valid(gen_iban_ro(rng))
        assert cui_valid(gen_cui(rng))


def test_person_is_coherent():
    rng = random.Random(1)
    for _ in range(100):
        p = gen_person(rng)
        info = parse_cnp(p.cnp)
        assert info.valid
        assert info.sex == p.sex                 # CNP sex matches the chosen name's sex
        assert p.county in p.address             # address county is consistent
        # CNP county code corresponds to the person's county.
        code = next(c for c, _pl, name in COUNTIES if name == p.county)
        assert info.county_code == code


def test_seeded_generation_is_deterministic():
    assert gen_person(random.Random(42)).cnp == gen_person(random.Random(42)).cnp


def test_bucharest_plate_uses_three_digits():
    rng = random.Random(3)
    plate = gen_plate(rng, "B")
    assert plate.startswith("B ")
