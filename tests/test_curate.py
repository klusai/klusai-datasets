"""Unit tests for AI4Privacy → KP curation mapping (no network)."""

from collections import Counter

import pytest

from klusai.privacy.datasets.data.curate import map_ai4privacy_row


def test_maps_native_labels_to_kp_and_drops_unmapped():
    text = "Email harry@hogwarts.edu about GIVEN matters"
    mask = [
        {"label": "EMAIL", "start": 6, "end": 24},        # → EMAIL
        {"label": "OBSCURE_LABEL", "start": 31, "end": 36},  # unmapped → dropped
    ]
    dropped: Counter = Counter()
    row = map_ai4privacy_row(text, mask, dropped=dropped)
    assert row["text"] == text
    assert row["spans"] == [{"start": 6, "end": 24, "label": "EMAIL"}]
    assert dropped["OBSCURE_LABEL"] == 1


def test_person_native_labels_collapse_to_person():
    text = "Ion Popescu"
    mask = [
        {"label": "GIVENNAME", "start": 0, "end": 3},
        {"label": "SURNAME", "start": 4, "end": 11},
    ]
    row = map_ai4privacy_row(text, mask)
    assert {s["label"] for s in row["spans"]} == {"PERSON"}


def test_misaligned_span_raises():
    with pytest.raises(ValueError):
        map_ai4privacy_row("a b", [{"label": "EMAIL", "start": 50, "end": 60}])


def test_openpii_demographic_labels_dropped_not_inflated():
    """RES-93: openpii-1m's TITLE/AGE/GENDER/SEX have no clean KP entity → dropped + counted.

    These four are the only native labels in the openpii-1m 19-class set with no KP mapping. We
    keep native->KP a function (no demographic-attribute KP type, which would change the BIOES
    label space) and record them as dropped rather than forcing a lossy mapping that inflates a
    core type. This pins that decision.
    """
    text = "Dr Smith is 40"
    mask = [
        {"label": "TITLE", "start": 0, "end": 2},    # unmapped
        {"label": "SURNAME", "start": 3, "end": 8},   # → PERSON
        {"label": "AGE", "start": 12, "end": 14},     # unmapped
    ]
    dropped: Counter = Counter()
    row = map_ai4privacy_row(text, mask, dropped=dropped)
    assert row["spans"] == [{"start": 3, "end": 8, "label": "PERSON"}]
    assert dropped["TITLE"] == 1 and dropped["AGE"] == 1
