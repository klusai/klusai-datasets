"""Revision identity, whole-corpus invariants, diagnosed regressions and blind handoff."""

from __future__ import annotations

import ast
import contextlib
import csv
import io
import json
from collections import Counter

import pytest

from europriv_bench.national_id import REGISTRY
from klusai.privacy.datasets.data import gateway_authoring_v3 as v3
from klusai.privacy.datasets.data.en_generators import card_valid, nino_format_valid
from klusai.privacy.datasets.data.gateway_traffic import (
    FEATURES,
    LANGUAGES,
    coverage_report,
    digest,
    file_digest,
    load_manifest,
    validate_collection,
)
from scripts.prepare_gateway_r1 import COORDINATOR, PACKET, fresh_sample, previous_rows


@pytest.fixture(scope="module")
def drafts():
    paths = [v3.ARTIFACTS / f"{s}.jsonl" for s in ("test", "dev")]
    return [(p, json.loads(line)) for p in paths for line in p.read_text().splitlines()]


@pytest.fixture(scope="module")
def rows(drafts):
    hashes = {p: file_digest(p) for p in {p for p, _ in drafts}}
    return [v3.attach_provenance(d, p, "a" * 40, hashes[p]) for p, d in drafts]


def test_frozen_ids_subjects_strata_and_quotas(drafts, rows):
    prior = {
        d["id"]: d
        for split in ("test", "dev")
        for line in (v3.ROOT / f"artifacts/gateway-traffic-v1/originals/v2/{split}.jsonl").read_text().splitlines()
        for d in [json.loads(line)]
    }
    assert len(drafts) == len(prior) == 9600
    assert {d["id"] for _, d in drafts} == set(prior)
    frozen = (
        "id",
        "language",
        "split",
        "family_id",
        "scenario_id",
        "translation_group_id",
        "source_document_id",
        "subject_ids",
        "dense_document",
        "intended_mix",
        "intended_length",
    )
    for _, draft in drafts:
        assert {k: draft[k] for k in frozen} == {k: prior[draft["id"]][k] for k in frozen}
    manifest = load_manifest(v3.ROOT / "conf/gateway_traffic_manifest.yaml")
    assert manifest["data_revision"] == 4
    plan = json.loads((v3.ROOT / manifest["split_plan"]["path"]).read_text())
    old = json.loads((v3.ROOT / "docs/gateway-authoring/audit-v2.json").read_text())["ledger"]
    ledger = validate_collection(rows, manifest, plan, old)
    assert all(ledger[k] == v for k, v in old.items())
    report = coverage_report(rows, manifest)
    assert report["errors"] == [
        f"{lang}: fewer than 100 native double-reviewed/adjudicated conversations" for lang in LANGUAGES
    ]
    assert all(set(c["features"]) == set(FEATURES) for c in report["cells"].values())


def test_whole_corpus_offsets_tokens_and_identity_fields(rows, drafts):
    tokenizer = v3.v1.get_tokenizer()
    seen = set()
    identifiers = {}
    for row, (_, draft) in zip(rows, drafts):
        text = row.messages[0].parts[0].text
        assert text not in seen
        seen.add(text)
        count = len(tokenizer.encode(text, add_special_tokens=False).ids)
        assert count == row.token_count
        lo, hi = {"short": (32, 128), "medium": (129, 512), "long": (513, 2048)}[draft["intended_length"]]
        assert lo <= count <= hi
        assert "[[" not in text
        assert {s.subject_id for s in row.spans if s.label == "PERSON"} == set(row.subject_ids)
        dates = {s.subject_id: s.text for s in row.spans if s.label == "DATE"}
        for span in row.spans:
            assert text[span.start : span.end] == span.text
            if span.entity_id.endswith("/card"):
                assert card_valid(span.text)
            if span.label != "NATIONAL_ID":
                continue
            country = v3.v1.COUNTRIES[row.language]
            assert identifiers.setdefault((country, span.text), row.split) == row.split
            if country == "GB":
                assert nino_format_valid(span.text)
                continue
            info = REGISTRY[country].parse(span.text)
            assert info.valid
            dob = dates.get(span.subject_id)
            if not dob:
                continue
            if info.extra.get("birth_date"):
                assert dob == info.extra["birth_date"]
            elif country == "FR":
                assert dob == f"{info.extra['birth_month']:02d}/{info.extra['birth_year_2digit']}"
            elif country == "IT":
                assert (
                    dob
                    == f"{info.extra['birth_day']:02d}/{info.extra['birth_month']:02d}/{info.extra['birth_year_2digit']}"
                )


