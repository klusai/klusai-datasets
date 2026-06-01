"""EN/UK generators: checksum-valid where a checksum exists, format-valid otherwise (seeded)."""

import random

from klusai.privacy.datasets.data import en_generators as en


def test_checksummed_identifiers_pass_their_checksums():
    rng = random.Random(0)
    for _ in range(300):
        p = en.gen_person(rng)
        assert en.iban_gb_valid(p.iban)   # mod-97
        assert en.card_valid(p.card)      # Luhn
        assert en.luhn_valid(en.gen_card(rng).replace(" ", ""))


def test_format_valid_identifiers_have_no_faked_checksum():
    rng = random.Random(1)
    for _ in range(200):
        p = en.gen_person(rng)
        assert en.nino_format_valid(p.nino)  # structure only — scheme defines no checksum
        assert en.ssn_format_valid(p.ssn)    # structure only


def test_known_reference_card_is_luhn_valid():
    assert en.luhn_valid("4539578763621486")


def test_luhn_and_iban_validators_reject_tampering():
    rng = random.Random(7)
    card = en.gen_card(rng).replace(" ", "")
    assert en.luhn_valid(card)
    tampered_card = card[:-1] + str((int(card[-1]) + 1) % 10)
    assert not en.luhn_valid(tampered_card)

    iban = en.gen_iban_gb(rng)
    assert en.iban_gb_valid(iban)
    # flip a check digit (positions 2-3 of a GB IBAN are numeric)
    tampered_iban = iban[:2] + str((int(iban[2]) + 1) % 10) + iban[3:]
    assert not en.iban_gb_valid(tampered_iban)


def test_ssn_excludes_invalid_area_666():
    rng = random.Random(3)
    for _ in range(500):
        area = int(en.gen_ssn(rng).split("-")[0])
        assert area != 666 and 1 <= area <= 899


def test_seeded_generation_is_deterministic():
    assert en.gen_person(random.Random(42)).iban == en.gen_person(random.Random(42)).iban
