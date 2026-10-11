"""TRAIN census plus contamination, resume and model-export regression gates."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from klusai.privacy.datasets.data.gateway_traffic import file_digest, load_manifest
from klusai.privacy.datasets.data.gateway_train import ROOT, identity_values, training_row
from klusai.privacy.datasets.data.gateway_train_audit import SimilarityIndex, jaccard, shingles, skeleton
from scripts.audit_gateway_train import audit
from scripts.author_gateway_train import write_verified

TRAIN_EXTENSION = load_manifest(ROOT / "conf/gateway_traffic_manifest.yaml")["train_extension"]
LOCAL_ARTIFACTS = {name for name in TRAIN_EXTENSION["artifacts"] if name.startswith("artifacts/")}
PINNED_FILES = TRAIN_EXTENSION["artifacts"] | {
    entry["path"]: entry["sha256"] for entry in TRAIN_EXTENSION["frozen_heldout"].values()
}


@pytest.mark.parametrize("name,sha", [pytest.param(name, sha, id=name) for name, sha in PINNED_FILES.items()])
def test_train_file_digest_when_present(name, sha):
    path = ROOT / name
    if name in LOCAL_ARTIFACTS and not path.exists():
        pytest.skip(f"local TRAIN artifact not materialized: {name}")
    assert file_digest(path) == sha, f"Pinned TRAIN input changed: {name}"


def test_full_train_census_and_zero_cross_split_overlap(request):
    missing = sorted(name for name in LOCAL_ARTIFACTS if not (ROOT / name).exists())
    if missing:
        pytest.skip(f"full TRAIN census requires local artifacts: {', '.join(missing)}")
    request.getfixturevalue("gateway_tokenizer")
    receipt = audit()
    committed = json.loads((ROOT / "docs/gateway-authoring/train-audit.json").read_text())
    assert receipt == committed
    assert receipt["status"] == "pass"
    assert receipt["train_rows"] == 40000 and receipt["heldout_rows"] == 9600
    assert not any(receipt["overlap"].values())


def test_near_duplicate_detection_cannot_be_evaded_by_names_or_digits():
    text = "Please organise the following witness information into a chronology of the bicycle accident. "
    text += (
        "Keep each statement separate and list any disagreements without assigning responsibility. Contact Alice 123."
    )
    start = text.index("Alice")
    first = dict(text=text, spans=[dict(start=start, end=start + 5, label="PERSON")])
    changed = dict(
        text=text.replace("Alice 123", "Beatriz 999"), spans=[dict(start=start, end=start + 7, label="PERSON")]
    )
    original = shingles(skeleton(first), masked=True)
    renamed = shingles(skeleton(changed), masked=True)
    assert original == renamed
    assert SimilarityIndex([original]).query(renamed)["matches"] == [(0, 1.0)]
    # Ordinary text edits above the threshold also produce a match.
    edited = shingles(text.replace("organise", "arrange"))
    assert SimilarityIndex([shingles(text)]).query(edited)["matches"]


def test_exact_join_covers_minhash_misses_and_agrees_with_brute_force():
    rng = random.Random(127)
    documents = [frozenset(rng.sample(range(80), rng.randint(10, 35))) for _ in range(30)]
    documents = [frozenset(map(str, d)) for d in documents]
    index = SimilarityIndex(documents)
    index.lsh.clear()  # Force every LSH candidate to be missed: certification must still work.
    queries = [d - set(list(sorted(d))[:2]) for d in documents] + [frozenset({"unseen"})]
    for query in queries:
        actual = {i for i, _ in index.query(query)["matches"]}
        expected = {i for i, doc in enumerate(index.documents) if jaccard(query, doc) >= 0.8}
        assert actual == expected
    with pytest.raises(ValueError, match="empty"):
        SimilarityIndex([])


def test_subject_value_audit_ignores_renamed_identity_ids():
    held = [dict(spans=[dict(label="PERSON", text="Ana Pop", subject_id="test/a")])]
    train = [dict(spans=[dict(label="PERSON", text="ANA  POP", subject_id="train/new")])]
    assert identity_values(held)["PERSON"] & identity_values(train)["PERSON"]


def test_model_export_rebases_tool_and_multiple_part_offsets():
    row = dict(
        language="ro",
        messages=[dict(parts=[dict(text="Salut Ana"), dict(text="42")]), dict(parts=[dict(text="Ana revine")])],
        spans=[
            dict(message=0, part=0, start=6, end=9, label="PERSON"),
            dict(message=1, part=0, start=0, end=3, label="PERSON"),
        ],
    )
    result = training_row(row)
    assert result["text"] == "Salut Ana\n\n42\n\nAna revine"
    assert [result["text"][s["start"] : s["end"]] for s in result["spans"]] == ["Ana", "Ana"]
    assert result["spans"][1]["start"] == 15


def test_resume_partial_prefix_and_refuse_corruption(tmp_path: Path):
    path = tmp_path / "rows.jsonl"
    rows = [dict(i=i) for i in range(10)]
    write_verified(path, rows[:3], False)
    write_verified(path, rows, True)
    write_verified(path, rows, True)
    assert [json.loads(line) for line in path.read_text().splitlines()] == rows
    with pytest.raises(ValueError, match="Existing artifact"):
        write_verified(path, rows, False)
    with pytest.raises(ValueError, match="Excess"):
        write_verified(path, rows[:2], True)
    with pytest.raises(ValueError, match="mismatch"):
        write_verified(path, [dict(i=100)], True)
    path.write_text('{"i":0}')
    with pytest.raises(ValueError, match="mismatch"):
        write_verified(path, rows, True)
