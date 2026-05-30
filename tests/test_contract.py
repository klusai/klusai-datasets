"""Contract tests: this repo must share europriv_bench's taxonomy + span alignment.

These fail loudly if the shared dependency isn't installed or if label spaces drift — the
guarantee that dataset gold labels, model label maps, and benchmark scores use one identical
BIOES space.
"""

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from europriv_bench.taxonomy import ENTITY_NAMES, bioes_labels


def test_shared_taxonomy_is_importable():
    assert "PERSON" in ENTITY_NAMES
    assert "S-PERSON" in bioes_labels()


def test_gold_spans_produce_labels_in_the_shared_space():
    # A dataset producing KP-labeled spans must yield tags that live in the benchmark's label space.
    tags = char_spans_to_bioes("Ion Popescu", [Span(0, 11, "PERSON")])
    validate_bioes(tags)
    assert set(tags) <= set(bioes_labels())
