"""Whole-tranche invariants: real artifacts, independently recounted lengths and IDs."""

from __future__ import annotations

import json
from collections import Counter

import pytest

from europriv_bench.national_id import REGISTRY
from klusai.privacy.datasets.data.en_generators import card_valid, nino_format_valid
from klusai.privacy.datasets.data.gateway_authoring import (
    COUNTRIES,
    ROOT,
    allocation,
    attach_provenance,
    get_tokenizer,
    splice,
)
from klusai.privacy.datasets.data.gateway_traffic import (
    FEATURES,
    LANGUAGES,
    coverage_report,
    file_digest,
    load_manifest,
    validate_collection,
)

ARTIFACTS = ROOT / "artifacts/gateway-traffic-v1/originals"


@pytest.fixture(scope="module")
def drafts():
    paths = [ARTIFACTS / f"{split}.jsonl" for split in ("test", "dev")]
    if not all(p.exists() for p in paths):
        pytest.skip("local authoring artifacts not materialized")
    return [(p, json.loads(line)) for p in paths for line in p.read_text().splitlines()]


@pytest.fixture(scope="module")
def rows(drafts):
    hashes = {p: file_digest(p) for p, _ in drafts}
    return [attach_provenance(d, p, "a" * 40, hashes[p]) for p, d in drafts]


def test_splice_unicode_repetition_and_alias_identity():
    msg, spans = splice("ș🙂 [[0.name]] / [[0.alias]] / [[0.name]]", [{"name": "Éva Mare", "alias": "Éva"}], 0, "s")
    assert len({s["entity_id"] for s in spans}) == 1
    assert [msg["parts"][0]["text"][s["start"] : s["end"]] for s in spans] == ["Éva Mare", "Éva", "Éva Mare"]


def test_allocations_exact_and_workflows_present():
    for split, n in (("test", 280), ("dev", 60)):
        plan = allocation(n, split)
        assert Counter(s for s, _ in plan) == dict(negative=n // 5, small=n * 2 // 5, medium=n * 3 // 10, dense=n // 10)
        assert Counter(s for _, s in plan) == dict(short=n // 2, medium=n * 7 // 20, long=n * 3 // 20)
    with pytest.raises(ValueError):
        allocation(50, "dev")


def test_tranche_schema_ledger_and_coverage(rows):
    manifest = load_manifest(ROOT / "conf/gateway_traffic_manifest.yaml")
    plan = json.loads((ROOT / manifest["split_plan"]["path"]).read_text())
    validate_collection(rows, manifest, plan, {})
    # Assess exact tranche ratios without changing the frozen release targets on disk.
    report = coverage_report(rows, manifest | {"targets": {"test": 280, "dev": 60}})
    assert report["errors"] == [
        f"{lang}: fewer than 100 native double-reviewed/adjudicated conversations" for lang in LANGUAGES
    ]
    assert all(not r.provenance.review.native_reviewers for r in rows)
    for cell in report["cells"].values():
        assert set(cell["features"]) == set(FEATURES)


def test_real_token_counts_offsets_and_uniqueness(rows):
    tokenizer = get_tokenizer()
    seen = set()
    for row in rows:
        # Recount via batch encoder, independent of author's count_tokens wrapper.
        parts = [p.text for m in row.messages for p in m.parts]
        encodings = tokenizer.encode_batch(parts, add_special_tokens=False)
        assert sum(len(e.ids) for e in encodings) == row.token_count
        assert 32 <= row.token_count <= 2048
        full = "\n".join(parts)
        assert full not in seen
        seen.add(full)
        for s in row.spans:
            assert row.messages[s.message].parts[s.part].text[s.start : s.end] == s.text


def test_ids_decode_dob_card_and_cross_split_values(rows):
    identifiers = {}
    for row in rows:
        dob = {s.subject_id: s.text for s in row.spans if s.label == "DATE"}
        for span in row.spans:
            if span.label == "NATIONAL_ID":
                if row.language == "en" and not span.entity_id.endswith("cross-border"):
                    assert nino_format_valid(span.text)
                    country = "GB"
                else:
                    country = "RO" if row.language == "en" else COUNTRIES[row.language]
                    info = REGISTRY[country].parse(span.text)
                    assert info.valid
                    if info.extra.get("birth_date") and span.subject_id in dob:
                        assert info.extra["birth_date"] == dob[span.subject_id]
                key = (country, span.text)
                assert identifiers.setdefault(key, row.split) == row.split
            if span.entity_id.endswith("/card"):
                assert card_valid(span.text)


def test_source_commit_and_artifact_hash_when_finalized():
    import subprocess

    for split in ("test", "dev"):
        path = ROOT / "artifacts/gateway-traffic-v1" / f"{split}.jsonl"
        if not path.exists():
            continue
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        provenance = rows[0]["provenance"]
        artifact = ROOT / provenance["artifact_path"]
        assert file_digest(artifact) == provenance["file_sha256"]
        committed = subprocess.check_output(
            ["git", "show", f"{provenance['source_revision']}:{provenance['artifact_path']}"], cwd=ROOT
        )
        assert committed == artifact.read_bytes()
        assert all(r["provenance"]["source_revision"] == provenance["source_revision"] for r in rows)


def test_email_subject_ownership_and_partial_dates(rows):
    import re

    from klusai.privacy.datasets.data.gateway_authoring import EXTRA

    for row in rows:
        text = row.messages[0].parts[0].text
        primary = row.id + "/subject/0"
        for s in row.spans:
            if s.label == "EMAIL" and "[at]" not in s.text:
                assert re.fullmatch(r"[a-z0-9.]+@example\.invalid", s.text)
            if s.label not in {"PERSON"}:
                assert s.subject_id == primary
        national = next((s for s in row.spans if s.label == "NATIONAL_ID"), None)
        dob = next((s for s in row.spans if s.label == "DATE"), None)
        if national and dob and row.language in {"it", "fr"}:
            info = REGISTRY[row.language.upper()].parse(national.text)
            if row.language == "fr":
                assert dob.text == f"{info.extra['birth_month']:02d}/{info.extra['birth_year_2digit']}"
            else:
                assert (
                    dob.text
                    == f"{info.extra['birth_day']:02d}/{info.extra['birth_month']:02d}/{info.extra['birth_year_2digit']}"
                )
        names = {s.entity_id: s.text for s in reversed(row.spans) if s.label == "PERSON"}
        assert len(names) == len(set(names.values()))
        if row.token_count > 128 and row.subject_ids:
            assert EXTRA[row.language][0] in text


def test_frozen_self_review_sample_matches_artifacts(drafts):
    from scripts.review_gateway_traffic import flatten, sample

    directory = ROOT / "docs/gateway-authoring/review"
    if not directory.exists():
        pytest.skip("review not materialized")
    frozen = json.loads((directory / "sample.json").read_text())
    assert sample([d for _, d in drafts]) == frozen
    assert len({r["id"] for r in frozen}) == 300
    judgments = json.loads((directory / "judgments.json").read_text())
    for _, draft in drafts:
        if draft["id"] in judgments:
            row = flatten(draft)
            assert judgments[draft["id"]]["text_sha256"] == row["sha256"]
            assert judgments[draft["id"]]["review_mode"] == "gold-aware author self-review"
