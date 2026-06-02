"""T1 generator checks for de/fr/es/nl: checksum validity, coherence, tampered-checksum rejection.

(IT has its own dedicated suite in ``test_it_generators.py`` — it is the critical-path
decode-bearing identifier.) These mirror ``test_pl_generators.py`` per locale.
"""

import random

from europriv_bench.national_id import parse_national_id
from klusai.privacy.datasets.data import de_generators as de
from klusai.privacy.datasets.data import es_generators as es
from klusai.privacy.datasets.data import fr_generators as fr
from klusai.privacy.datasets.data import nl_generators as nl


def test_de_identifiers_pass_their_checksums():
    rng = random.Random(0)
    for _ in range(300):
        p = de.gen_person(rng)
        assert de.steuer_id_valid(p.steuer_id)
        assert de.iban_de_valid(p.iban)
        assert de.ust_idnr_valid(de.gen_ust_idnr(rng))


def test_de_steuer_id_rejects_tampered_checksum():
    rng = random.Random(3)
    sid = de.gen_steuer_id(rng)
    assert de.steuer_id_valid(sid)
    assert not de.steuer_id_valid(sid[:-1] + str((int(sid[-1]) + 1) % 10))


def test_fr_identifiers_pass_their_checksums():
    rng = random.Random(0)
    for _ in range(300):
        p = fr.gen_person(rng)
        assert fr.nir_valid(p.nir)
        assert fr.nir_sex(p.nir) == p.sex      # NIR sex digit matches the chosen name
        assert fr.iban_fr_valid(p.iban)
        assert fr.siren_valid(fr.gen_siren(rng))


def test_fr_nir_rejects_tampered_key():
    rng = random.Random(4)
    nir = fr.gen_nir(rng)
    assert fr.nir_valid(nir)
    assert not fr.nir_valid(nir[:-1] + str((int(nir[-1]) + 1) % 10))


def test_es_identifiers_pass_their_checksums_via_source_of_truth():
    rng = random.Random(0)
    for _ in range(300):
        p = es.gen_person(rng)
        assert es.dni_valid(p.dni)
        assert parse_national_id(p.dni, "ES").valid          # benchmark validator agrees
        assert not parse_national_id(p.dni, "ES").decode_bearing  # ES is coverage-only
        assert es.nie_valid(es.gen_nie(rng))
        assert es.iban_es_valid(p.iban)


def test_es_dni_rejects_tampered_letter():
    rng = random.Random(5)
    dni = es.gen_dni(rng)
    assert es.dni_valid(dni)
    bad = dni[:-1] + chr((ord(dni[-1]) - ord("A") + 1) % 26 + ord("A"))
    assert not es.dni_valid(bad)


def test_nl_identifiers_pass_their_checksums():
    rng = random.Random(0)
    for _ in range(300):
        p = nl.gen_person(rng)
        assert nl.bsn_valid(p.bsn)
        assert nl.iban_nl_valid(p.iban)


def test_nl_bsn_rejects_tampered_checksum():
    rng = random.Random(6)
    bsn = nl.gen_bsn(rng)
    assert nl.bsn_valid(bsn)
    assert not nl.bsn_valid(bsn[:-1] + str((int(bsn[-1]) + 5) % 10))


def test_seeded_generation_is_deterministic():
    for mod, attr in [(de, "steuer_id"), (fr, "nir"), (es, "dni"), (nl, "bsn")]:
        a = getattr(mod.gen_person(random.Random(42)), attr)
        b = getattr(mod.gen_person(random.Random(42)), attr)
        assert a == b
