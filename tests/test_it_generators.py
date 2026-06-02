"""IT generators must produce checksum-valid, decode-coherent identifiers (deterministic / seeded).

The codice fiscale is the critical-path decode-bearing identifier (KLU-105/106): a generated CF must
validate AND decode (sex/DOB/place) against ``europriv_bench.national_id`` — the single source of
truth the leakage metric uses.
"""

import random

from europriv_bench.national_id import parse_national_id
from klusai.privacy.datasets.data import it_generators as it


def test_generated_identifiers_pass_their_checksums():
    rng = random.Random(0)
    for _ in range(300):
        p = it.gen_person(rng)
        assert it.codice_fiscale_valid(p.codice_fiscale)
        assert it.partita_iva_valid(it.gen_partita_iva(rng))
        assert it.iban_it_valid(it.gen_iban_it(rng))


def test_codice_fiscale_decodes_coherently():
    """The CF the validator decodes must agree with the person's sex (decode-bearing coherence)."""
    rng = random.Random(1)
    for _ in range(200):
        p = it.gen_person(rng)
        info = parse_national_id(p.codice_fiscale, "IT")
        assert info.valid and info.decode_bearing
        assert info.extra["sex"] == p.sex
        # DOB the person reports is the one the CF actually encodes.
        dd, mm, yy = p.dob.split("/")
        assert int(dd) == info.extra["birth_day"]
        assert int(mm) == info.extra["birth_month"]
        assert {"DATE_OF_BIRTH", "SEX", "PLACE_OF_BIRTH"} == info.disclosed_quasi_identifiers()


def test_known_reference_codice_fiscale_validates():
    # RSSMRA85T10A562S — a widely-cited structurally-valid codice fiscale (Mario Rossi).
    assert it.codice_fiscale_valid("RSSMRA85T10A562S")


def test_partita_iva_validator_rejects_tampered_checksum():
    rng = random.Random(5)
    piva = it.gen_partita_iva(rng)
    assert it.partita_iva_valid(piva)
    tampered = piva[:-1] + str((int(piva[-1]) + 1) % 10)
    assert not it.partita_iva_valid(tampered)


def test_codice_fiscale_rejects_tampered_control_letter():
    rng = random.Random(6)
    cf = it.gen_person(rng).codice_fiscale
    assert it.codice_fiscale_valid(cf)
    tampered = cf[:-1] + chr((ord(cf[-1]) - ord("A") + 1) % 26 + ord("A"))
    assert not it.codice_fiscale_valid(tampered)


def test_iban_validator_rejects_tampered_checksum():
    rng = random.Random(7)
    iban = it.gen_iban_it(rng)
    assert it.iban_it_valid(iban)
    # Perturb the 2-digit mod-97 check field (positions 2-3); position 4 is the CIN letter.
    tampered = iban[:2] + str((int(iban[2]) + 1) % 10) + iban[3:]
    assert not it.iban_it_valid(tampered)


def test_seeded_generation_is_deterministic():
    a = it.gen_person(random.Random(42)).codice_fiscale
    b = it.gen_person(random.Random(42)).codice_fiscale
    assert a == b
