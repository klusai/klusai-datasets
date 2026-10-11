"""Contract fixtures only; no gateway dataset generation (RES-124)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from pydantic import ValidationError

from europriv_bench.taxonomy import ENTITY_NAMES, TAXONOMY_VERSION
from klusai.privacy.datasets.data.gateway_traffic import (
    FEATURES,
    LANGUAGES,
    Conversation,
    audit_training,
    coverage_report,
    digest,
    extend_ledger,
    file_digest,
    load_manifest,
    text_digest,
    validate_collection,
)
from scripts.audit_gateway_traffic import main

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "conf/gateway_traffic_manifest.yaml"
HASH = "a" * 64
REV = "a" * 40


def row(**changes):
    messages = [{"role": "user", "parts": [{"type": "text", "text": "Ana știe."}]}]
    data = dict(
        schema_version="gateway-traffic-v1",
        config_status="dev",
        taxonomy_version=TAXONOMY_VERSION,
        id="fixture/one",
        language="ro",
        secondary_languages=[],
        source_id="originals",
        stratum="original-synthetic",
        scenario_id="fixture/scenario-1",
        family_id="gateway-v1/family-002",
        source_document_id="fixture/document-1",
        translation_group_id="fixture/translation-1",
        subject_ids=["fixture/subject-1"],
        split="test",
        messages=messages,
        spans=[
            dict(
                message=0,
                part=0,
                start=0,
                end=3,
                text="Ana",
                label="PERSON",
                entity_id="fixture/entity-1",
                subject_id="fixture/subject-1",
                identifier_class="DIRECT",
                protection="pseudonymize",
            )
        ],
        features=[],
        dense_document=False,
        token_count=32,
        tokenizer_id="fixture-tokenizer",
        tokenizer_revision=REV,
        truncated=False,
        provenance=dict(
            source_revision=REV,
            source_split="authored",
            source_record_id="fixture/source-1",
            artifact_path="fixtures/source.json",
            file_sha256=HASH,
            author="test",
            tool="pytest",
            session="fixture",
            generator_version="fixture-v1",
            prompt_sha256=HASH,
            content_sha256=digest(messages),
            seed=123,
            identity_provenance="fictional test fixture",
            exclusions=[],
            review=dict(annotators=["fixture-author"], native_reviewers=[], adjudicator=None, guide_sha256=HASH),
        ),
    )
    data.update(changes)
    return Conversation.model_validate(data)


def spec_plan():
    spec = load_manifest(MANIFEST)
    return spec, json.loads((ROOT / spec["split_plan"]["path"]).read_text())


def test_manifest_schema_and_frozen_targets():
    spec, plan = spec_plan()
    assert sum(spec["targets"].values()) * len(LANGUAGES) == 9600
    assert len(plan["families"]) == 24
    assert set(f["split"] for f in plan["families"]) == {"train", "dev", "test"}
    assert set(spec["required_labels"]) <= set(ENTITY_NAMES)
    assert json.loads((ROOT / "conf/gateway_traffic.schema.json").read_text()) == Conversation.model_json_schema()
    assert spec["sources"]["tab"]["allowed_gateway_splits"] == []
    assert spec["sources"]["originals"]["license"] == "CC-BY-4.0"
    # An altered v1 assignment requires a new dataset version, not a rewritten digest.
    assert spec["split_plan"]["sha256"] == "f8004ecd49fea70fb71dee5e233dad8b51044deeac1bc8a790cd2828fb1677ff"


@pytest.mark.parametrize(
    "field,value",
    [
        ("language", "cs"),
        ("config_status", "real-gold"),
        ("token_count", 2049),
        ("token_count", 31),
        ("token_count", "32"),
        ("truncated", True),
        ("messages", []),
        ("subject_ids", []),
        ("features", ["imaginary"]),
        ("secondary_languages", ["en"]),
    ],
)
def test_schema_rejects_invalid_contract(field, value):
    with pytest.raises(ValidationError):
        row(**{field: value})


@pytest.mark.parametrize(
    "change",
    [
        {"end": 99},
        {"start": 2, "end": 1},
        {"message": 3},
        {"part": 1},
        {"text": "Bob"},
        {"label": "NOT_KP"},
        {"start": -1},
        {"identifier_class": "NO_MASK"},
    ],
)
def test_invalid_spans_rejected(change):
    spans = row().model_dump()["spans"]
    spans[0].update(change)
    with pytest.raises(ValidationError):
        row(spans=spans)


def test_unicode_offsets_parts_repetition_and_coreference():
    data = row().model_dump()
    data["messages"][0]["parts"].append({"type": "text", "text": "Și Ana."})
    span = dict(data["spans"][0], part=1, start=3, end=6)
    data["spans"].append(span)
    data["provenance"]["content_sha256"] = digest(data["messages"])
    valid = Conversation.model_validate(data)
    assert len(valid.spans) == 2
    data["spans"][1]["label"] = "ADDRESS"
    with pytest.raises(ValidationError, match="coreference"):
        Conversation.model_validate(data)


def test_overlaps_and_content_tampering_rejected():
    data = row().model_dump()
    data["spans"].append(data["spans"][0])
    with pytest.raises(ValidationError, match="overlapping"):
        Conversation.model_validate(data)
    data = row().model_dump()
    data["messages"][0]["parts"][0]["text"] += "x"
    with pytest.raises(ValidationError, match="content hash"):
        Conversation.model_validate(data)


@pytest.mark.parametrize(
    "kind,key",
    [
        ("family", "gateway-v1/family-002"),
        ("subject", "fixture/subject-1"),
        ("document", "originals:fixture/document-1"),
        ("translation", "fixture/translation-1"),
        ("scenario", "fixture/scenario-1"),
        ("conversation", "fixture/one"),
        ("text", text_digest("Ana știe.")),
    ],
)
def test_every_identity_kind_blocks_split_leakage(kind, key):
    original = {f"{kind}:{key}": "train"}
    before = dict(original)
    with pytest.raises(ValueError, match="cross-split"):
        extend_ledger(original, [row()])
    assert original == before


def test_transitive_bridge_is_rejected_without_reassigning_history():
    ledger = {"subject:fixture/subject-1": "test", "translation:fixture/translation-1": "dev"}
    with pytest.raises(ValueError, match="cross-split"):
        extend_ledger(ledger, [row()])
    assert ledger["translation:fixture/translation-1"] == "dev"


def test_ledger_is_stable_and_allows_same_split_siblings():
    first = extend_ledger({}, [row()])
    assert extend_ledger(first, [row()]) == first
    sibling = row(id="fixture/sibling")
    assert extend_ledger({}, [row(), sibling]) == extend_ledger({}, [sibling, row()])


def test_sources_reservations_and_duplicate_ids():
    spec, plan = spec_plan()
    validate_collection([row()], spec, plan, {})
    for bad in [
        row(source_id="tab"),
        row(source_id="unknown"),
        row(family_id="unreserved"),
        row(split="dev"),
        row(stratum="external-synthetic"),
    ]:
        with pytest.raises(ValueError):
            validate_collection([bad], spec, plan, {})
    with pytest.raises(ValueError, match="duplicate"):
        validate_collection([row(), row()], spec, plan, {})
    with pytest.raises(ValueError, match="contradicts"):
        validate_collection([], spec, plan, {"family:gateway-v1/family-002": "train"})


def test_external_revision_pinned():
    spec, plan = spec_plan()
    with pytest.raises(ValueError, match="revision"):
        validate_collection([row(source_id="openpii", stratum="external-synthetic")], spec, plan, {})


def test_reserved_family_capacity_is_enforced():
    spec, plan = spec_plan()
    with pytest.raises(ValueError, match="capacity"):
        validate_collection([row(id=f"fixture/{i}") for i in range(126)], spec, plan, {})


def test_translation_and_subject_siblings_cannot_cross_language_splits():
    ledger = extend_ledger({}, [row()])
    sibling = row(id="translated", language="en", split="dev", family_id="gateway-v1/family-001")
    with pytest.raises(ValueError, match="cross-split"):
        extend_ledger(ledger, [sibling])


def test_empty_coverage_reports_all_languages_and_external_cannot_fill_original_quota():
    spec, _ = spec_plan()
    report = coverage_report([], spec)
    assert report["status"] == "incomplete"
    assert len(report["cells"]) == 16
    assert {k.split("/")[1] for k in report["cells"]} == set(LANGUAGES)
    external = coverage_report([row(stratum="external-synthetic", source_id="openpii")], spec)
    assert external["cells"] == report["cells"]


def test_coverage_counts_boundaries_mix_and_native_review():
    spec, _ = spec_plan()
    rows = []
    for i, (tokens, subjects, dense) in enumerate([(128, 0, False), (129, 1, False), (512, 3, False), (513, 6, True)]):
        data = row(id=f"fixture/{i}", token_count=tokens).model_dump()
        text = " ".join(f"P{x}" for x in range(subjects)) or "Public text."
        data["messages"][0]["parts"][0]["text"] = text
        data["spans"] = [
            dict(data["spans"][0], start=x * 3, end=x * 3 + 2, text=f"P{x}", subject_id=f"s{x}", entity_id=f"e{x}")
            for x in range(subjects)
        ]
        data["subject_ids"] = [f"s{x}" for x in range(subjects)]
        data["dense_document"] = dense
        data["provenance"]["content_sha256"] = digest(data["messages"])
        data["provenance"]["review"].update(annotators=["r1", "r2"], native_reviewers=["r1", "r2"], adjudicator="r3")
        rows.append(Conversation.model_validate(data))
    report = coverage_report(rows, spec)
    cell = report["cells"]["test/ro"]
    assert cell["mix"] == dict(negative=1, small=1, medium=1, dense=1)
    assert cell["lengths"] == dict(short=1, medium=2, long=1)
    assert cell["native_double_reviewed"] == 4
    assert all(any(f"missing feature {f}" in e for e in report["errors"]) for f in FEATURES)


@pytest.mark.parametrize("reviewers", [["same", "same"], ["unknown"]])
def test_review_cannot_fake_double_annotation(reviewers):
    data = row().model_dump()
    data["provenance"]["review"]["native_reviewers"] = reviewers
    with pytest.raises(ValidationError):
        Conversation.model_validate(data)


def inventory_fixture(tmp_path):
    path = tmp_path / "train.jsonl"
    path.write_text(json.dumps({"text": " ANA   ȘTIE. "}) + "\n")
    inventory = {
        "scope": "unit test",
        "corpora": [{"id": "train-fixture", "file_sha256": file_digest(path), "rows": 1}],
    }
    return inventory, {"train-fixture": path}


def test_training_audit_detects_normalized_overlap_and_no_false_clean_for_empty(tmp_path):
    inventory, paths = inventory_fixture(tmp_path)
    assert audit_training([row()], inventory, paths)["status"] == "overlap"
    assert audit_training([], inventory, paths)["status"] == "pending_generation"
    report = audit_training([row(split="train")], inventory, paths)
    assert report["hits"] == []
    assert "unverified" in report["semantic_disjointness"]


def test_training_audit_requires_every_corpus_and_matching_bytes_counts(tmp_path):
    inventory, paths = inventory_fixture(tmp_path)
    with pytest.raises(ValueError, match="paths mismatch"):
        audit_training([], inventory, {})
    paths["train-fixture"].write_text('{"text":"changed"}\n')
    with pytest.raises(ValueError, match="hash mismatch"):
        audit_training([], inventory, paths)
    inventory["corpora"][0]["file_sha256"] = file_digest(paths["train-fixture"])
    inventory["corpora"][0]["rows"] = 2
    with pytest.raises(ValueError, match="count mismatch"):
        audit_training([], inventory, paths)


def test_parquet_audit_uses_local_file(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = tmp_path / "train.parquet"
    pq.write_table(pa.Table.from_pylist([{"text": "Ana știe."}]), path)
    inventory = {"scope": "fixture", "corpora": [{"id": "parquet", "file_sha256": file_digest(path), "rows": 1}]}
    assert audit_training([row()], inventory, {"parquet": path})["status"] == "overlap"


@pytest.mark.parametrize("mutation", ["license", "rights", "revision", "evidence", "plan", "inventory"])
def test_manifest_fails_closed_on_bad_source_or_changed_frozen_input(tmp_path, mutation):
    import shutil

    shutil.copytree(ROOT / "conf", tmp_path / "conf")
    path = tmp_path / "conf/gateway_traffic_manifest.yaml"
    spec = yaml.safe_load(path.read_text())
    source = spec["sources"]["openpii"]
    if mutation == "license":
        source["license"] = "CC-BY-NC-ND-4.0"
    elif mutation == "rights":
        source["permitted_train"] = False
    elif mutation == "revision":
        source["revision"] = "main"
    elif mutation == "evidence":
        source["license_sha256"] = "0" * 64
    else:
        key = "split_plan" if mutation == "plan" else "training_inventory"
        spec[key]["sha256"] = "0" * 64
    path.write_text(yaml.safe_dump(spec))
    with pytest.raises(ValueError):
        load_manifest(path)


def test_cli_rejects_partial_training_map(tmp_path):
    paths = tmp_path / "paths.json"
    paths.write_text("{}")
    result = CliRunner().invoke(
        main, ["--manifest", str(MANIFEST), "--training-paths", str(paths), "--output", str(tmp_path / "audit.json")]
    )
    assert result.exit_code != 0
    assert "paths mismatch" in result.output
    assert not (tmp_path / "audit.json").exists()


def test_cli_rejects_tampered_prior_ledger(tmp_path):
    paths = tmp_path / "paths.json"
    paths.write_text("{}")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"ledger": {}, "ledger_sha256": HASH}))
    result = CliRunner().invoke(
        main,
        [
            "--manifest",
            str(MANIFEST),
            "--training-paths",
            str(paths),
            "--prior-ledger",
            str(receipt),
            "--output",
            str(tmp_path / "out.json"),
        ],
    )
    assert result.exit_code != 0
    assert "prior ledger hash" in result.output
