"""Freeze a score-free Stage A handoff; no inference, ratings, or publication."""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from dataclasses import asdict

from europriv_bench.taxonomy import TAXONOMY, TAXONOMY_VERSION
from klusai.privacy.datasets.data.gateway_authoring_v3 import ARTIFACTS, ROOT
from klusai.privacy.datasets.data.gateway_traffic import LANGUAGES, file_digest
from scripts.review_gateway_traffic import BENCH_REVISION, flatten, write_new

SEED = 12403
PACKET = ROOT / "docs/validation/gateway-r1-sample"
COORDINATOR = ROOT / "docs/gateway-authoring/review-v3"
PREVIOUS = (
    ROOT / "docs/gateway-authoring/review/sample.json",
    ROOT / "docs/gateway-authoring/review-v2/mapping.json",
)


def previous_rows():
    first, second = [json.loads(p.read_text()) for p in PREVIOUS]
    return first + list(second.values())


def fresh_sample(rows, previous):
    """Exclude all previously reviewed scenario groups across languages, regardless of outcome."""
    excluded = {(r["family"], r["id"].rsplit("-", 1)[1]) for r in previous}
    rng = random.Random(SEED)
    selected = []
    for li, lang in enumerate(LANGUAGES):
        total = 38 if li < 4 else 37
        for split, n in (("test", total // 2), ("dev", total - total // 2)):
            groups = defaultdict(list)
            for row in rows:
                key = (row["family_id"], row["id"].rsplit("-", 1)[1])
                if row["language"] == lang and row["split"] == split and key not in excluded:
                    groups[row["family_id"]].append(row)
            if len(groups) != 8 or any(len(group) < 2 for group in groups.values()):
                raise ValueError("Insufficient unseen scenarios; do not silently relax exclusions")
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
    paths = [ARTIFACTS / f"{split}.jsonl" for split in ("test", "dev")]
    rows = [json.loads(line) for p in paths for line in p.read_text().splitlines()]
    selected = fresh_sample(rows, previous_rows())
    PACKET.mkdir(parents=True, exist_ok=True)
    COORDINATOR.mkdir(parents=True, exist_ok=True)
    packet, mapping = [], {}
    for i, row in enumerate(selected):
        opaque = f"G{i + 1:03d}"
        mapping[opaque] = row
        packet.append(dict(id=opaque, language=row["language"], text=row["text"]))
    write_new(PACKET / "sample.json", packet)
    write_new(PACKET / "taxonomy.json", dict(version=TAXONOMY_VERSION, entities=[asdict(e) for e in TAXONOMY]))
    write_new(COORDINATOR / "mapping.json", mapping)
    # Coordinator-only panel rows use opaque IDs so Stage A responses can be aligned directly.
    write_new(COORDINATOR / "panel-rows.json", [dict(row, id=key) for key, row in mapping.items()])
    write_new(
        COORDINATOR / "sample-manifest.json",
        dict(
            n=len(packet),
            population_n=len(rows),
            sampling_seed=SEED,
            sampling_seed_count=1,
            model_scoring_seed_count=0,
            status="awaiting_separate_blind_reviewer",
            method="two per eligible language/split/family cell plus random extras, shuffled opaque IDs",
            exclusion="union of both earlier reviewed scenario/translation groups across all languages",
            previous_samples={str(p.relative_to(ROOT)): file_digest(p) for p in PREVIOUS},
            reviewer_files={p.name: file_digest(p) for p in sorted(PACKET.iterdir()) if p.is_file()},
            mapping_sha256=file_digest(COORDINATOR / "mapping.json"),
            panel_rows_sha256=file_digest(COORDINATOR / "panel-rows.json"),
            sources={str(p.relative_to(ROOT)): file_digest(p) for p in paths},
            strata=dict(Counter(r["stratum"] for r in selected)),
            bench_revision=BENCH_REVISION,
            limitations=[
                "Shared author and template families; prior reviewed scenario groups are excluded, not entire families.",
                "Balanced language/split/workflow sample; not population-weighted traffic estimates.",
                "One sampling seed; no independent annotations, scores, CIs or agreement yet.",
                "Reviewer folder is an information boundary, not access control; distribute only that folder for Stage A.",
            ],
        ),
    )
    print(f"Frozen {len(packet)} unscored documents: {PACKET}")


if __name__ == "__main__":
    main()
