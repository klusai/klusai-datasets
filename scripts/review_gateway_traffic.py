"""Frozen 300-doc author self-review adapter for europriv-bench panel statistics.

This does not implement or impersonate a three-family panel. Judgments must be
supplied explicitly after inspection; no API or automatic rating assignment.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from klusai.privacy.datasets.data.gateway_authoring import ROOT
from klusai.privacy.datasets.data.gateway_traffic import LANGUAGES, digest, file_digest

JUDGE = "openai/codex-session-gold-aware-self-review"
BENCH_REVISION = "14cfc44d5218e2f96081fc7ea8db5b07eb2880b3"


def flatten(row):
    text, spans = "", []
    for mi, message in enumerate(row["messages"]):
        for pi, part in enumerate(message["parts"]):
            if text:
                text += "\n"
            offset = len(text)
            text += part["text"]
            spans.extend(
                dict(start=s["start"] + offset, end=s["end"] + offset, label=s["label"], text=s["text"])
                for s in row["spans"]
                if s["message"] == mi and s["part"] == pi
            )
    return dict(
        id=row["id"],
        text=text,
        spans=spans,
        language=row["language"],
        split=row["split"],
        stratum=row["language"] + "/" + row["split"],
        family=row["family_id"],
        token_count=row["token_count"],
        subject_count=len(row["subject_ids"]),
        sha256=digest(text),
    )


def sample(rows):
    rng = random.Random(77)
    result = []
    for li, language in enumerate(LANGUAGES):
        # Four languages at 38 and four at 37; balanced test/dev within language.
        total = 38 if li < 4 else 37
        for split, n in (("test", total // 2), ("dev", total - total // 2)):
            groups = defaultdict(list)
            for row in rows:
                if row["language"] == language and row["split"] == split:
                    groups[row["family_id"]].append(row)
            selected = []
            for _, group in sorted(groups.items()):
                selected.extend(rng.sample(sorted(group, key=lambda r: r["id"]), 2))
            used = {r["id"] for r in selected}
            rest = sorted([r for group in groups.values() for r in group if r["id"] not in used], key=lambda r: r["id"])
            selected.extend(rng.sample(rest, n - len(selected)))
            result.extend(sorted(selected, key=lambda r: r["id"]))
    assert len(result) == len({r["id"] for r in result}) == 300
    return [flatten(r) for r in result]


def write_new(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("sample", "score"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--panel-root", type=Path)
    parser.add_argument("--judgments", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sample_path = args.output / "sample.json"
    if args.phase == "sample":
        paths = [ROOT / f"artifacts/gateway-traffic-v1/originals/{s}.jsonl" for s in ("test", "dev")]
        rows = [json.loads(line) for p in paths for line in p.read_text().splitlines()]
        selected = sample(rows)
        write_new(sample_path, selected)
        write_new(
            args.output / "sample-manifest.json",
            dict(
                n=300,
                population_n=len(rows),
                seed=77,
                seed_count=1,
                method="two per language/split/family cell, remaining slots random within language/split",
                sample_sha256=file_digest(sample_path),
                source_sha256={p.name: file_digest(p) for p in paths},
                strata=dict(Counter(r["stratum"] for r in selected)),
                bench_revision=BENCH_REVISION,
                review_mode="nonblind author self-review; not the frozen three-family panel",
            ),
        )
        return
    if not args.panel_root or not args.judgments:
        parser.error("score requires --panel-root and --judgments")
    # Import exact upstream main snapshot in an isolated read-only directory.
    spec = importlib.util.spec_from_file_location(
        "gateway_upstream_panel", args.panel_root / "analysis/panel_report.py"
    )
    panel = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = panel
    spec.loader.exec_module(panel)
    from europriv_bench.metrics import wilson_interval
    from europriv_bench.panel import candidates, span_set

    rows = json.loads(sample_path.read_text())
    manifest = json.loads((args.output / "sample-manifest.json").read_text())
    if file_digest(sample_path) != manifest["sample_sha256"]:
        raise ValueError("sample hash changed after freeze")
    judgments = json.loads(args.judgments.read_text())
    if set(judgments) != {r["id"] for r in rows}:
        raise ValueError("missing/extra self-review judgments")
    annotations, differences = {}, []
    for row in rows:
        annotation = judgments[row["id"]]
        if annotation["text_sha256"] != row["sha256"] or not annotation["reason"].strip():
            raise ValueError("judgment source hash/reason mismatch")
        if annotation["review_mode"] != "gold-aware author self-review":
            raise ValueError("self-review provenance must be explicit")
        for key in ("fluency", "naturalness"):
            if type(annotation[key]) is not int or not 1 <= annotation[key] <= 5:
                raise ValueError("invalid review rating")
        if not isinstance(annotation["artifacts"], list):
            raise ValueError("missing artifact observations")
        for span in annotation["spans"]:
            if row["text"][span["start"] : span["end"]] != span["text"]:
                raise ValueError("self-review span mismatch")
        annotations[row["id"]] = annotation
        differences.extend(dict(document=row["id"], **p) for p in candidates(row, [annotation]))
    stats = panel.bootstrap(rows, {JUDGE: annotations}, models=(JUDGE,))
    identical = sum(span_set(r["spans"]) == span_set(annotations[r["id"]]["spans"]) for r in rows)
    flagged = sum(bool(annotations[r["id"]]["artifacts"]) for r in rows)
    stats.update(
        review_mode="gold-aware author self-review; agreement is not independent annotation accuracy",
        seed_count=1,
        sampling_seed=77,
        bootstrap_seed=7701,
        config_status="dev",
        release_ready=False,
        exact_document_agreement=dict(
            n=len(rows), identical=identical, ci95=list(wilson_interval(identical, len(rows)))
        ),
        artifact_documents=dict(n=len(rows), flagged=flagged, ci95=list(wilson_interval(flagged, len(rows)))),
        independent_judges=0,
        native_human_reviewers=0,
        model_scoring_seeds=0,
        provenance=dict(
            bench_revision=BENCH_REVISION,
            panel_sha256=file_digest(args.panel_root / "src/europriv_bench/panel.py"),
            report_tool_sha256=file_digest(args.panel_root / "analysis/panel_report.py"),
            protocol_sha256=file_digest(args.panel_root / "docs/validation/panel-protocol.md"),
            sample_sha256=file_digest(sample_path),
            judgments_sha256=file_digest(args.judgments),
        ),
        by_language={
            lang: panel.bootstrap([r for r in rows if r["language"] == lang], {JUDGE: annotations}, models=(JUDGE,))
            for lang in LANGUAGES
        },
        limitations=[
            "Nonblind same-author approval is circular; alpha is descriptive only.",
            "Document bootstrap does not cover template-family or judge uncertainty.",
            "Not native review, three-family panel validation, or model performance scoring.",
            "The upstream protocol's RO/PL four-stratum design is adapted, not claimed fulfilled.",
        ],
    )
    write_new(args.output / "self-review-results.json", stats)
    write_new(args.output / "self-review-disagreements.json", differences)
    print(json.dumps({k: stats[k] for k in ("n", "alpha", "ratings", "artifact_documents")}, indent=2))


if __name__ == "__main__":
    main()
