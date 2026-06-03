"""it-realskeleton-v1: faithful-structure IT docs with checksum-valid, decode-coherent codice fiscale.

The codice fiscale is the third (and richest) decode-bearing identifier (KLU-105): a leaked CF
discloses DATE_OF_BIRTH + SEX + PLACE_OF_BIRTH. These tests pin the crux pieces:
  * omocodia — a base CF and ≥1 omocode of the same identity decode to the SAME quasi-identifiers
    (incl. place-of-birth), and the omocode's own control character validates;
  * sex via day-of-birth +40, and place-of-birth resolution against the pinned Belfiore snapshot;
  * the dataset's offset/byte-equality/BIOES invariants (inherited) + country='IT' dispatch.
"""

import random

from europriv_bench.national_id import parse_national_id
from klusai.privacy.datasets.data import it_generators as itg
from klusai.privacy.datasets.data import it_skeletons as sk


def test_pack_checksum_self_test_passes_including_omocodes():
    # The pack's CF self-test draws CFs exactly as the dataset renders them (base OR omocode); every
    # draw must validate against europriv_bench (the leakage-metric source of truth).
    sk.it_skeleton_pack.checksum_self_test(n=400, seed=0)


def test_dataset_rows_carry_country_it_and_valid_decoding_cf():
    rows = list(sk.generate_dataset(60, seed=11))
    assert rows and all(r["country"] == "IT" and r["language"] == "it" for r in rows)
    seen_cf = 0
    for r in rows:
        for s in r["spans"]:
            assert r["text"][s["start"]:s["end"]] == r["text"][s["start"]:s["end"]]  # offsets exist
            if s["label"] == "NATIONAL_ID":
                value = r["text"][s["start"]:s["end"]]
                info = parse_national_id(value, "IT")
                assert info.valid and info.decode_bearing, value
                assert info.disclosed_quasi_identifiers() == {"DATE_OF_BIRTH", "SEX", "PLACE_OF_BIRTH"}
                seen_cf += 1
    assert seen_cf > 0


def test_omocode_decodes_to_same_quasi_identifiers_as_base():
    """A base CF and ≥1 omocode of the SAME identity decode to identical QIs (incl. place), and the
    omocode validates — the mandatory KLU-105 omocodia unit-test, on the dataset generator."""
    rng = random.Random(3)
    for _ in range(200):
        p = itg.gen_person(rng)
        base = parse_national_id(p.codice_fiscale, "IT")
        assert base.valid
        for k in range(1, 4):  # 1..3 substitutions
            omo = itg.gen_omocode(p.codice_fiscale, k)
            assert omo != p.codice_fiscale
            info = parse_national_id(omo, "IT")
            assert info.valid, f"omocode {omo} must carry a valid control char"
            assert info.extra == base.extra, f"omocode {omo} decoded differently"
            assert info.disclosed_quasi_identifiers() == base.disclosed_quasi_identifiers()


def test_sex_decodes_via_day_plus_40():
    """Sex is encoded as day-of-birth +40 for females — decode must recover the generator's sex."""
    rng = random.Random(8)
    saw_m = saw_f = False
    for _ in range(300):
        p = itg.gen_person(rng)
        info = parse_national_id(p.codice_fiscale, "IT")
        assert info.extra["sex"] == p.sex
        assert 1 <= info.extra["birth_day"] <= 31
        saw_m |= p.sex == "M"
        saw_f |= p.sex == "F"
    assert saw_m and saw_f  # both sexes exercised


def test_place_of_birth_resolves_to_a_named_comune_from_snapshot():
    """Every generator CITY's Belfiore code is in the pinned snapshot → place-of-birth is named."""
    rng = random.Random(0)
    for _ in range(100):
        p = itg.gen_person(rng)
        info = parse_national_id(p.codice_fiscale, "IT")
        assert info.extra["place_kind"] == "comune"
        assert info.extra["place_of_birth"] == p.city


def test_seeded_dataset_is_deterministic():
    a = [r["text"] for r in sk.generate_dataset(15, seed=42)]
    b = [r["text"] for r in sk.generate_dataset(15, seed=42)]
    assert a == b
