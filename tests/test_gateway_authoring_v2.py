"""Full revision invariants, including meaningful owner roles and historical split identity."""

from __future__ import annotations

import json
import re
from collections import Counter

import pytest

from europriv_bench.national_id import REGISTRY
from klusai.privacy.datasets.data import gateway_authoring as v1
from klusai.privacy.datasets.data import gateway_authoring_v2 as v2
from klusai.privacy.datasets.data.en_generators import card_valid, nino_format_valid
from klusai.privacy.datasets.data.gateway_traffic import (
    FEATURES,
    LANGUAGES,
    coverage_report,
    file_digest,
    load_manifest,
    validate_collection,
)


@pytest.fixture(scope="module")
def drafts():
    paths = [v2.ARTIFACTS / f"{s}.jsonl" for s in ("test", "dev")]
    assert all(p.exists() for p in paths), "The full authored revision must be present"
    return [(p, json.loads(line)) for p in paths for line in p.read_text().splitlines()]


@pytest.fixture(scope="module")
def rows(drafts):
    hashes = {p: file_digest(p) for p in {path for path, _ in drafts}}
    return [v2.attach_provenance(d, p, "a" * 40, hashes[p]) for p, d in drafts]


def test_full_volume_and_reserved_slots(drafts):
    counts = Counter((d["split"], d["language"]) for _, d in drafts)
    assert counts == {(s, lang): n for s, n in (("test", 1000), ("dev", 200)) for lang in LANGUAGES}
    for s, n in (("test", 1000), ("dev", 200)):
        plan = v2.allocation(n, s)
        assert Counter(a for a, _ in plan) == dict(negative=n // 5, small=n * 2 // 5, medium=n * 3 // 10, dense=n // 10)
        assert Counter(b for _, b in plan) == dict(short=n // 2, medium=n * 7 // 20, long=n * 3 // 20)
        assert all(not (a == "dense" and b == "short") for a, b in plan)


def test_schema_coverage_and_append_only_ledger(rows):
    manifest = load_manifest(v2.ROOT / "conf/gateway_traffic_manifest.yaml")
    plan = json.loads((v2.ROOT / manifest["split_plan"]["path"]).read_text())
    prior = json.loads((v2.ROOT / "docs/gateway-authoring/audit.json").read_text())["ledger"]
    ledger = validate_collection(rows, manifest, plan, prior)
    assert all(ledger[key] == split for key, split in prior.items())
    report = coverage_report(rows, manifest)
    assert report["errors"] == [
        f"{lang}: fewer than 100 native double-reviewed/adjudicated conversations" for lang in LANGUAGES
    ]
    assert all(set(cell["features"]) == set(FEATURES) for cell in report["cells"].values())


def test_whole_revision_token_counts(rows, gateway_tokenizer):
    for row in rows:
        parts = [p.text for m in row.messages for p in m.parts]
        count = sum(len(e.ids) for e in gateway_tokenizer.encode_batch(parts, add_special_tokens=False))
        assert count == row.token_count


def test_whole_revision_offsets_lengths_and_distinct_text(rows, drafts):
    seen = set()
    for row, (_, draft) in zip(rows, drafts):
        parts = [p.text for m in row.messages for p in m.parts]
        lo, hi = {"short": (32, 128), "medium": (129, 512), "long": (513, 2048)}[draft["intended_length"]]
        assert lo <= row.token_count <= hi
        text = "\n".join(parts)
        assert text not in seen
        seen.add(text)
        assert "[[" not in text
        for span in row.spans:
            assert row.messages[span.message].parts[span.part].text[span.start : span.end] == span.text
        if row.subject_ids:
            # Each participant has an attributed case/status/skill, not a detached list of names.
            names = [s for s in row.spans if s.label == "PERSON"]
            assert all(
                any(s.subject_id == sid and text[s.end : s.end + 3] == " — " for s in names) for sid in row.subject_ids
            )
        else:
            assert not row.spans


def test_all_national_ids_cards_and_owner_dob(rows):
    identifiers = {}
    for row in rows:
        dates = {s.subject_id: s.text for s in row.spans if s.label == "DATE"}
        for s in row.spans:
            if s.label == "EMAIL" and "[at]" not in s.text:
                assert re.fullmatch(r"[a-z0-9.]+@example\.invalid", s.text)
            if s.entity_id.endswith("/card"):
                assert card_valid(s.text)
            if s.label != "NATIONAL_ID":
                continue
            country = v1.COUNTRIES[row.language]
            assert identifiers.setdefault((country, s.text), row.split) == row.split
            if country == "GB":
                assert nino_format_valid(s.text)
                continue
            info = REGISTRY[country].parse(s.text)
            assert info.valid
            dob = dates.get(s.subject_id)
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


def test_fresh_review_excludes_prior_translation_groups(drafts):
    from scripts.review_gateway_traffic_v2 import fresh_sample

    prior = json.loads((v2.ROOT / "docs/gateway-authoring/review/sample.json").read_text())
    excluded = {(r["family"], r["id"].rsplit("-", 1)[1]) for r in prior}
    fresh = fresh_sample([d for _, d in drafts], prior)
    assert len(fresh) == len({r["id"] for r in fresh}) == 300
    assert all((r["family"], r["id"].rsplit("-", 1)[1]) not in excluded for r in fresh)
    assert set(r["language"] for r in fresh) == set(LANGUAGES)
    path = v2.ROOT / "docs/gateway-authoring/review-v2/packet.json"
    if path.exists():
        packet = json.loads(path.read_text())
        assert packet == [dict(id=f"R{i + 1:03d}", language=r["language"], text=r["text"]) for i, r in enumerate(fresh)]
        assert all(set(row) == {"id", "language", "text"} for row in packet)


def test_expense_csv_and_field_owner_boundaries(rows):
    import csv
    import io

    for row in rows:
        text = row.messages[0].parts[0].text
        if "```csv\n" not in text:
            continue
        table = text.split("```csv\n", 1)[1].split("```", 1)[0]
        parsed = list(csv.reader(io.StringIO(table), delimiter=";"))
        assert len(parsed) == 37
        assert all(len(r) == 8 for r in parsed)
        # Header-like bank/company fields must follow the named owner, not the last person in a list.
        last_subject = None
        for span in row.spans:
            if span.start >= text.index("```csv\n"):
                break
            if span.label == "PERSON":
                last_subject = span.subject_id
            else:
                assert span.subject_id == last_subject


def test_review_receipts_bind_every_judgment_to_frozen_text():
    from klusai.privacy.datasets.data.gateway_traffic import digest

    directory = v2.ROOT / "docs/gateway-authoring/review-v2"
    packet = json.loads((directory / "packet.json").read_text())
    judgments = json.loads((directory / "judgments.json").read_text())
    report = json.loads((directory / "results.json").read_text())
    assert set(judgments) == {row["id"] for row in packet}
    assert report["provenance"]["packet_sha256"] == file_digest(directory / "packet.json")
    assert report["provenance"]["judgments_sha256"] == file_digest(directory / "judgments.json")
    for row in packet:
        assert judgments[row["id"]]["text_sha256"] == digest(row["text"])
        assert judgments[row["id"]]["reason"].strip()