def test_receipts_supply_comparisons_and_heterogeneous_values(rows):
    lengths = set()
    for row in rows:
        text = row.messages[0].parts[0].text
        if "```csv\n" not in text:
            continue
        parsed = list(csv.reader(io.StringIO(text.split("```csv\n")[1].split("```")[0]), delimiter=";"))
        assert all(len(r) == 10 for r in parsed)
        lengths.add(len(parsed))
        assert len({r[5].split(",")[1] for r in parsed[1:]}) > 1
        assert all(r[8] and r[9] for r in parsed[1:])  # Both sides of the merchant comparison are supplied.
        names = {s.text for s in row.spans if s.label == "PERSON"}
        assert {r[0] for r in parsed[1:]} == names
    assert len(lengths) >= 8  # Receipt sizes cannot collapse into a constant-length fixture.


def test_context_sensitive_identifiers_and_used_queue_secret(rows):
    for row in rows:
        workflow = int(row.id.split("/")[-1].split("-")[0])
        text = row.messages[0].parts[0].text
        if workflow == 3:
            assert not any(s.label == "NATIONAL_ID" for s in row.spans)
        if workflow == 7 and row.subject_ids:
            assert {s.subject_id for s in row.spans if s.label == "CASE_NUMBER"} == set(row.subject_ids)
        if workflow == 5 and row.subject_ids:
            assert {s.subject_id for s in row.spans if s.label == "EMAIL"} == set(row.subject_ids)
        if workflow == 6 and row.split == "dev" and any(s.label == "SECRET" for s in row.spans):
            code = text.split("```python\n")[1].split("```")[0]
            tree = ast.parse(code)
            assert any(
                isinstance(n, ast.Name) and n.id == "TOKEN" and isinstance(n.ctx, ast.Load) for n in ast.walk(tree)
            )


@pytest.mark.parametrize("split", ["test", "dev"])
def test_long_code_reproduction_has_distinct_executable_checks(split):
    code = v3.code_repro(split, 6).split("```python\n")[1].split("```")[0]
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(code, "gateway-repro", "exec"), {})
    lines = output.getvalue().splitlines()
    assert any("check_replay FAIL" in line for line in lines)
    assert any("check_new_event_same_sku OK" in line for line in lines)
    assert len(lines) == (4 if split == "test" else 3)


def test_blind_packet_is_fresh_complete_and_bound_to_sources(drafts):
    sample = fresh_sample([d for _, d in drafts], previous_rows())
    excluded = {(r["family"], r["id"].rsplit("-", 1)[1]) for r in previous_rows()}
    assert len(sample) == len({r["id"] for r in sample}) == 300
    assert all((r["family"], r["id"].rsplit("-", 1)[1]) not in excluded for r in sample)
    assert set(r["language"] for r in sample) == set(LANGUAGES)
    packet = json.loads((PACKET / "sample.json").read_text())
    assert packet == [dict(id=f"G{i + 1:03d}", language=r["language"], text=r["text"]) for i, r in enumerate(sample)]
    assert set(p.name for p in PACKET.iterdir()) == {"sample.json", "rubric.md", "taxonomy.json", "README.md"}
    assert all(set(r) == {"id", "language", "text"} for r in packet)
    manifest = json.loads((COORDINATOR / "sample-manifest.json").read_text())
    assert manifest["status"] == "awaiting_separate_blind_reviewer"
    for name, sha in manifest["reviewer_files"].items():
        assert file_digest(PACKET / name) == sha
    for name, sha in manifest["sources"].items():
        assert file_digest(v3.ROOT / name) == sha
    mapping = json.loads((COORDINATOR / "mapping.json").read_text())
    for item in packet:
        row = mapping[item["id"]]
        assert row["sha256"] == digest(item["text"])
        assert all(item["text"][s["start"] : s["end"]] == s["text"] for s in row["spans"])


def test_all_108_flags_are_clustered_once():
    old = json.loads((v3.ROOT / "docs/gateway-authoring/review-v2/judgments.json").read_text())
    clusters = json.loads((v3.ROOT / "docs/gateway-authoring/clusters-v3.json").read_text())
    docs = clusters["documents"]
    assert len(docs) == len({r["review_id"] for r in docs}) == 108
    assert {r["review_id"] for r in docs} == {key for key, row in old.items() if row["artifacts"]}
    assert dict(Counter(r["cluster"] for r in docs)) == clusters["clusters"]
    assert all(old[r["review_id"]]["artifacts"] == [r["cause"]] for r in docs)
