"""T1 LocalePack acceptance (KLU-102): the 5 packs are registered, on the shared interface, with the
label space == bioes_labels() contract and the contamination pre-declaration in place.

Per-pack checksum self-test / byte-equality / strict-BIOES / determinism / NATIONAL_ID coverage are
exercised generically by ``test_localepack.py`` (which parametrizes over every registered pack); this
suite adds the T1-specific acceptance the issue calls out.
"""

from pathlib import Path

import yaml

from europriv_bench.spans import Span, char_spans_to_bioes
from europriv_bench.taxonomy import bioes_labels
from klusai.privacy.datasets.data import LOCALE_PACKS

T1_LOCALES = ["it", "de", "fr", "es", "nl"]


def test_all_five_t1_packs_registered():
    for loc in T1_LOCALES:
        assert loc in LOCALE_PACKS, f"T1 pack {loc!r} not registered"
        assert LOCALE_PACKS[loc].language == loc


def test_it_pack_lands_first_with_decode_bearing_codice_fiscale():
    """IT is the critical-path pack: it must declare codice fiscale as a checksummed id."""
    it = LOCALE_PACKS["it"]
    names = {c.name for c in it.checksummed_ids}
    assert "codice fiscale" in names


def test_t1_pack_label_space_is_within_bioes_labels():
    """Contract: every BIOES tag a T1 pack emits lives in the shared benchmark label space."""
    allowed = set(bioes_labels())
    for loc in T1_LOCALES:
        pack = LOCALE_PACKS[loc]
        seen_any = False
        for d in pack.generate_dataset(40, seed=0):
            tags = char_spans_to_bioes(
                d["text"], [Span(s["start"], s["end"], s["label"]) for s in d["spans"]]
            )
            assert set(tags) <= allowed, f"{loc}: tags outside bioes_labels(): {set(tags) - allowed}"
            seen_any = seen_any or any(t != "O" for t in tags)
        assert seen_any, f"{loc}: produced no non-O tags"


def test_t1_packs_checksum_self_test_passes():
    """Bound: each T1 pack's checksummed ids validate (100%) on a fixed sample (KLU-102 stop-gate)."""
    for loc in T1_LOCALES:
        LOCALE_PACKS[loc].checksum_self_test(n=200, seed=0)


def _datasets_conf():
    path = Path(__file__).resolve().parent.parent / "conf" / "datasets.yaml"
    return yaml.safe_load(path.read_text())


def test_contamination_predeclaration_in_config():
    """conf/datasets.yaml must declare every synthetic config as contamination_role=train so KLU-106
    cannot silently score the matching general config as held-out (must be in_distribution)."""
    conf = _datasets_conf()
    synth = {s["name"]: s for s in conf["synthetic"] if "pack" in s}
    # Every T1 config present and pre-declared as train-contaminating.
    for loc in T1_LOCALES:
        name = f"ds-kp-general-{loc}-50k"
        assert name in synth, f"missing synthetic config {name}"
        assert synth[name]["contamination_role"] == "train"
        assert synth[name]["pack"] == loc
