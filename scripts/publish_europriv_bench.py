#!/usr/bin/env python3
"""Publish EuroPriv-Bench v0 (detection) to HF as per-language configs.

v0 is seeded from AI4Privacy open core (CC-BY-4.0), remapped to the harmonized KP taxonomy.
Legal/clinical splits and TAB/MEDDOCAN subsumption come in later phases. Published PRIVATE to
match the WIP GitHub repos; flip to public at launch.

    python scripts/publish_europriv_bench.py --cap 1500 --private
"""

from __future__ import annotations

from collections import Counter

import click
from datasets import Dataset

from klusai.privacy.datasets.data.curate import map_ai4privacy_row
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish")

REPO = "klusai/europriv-bench"
SOURCE = "ai4privacy/open-pii-masking-500k-ai4privacy"
LANGS = ["en", "fr", "es", "de", "it", "nl"]  # European langs available in AI4Privacy v0

CARD = """# EuroPriv-Bench (v0 — detection)

Held-out gold for **pan-European PII/PHI de-identification**, labeled in the harmonized
**KP taxonomy** (BIOES). Each row: `text`, `spans` (`{start, end, label}`, KP labels),
`language`. Scored by the [`europriv-bench`](https://github.com/klusai/europriv-bench) harness
(entity F1 / recall-weighted F2; re-identification-risk + privacy-utility tracks to follow).

> **v0 scope:** seeded from AI4Privacy open core, remapped to KP. Legal + clinical splits,
> Romanian (not in AI4Privacy), and TAB/MEDDOCAN subsumption land in later phases. This is the
> *first unified* step, not the finished benchmark.

## Configs

One per language: `en`, `fr`, `es`, `de`, `it`, `nl` (split: `test`).

```python
from datasets import load_dataset
ds = load_dataset("klusai/europriv-bench", "en", split="test")
```

## Attribution & license

Derived from **[AI4Privacy open-pii-masking-500k](https://huggingface.co/datasets/ai4privacy/open-pii-masking-500k-ai4privacy)**
(CC-BY-4.0); native labels remapped to the KP taxonomy crosswalk. Redistributed under
**CC-BY-4.0** with attribution. Only cleanly-licensed sources are used so the suite stays
openly redistributable.
"""


@click.command()
@click.option("--cap", type=int, default=1500, help="Max rows per language.")
@click.option("--scan-cap", type=int, default=120000, help="Max source rows to scan.")
@click.option("--private/--public", default=True, help="Publish private (default) or public.")
@click.option("--dry-run", is_flag=True, help="Curate + report, but do not push.")
def main(cap: int, scan_cap: int, private: bool, dry_run: bool) -> None:
    from datasets import load_dataset

    buckets: dict[str, list[dict]] = {lang: [] for lang in LANGS}
    dropped: Counter = Counter()
    scanned = 0
    ds = load_dataset(SOURCE, split="validation", streaming=True)
    for r in ds:
        scanned += 1
        lang = r.get("language")
        if lang not in buckets or len(buckets[lang]) >= cap:
            if all(len(buckets[x]) >= cap for x in LANGS) or scanned >= scan_cap:
                break
            continue
        text = r.get("source_text") or r.get("text")
        try:
            row = map_ai4privacy_row(text, r.get("privacy_mask") or [], dropped=dropped)
        except ValueError:
            continue
        row["language"] = lang
        buckets[lang].append(row)

    for lang in LANGS:
        logger.info("%s: %d gold rows", lang, len(buckets[lang]))
    if dropped:
        logger.info("dropped unmapped native labels: %s", dict(dropped.most_common()))

    if dry_run:
        logger.info("dry-run — not pushing")
        return

    for lang in LANGS:
        rows = buckets[lang]
        if not rows:
            logger.warning("%s: no rows, skipping", lang)
            continue
        Dataset.from_list(rows).push_to_hub(REPO, config_name=lang, split="test", private=private)
        logger.info("pushed config %s (%d rows)", lang, len(rows))

    # Edit the card via DatasetCard so push_to_hub's `configs:` registry is preserved
    # (a raw README upload would clobber it and collapse all configs back to `default`).
    from huggingface_hub import DatasetCard

    card = DatasetCard.load(REPO, repo_type="dataset")
    card.data.license = "cc-by-4.0"
    card.data.language = LANGS
    card.data.task_categories = ["token-classification"]
    card.data.tags = ["pii", "privacy", "de-identification", "europriv-bench", "kp"]
    card.data.pretty_name = "EuroPriv-Bench (v0, detection)"
    card.text = CARD
    card.push_to_hub(REPO, repo_type="dataset")
    logger.info("published %s (private=%s) -> https://huggingface.co/datasets/%s", REPO, private, REPO)


if __name__ == "__main__":
    main()
