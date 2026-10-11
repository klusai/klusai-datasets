"""Freeze a fresh score-blind review packet; score explicit judgments with the upstream panel tool.

No model calls or automatic ratings. Reviewers see opaque IDs, language and text.
The private mapping and population hashes make the blinding and exclusions auditable.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from klusai.privacy.datasets.data.gateway_authoring_v2 import ARTIFACTS, ROOT
from klusai.privacy.datasets.data.gateway_traffic import LANGUAGES, digest, file_digest
from scripts.review_gateway_traffic import BENCH_REVISION, flatten, write_new

SEED = 12402


def fresh_sample(rows, previous):
    excluded = {(r["family"], r["id"].rsplit("-", 1)[1]) for r in previous}
    rng = random.Random(SEED)
    selected = []
    for li, lang in enumerate(LANGUAGES):
        total = 38 if li < 4 else 37
        for split, n in (("test", total // 2), ("dev", total - total // 2)):
            groups = defaultdict(list)
            for row in rows:
                if row["language"] == lang and row["split"] == split:
                    key = (row["family_id"], row["id"].rsplit("-", 1)[1])
                    if key not in excluded:
                        groups[row["family_id"]].append(row)
            cell = []
            for _, group in sorted(groups.items()):
                cell.extend(rng.sample(sorted(group, key=lambda r: r["id"]), 2))
            used = {r["id"] for r in cell}
            rest = sorted([r for group in groups.values() for r in group if r["id"] not in used], key=lambda r: r["id"])
            cell.extend(rng.sample(rest, n - len(cell)))
            selected.extend(cell)
    rng.shuffle(selected)
    return [flatten(r) for r in selected]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("sample", "score"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judgments", type=Path)
    parser.add_argument("--panel-root", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase == "sample":
        paths = [ARTIFACTS / f"{split}.jsonl" for split in ("test", "dev")]
        rows = [json.loads(line) for p in paths for line in p.read_text().splitlines()]
        previous_path = ROOT / "docs/gateway-authoring/review/sample.json"
        selected = fresh_sample(rows, json.loads(previous_path.read_text()))
        packet, mapping = [], {}
        for i, row in enumerate(selected):
            opaque = f"R{i + 1:03d}"
            mapping[opaque] = row
            packet.append(dict(id=opaque, language=row["language"], text=row["text"]))
        write_new(args.output / "packet.json", packet)
        write_new(args.output / "mapping.json", mapping)
        write_new(
            args.output / "sample-manifest.json",
            dict(
                n=len(packet),
                population_n=len(rows),
                sampling_seed=SEED,
                seed_count=1,
                method="two per eligible language/split/family cell plus random extras, then shuffled opaque IDs",
                exclusion="every scenario/translation group present in the earlier sample, across all languages",
                previous_sample_sha256=file_digest(previous_path),
                packet_sha256=file_digest(args.output / "packet.json"),
                mapping_sha256=file_digest(args.output / "mapping.json"),
                sources={str(p.relative_to(ROOT)): file_digest(p) for p in paths},
                strata=dict(Counter(r["stratum"] for r in selected)),
                bench_revision=BENCH_REVISION,
            ),
        )
        return
    if not args.judgments or not args.panel_root:
        parser.error("score requires --judgments and --panel-root")
    packet = json.loads((args.output / "packet.json").read_text())
    mapping = json.loads((args.output / "mapping.json").read_text())
    manifest = json.loads((args.output / "sample-manifest.json").read_text())
    for name in ("packet", "mapping"):
        if file_digest(args.output / f"{name}.json") != manifest[f"{name}_sha256"]:
            raise ValueError("review packet changed after freeze")
    judgments = json.loads(args.judgments.read_text())
    if set(judgments) != set(mapping):
        raise ValueError("missing/extra judgments")
    for row in packet:
        j = judgments[row["id"]]
        if j["text_sha256"] != digest(row["text"]) or not j["reason"].strip():
            raise ValueError("judgment source hash/reason mismatch")
        for key in ("fluency", "naturalness"):
            if type(j[key]) is not int or not 1 <= j[key] <= 5:
                raise ValueError("invalid rating")
        if not isinstance(j["artifacts"], list):
            raise ValueError("artifact observations must be explicit")
    spec = importlib.util.spec_from_file_location("gateway_panel_v2", args.panel_root / "analysis/panel_report.py")
    panel = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = panel
    spec.loader.exec_module(panel)
    from europriv_bench.metrics import wilson_interval

    judge = "openai/codex-session-naturalness-self-review"
    # Naturalness review does not manufacture an annotation-agreement result.
    rows = [dict(id=key, language=row["language"], stratum=row["stratum"], spans=[]) for key, row in mapping.items()]
    annotations = {key: dict(**value, spans=[]) for key, value in judgments.items()}
    stats = panel.bootstrap(rows, {judge: annotations}, models=(judge,))
    flagged = sum(bool(j["artifacts"]) for j in judgments.values())
    stats.update(
        sampling_seed=SEED,
        sampling_seed_count=1,
        bootstrap_seed=7701,
        config_status="dev",
        release_ready=False,
        review_mode="same-author self-review; packet hides scores but reviewer knew earlier aggregate scores",
        independent_judges=0,
        native_human_reviewers=0,
        model_scoring_seed_count=0,
        gold_agreement=None,
        artifact_documents=dict(n=len(rows), flagged=flagged, ci95=list(wilson_interval(flagged, len(rows)))),
        by_language={
            lang: panel.bootstrap([r for r in rows if r["language"] == lang], {judge: annotations}, models=(judge,))
            for lang in LANGUAGES
        },
        provenance=dict(
            bench_revision=BENCH_REVISION,
            panel_sha256=file_digest(args.panel_root / "src/europriv_bench/panel.py"),
            report_tool_sha256=file_digest(args.panel_root / "analysis/panel_report.py"),
            protocol_sha256=file_digest(args.panel_root / "docs/validation/panel-protocol.md"),
            packet_sha256=manifest["packet_sha256"],
            judgments_sha256=file_digest(args.judgments),
        ),
        limitations=[
            "Earlier aggregate scores were known to the author; this is not a blind validation pass.",
            "Fresh membership excludes earlier sampled scenarios across languages, not entire template families.",
            "Document bootstrap omits family and reviewer uncertainty; no independent delta/win claim.",
            "No new gold annotation agreement, native review, or three-family panel is claimed.",
        ],
    )
    write_new(args.output / "results.json", stats)
    print(json.dumps({k: stats[k] for k in ("n", "ratings", "artifact_documents")}, indent=2))


if __name__ == "__main__":
    main()
