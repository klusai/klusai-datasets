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
