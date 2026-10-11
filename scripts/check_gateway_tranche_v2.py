"""Whole-tranche, local-only integrity/ID checks using the shared harness registry."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from europriv_bench.metrics import wilson_interval
from europriv_bench.national_id import REGISTRY
from klusai.privacy.datasets.data.en_generators import nino_format_valid
from klusai.privacy.datasets.data.gateway_artifact_provenance import revision_bytes
from klusai.privacy.datasets.data.gateway_authoring import COUNTRIES, ROOT, get_tokenizer
from klusai.privacy.datasets.data.gateway_authoring_v2 import attach_provenance
from klusai.privacy.datasets.data.gateway_traffic import Conversation, coverage_report, file_digest, load_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records-dir", type=Path, default=ROOT / "artifacts/gateway-traffic-v1")
    args = parser.parse_args()
    rows, sources = [], {}
    output = ROOT / "artifacts/gateway-traffic-v1"
    for split in ("test", "dev"):
        path = args.records_dir / f"{split}.jsonl"
        group = [Conversation.model_validate_json(line) for line in path.read_text().splitlines()]
        artifact = output / "originals/v2" / f"{split}.jsonl"
        raw = [json.loads(line) for line in artifact.read_text().splitlines()]
        sha = file_digest(artifact)
        revision = group[0].provenance.source_revision
        committed = revision_bytes(revision, artifact, ROOT)
        assert committed == artifact.read_bytes()
        assert len(group) == len(raw)
        for row, draft in zip(group, raw):
            assert row == attach_provenance(draft, artifact, revision, sha)
        sources[split] = dict(
            n=len(group),
            input_revision=revision,
            input_revision_kind="git_blob",
            input_sha256=sha,
            records_sha256=file_digest(path),
        )
        rows.extend(group)
    tokenizer = get_tokenizer()
    counts, dob_counts, countries = Counter(), Counter(), defaultdict(set)
    for row in rows:
        parts = [p.text for m in row.messages for p in m.parts]
        assert sum(len(e.ids) for e in tokenizer.encode_batch(parts, add_special_tokens=False)) == row.token_count
        dob = {s.subject_id: s.text for s in row.spans if s.label == "DATE"}
        for span in row.spans:
            assert row.messages[span.message].parts[span.part].text[span.start : span.end] == span.text
            counts["spans"] += 1
            if span.label == "EMAIL" and "[at]" not in span.text:
                assert re.fullmatch(r"[a-z0-9.]+@example\.invalid", span.text)
                counts["plain_email_mentions"] += 1
            if span.label != "NATIONAL_ID":
                continue
            country = "RO" if span.entity_id.endswith("cross-border") else COUNTRIES[row.language]
            countries[country].add((row.id, span.text))
            if country == "GB":
                assert nino_format_valid(span.text)
                continue
            info = REGISTRY[country].parse(span.text)
            assert info.valid
            if span.subject_id not in dob:
                continue
            value = dob[span.subject_id]
            if info.extra.get("birth_date"):
                assert info.extra["birth_date"] == value
                dob_counts["full_date"] += 1
            elif country == "IT":
                assert (
                    value
                    == f"{info.extra['birth_day']:02d}/{info.extra['birth_month']:02d}/{info.extra['birth_year_2digit']}"
                )
                dob_counts["day_month_two_digit_year"] += 1
            elif country == "FR":
                assert value == f"{info.extra['birth_month']:02d}/{info.extra['birth_year_2digit']}"
                dob_counts["month_two_digit_year"] += 1
    spec = load_manifest(ROOT / "conf/gateway_traffic_manifest.yaml")
    coverage = coverage_report(rows, spec)
    assert all("native double-reviewed" in e for e in coverage["errors"])
    checks = {
        country: dict(
            n=len(values),
            valid=len(values),
            ci95=list(wilson_interval(len(values), len(values))),
            kind="format-only; no checksum exists" if country == "GB" else "harness checksum/structure",
        )
        for country, values in sorted(countries.items())
    }
    report = dict(
        n=len(rows),
        generation_seed=124,
        generation_seed_count=1,
        model_scoring_seed_count=0,
        config_status="dev",
        sources=sources,
        counts=dict(counts),
        identifiers=checks,
        decoded_dob_comparisons=dict(dob_counts),
        tranche_coverage=coverage,
        tokenizer=dict(
            id=rows[0].tokenizer_id,
            revision=rows[0].tokenizer_revision,
            tokens_min=min(r.token_count for r in rows),
            tokens_max=max(r.token_count for r in rows),
        ),
        caveats=[
            "Census checks, not model scores; Wilson intervals are descriptive only.",
            "No real registry assignment, exact street geography or account existence checked.",
            "Full volume met; independent blind/naturalness and native review gates are not established here.",
        ],
    )
    path = ROOT / "docs/gateway-authoring/invariants-v2.json"
    with path.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps({"n": len(rows), "counts": dict(counts), "identifiers": checks, "dob": dict(dob_counts)}, indent=2)
    )


if __name__ == "__main__":
    main()
