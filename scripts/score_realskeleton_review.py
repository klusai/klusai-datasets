#!/usr/bin/env python3
"""Summarize fixed author ratings with protocol CIs; does not generate or change ratings."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from europriv_bench.metrics import wilson_interval


def percentile(values, q):
    values = sorted(values)
    position = (len(values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def summarize(sample: Path, annotations: Path):
    data = sample.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    source = {r["source_index"]: r for r in map(json.loads, data.decode().splitlines())}
    with annotations.open() as f:
        ratings = list(csv.DictReader(f))
    assert len(ratings) == len(source) == 100
    assert len({int(r["source_index"]) for r in ratings}) == len(ratings)
    groups = defaultdict(list)
    for rating in ratings:
        row = source[int(rating["source_index"])]
        assert rating["text_sha256"] == row["text_sha256"] == hashlib.sha256(row["text"].encode()).hexdigest()
        assert rating["sample_sha256"] == sha and rating["stratum"] == row["stratum"]
        assert rating["config"] == row["config"]
        for metric in ("naturalness", "fluency"):
            rating[metric] = int(rating[metric])
            assert 1 <= rating[metric] <= 5
        groups[rating["stratum"]].append(rating)
    assert len(groups) == 4 and all(len(group) == 25 for group in groups.values())
    result = {
        "n": 100, "judge_count": 1, "judge": "Codex author self-review",
        "independent": False, "scored_generation_seed_count": 1, "total_build_seed_count": 2,
        "bootstrap_replicates": 2000, "bootstrap_seed": 7701,
        "sampling": "25 per type without replacement, equal-stratum estimates",
        "sample_sha256": sha, "annotations_sha256": hashlib.sha256(annotations.read_bytes()).hexdigest(),
        "limitations": "Conditional document CIs only; no judge, template-family or author-bias uncertainty",
    }
    rng = random.Random(7701)
    replicates = {metric: [] for metric in ("naturalness", "fluency")}
    for _ in range(2000):
        draw = [rng.choice(group) for _, group in sorted(groups.items()) for _ in range(len(group))]
        for metric in replicates:
            replicates[metric].append(statistics.median(r[metric] for r in draw))
    for metric, values in replicates.items():
        result[metric] = {
            "median": statistics.median(r[metric] for r in ratings),
            "bootstrap_95": [percentile(values, 0.025), percentile(values, 0.975)],
            "distribution": dict(sorted(Counter(r[metric] for r in ratings).items())),
        }
    flagged = sum(bool(r["artifact_flags"]) for r in ratings)
    above = sum(r["naturalness"] >= 4 for r in ratings)
    result["artifact_flagged"] = {"n": 100, "count": flagged, "wilson_95": wilson_interval(flagged, 100)}
    result["naturalness_at_least_4"] = {"n": 100, "count": above, "wilson_95": wilson_interval(above, 100)}
    result["by_stratum"] = {
        kind: {"n": len(group), "naturalness_median": statistics.median(r["naturalness"] for r in group),
               "fluency_median": statistics.median(r["fluency"] for r in group),
               "flagged": sum(bool(r["artifact_flags"]) for r in group)}
        for kind, group in sorted(groups.items())
    }
    result["naturalness_target_met_in_author_review"] = result["naturalness"]["median"] >= 4
    result["full_panel_pass"] = False
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, default=Path("docs/validation"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {lang: summarize(args.samples / f"{lang}-realskeleton-v2/self-review.jsonl",
                              args.annotations / f"{lang}-realskeleton-v2-self-review.csv")
              for lang in ("ro", "pl")}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
