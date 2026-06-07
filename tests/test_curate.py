"""Unit tests for AI4Privacy → KP and TAB → KP curation mappings (no network)."""

from collections import Counter

import pytest

from klusai.privacy.datasets.data.curate import (
    map_ai4privacy_row,
    map_tab_document,
    pick_tab_annotator,
)


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


# --- RES-89: TAB (Text Anonymization Benchmark) → KP -------------------------------------------
def _tab_mention(et, s, e, idt, eid, span_text):
    return {
        "entity_type": et, "start_offset": s, "end_offset": e,
        "identifier_type": idt, "entity_id": eid, "span_text": span_text,
    }


def test_tab_maps_entity_types_and_preserves_identifier_type_and_coref():
    # "Mr Galip Yalman" (PERSON/DIRECT), "36110/97" (CODE/QUASI), "Ankara" (LOC/NO_MASK → dropped)
    text = "Mr Galip Yalman in 36110/97 at Ankara"
    doc = {
        "text": text,
        "doc_id": "d1",
        "quality_checked": ["annotator1"],
        "annotations": {"annotator1": {"entity_mentions": [
            _tab_mention("PERSON", 0, 15, "DIRECT", "e1", "Mr Galip Yalman"),
            _tab_mention("CODE", 19, 27, "QUASI", "e2", "36110/97"),
            _tab_mention("LOC", 31, 37, "NO_MASK", "e3", "Ankara"),
        ]}},
    }
    dropped: Counter = Counter()
    row = map_tab_document(doc, dropped=dropped)
    assert row["doc_id"] == "d1" and row["annotator"] == "annotator1"
    # NO_MASK LOC dropped (not a detection target); the other two mapped + preserved.
    assert [(s["label"], s["identifier_type"], s["entity_id"]) for s in row["spans"]] == [
        ("PERSON", "DIRECT", "e1"),
        ("CASE_NUMBER", "QUASI", "e2"),
    ]


def test_tab_unmapped_entity_types_dropped_and_counted():
    text = "the Turkish doctor-patient relationship spans 229 sq. m"
    doc = {
        "text": text,
        "doc_id": "d2",
        "quality_checked": [],
        "annotations": {"annotator1": {"entity_mentions": [
            _tab_mention("DEM", 4, 11, "QUASI", "e1", "Turkish"),
            _tab_mention("MISC", 12, 39, "QUASI", "e2", "doctor-patient relationship"),
            _tab_mention("QUANTITY", 46, 55, "QUASI", "e3", "229 sq. m"),
        ]}},
    }
    dropped: Counter = Counter()
    row = map_tab_document(doc, dropped=dropped)
    assert row["spans"] == []  # none have a clean KP type
    assert dropped == Counter({"DEM": 1, "MISC": 1, "QUANTITY": 1})


def test_tab_nested_spans_resolved_longest_wins():
    # ORG "Church of Sweden" nested in a longer ORG parenthetical → keep the outer, drop the inner.
    text = "the Katowice Regional Court (Sad Wojewodzki) ruled"
    doc = {
        "text": text,
        "doc_id": "d3",
        "quality_checked": ["annotator1"],
        "annotations": {"annotator1": {"entity_mentions": [
            _tab_mention("ORG", 4, 27, "QUASI", "e1", "Katowice Regional Court"),
            _tab_mention("ORG", 4, 44, "QUASI", "e1", "Katowice Regional Court (Sad Wojewodzki)"),
        ]}},
    }
    row = map_tab_document(doc)
    assert len(row["spans"]) == 1
    assert (row["spans"][0]["start"], row["spans"][0]["end"]) == (4, 44)  # outermost kept


def test_tab_picks_first_quality_checked_annotator():
    doc = {
        "doc_id": "d4",
        "quality_checked": ["annotator3", "annotator1"],
        "annotations": {
            "annotator1": {"entity_mentions": []},
            "annotator3": {"entity_mentions": []},
        },
    }
    assert pick_tab_annotator(doc) == "annotator3"


def test_tab_falls_back_to_first_annotator_when_none_quality_checked():
    doc = {
        "doc_id": "d5",
        "quality_checked": [],
        "annotations": {"annotator2": {"entity_mentions": []}, "annotator1": {"entity_mentions": []}},
    }
    assert pick_tab_annotator(doc) == "annotator1"


def test_tab_subtoken_collision_raises_not_silently_misaligned():
    # Two char-disjoint CASE_NUMBERs inside ONE whitespace token "14553-14554/89" → whitespace
    # BIOES can't represent it. Must RAISE (caller drops+counts) rather than emit misaligned gold.
    text = "nos. 14553-14554/89 lodged"
    doc = {
        "text": text,
        "doc_id": "d6",
        "quality_checked": ["annotator1"],
        "annotations": {"annotator1": {"entity_mentions": [
            _tab_mention("CODE", 5, 10, "DIRECT", "e1", "14553"),
            _tab_mention("CODE", 11, 19, "DIRECT", "e2", "14554/89"),
        ]}},
    }
    with pytest.raises(ValueError):
        map_tab_document(doc)
