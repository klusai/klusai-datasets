#!/usr/bin/env python3
"""Curate a EuroPriv-Bench gold split from AI4Privacy open core (CC-BY-4.0).

Maps source rows to the harmonized KP taxonomy and writes validated JSONL
({text, spans, language}) ready for `scripts/upload_dataset.py`. Reports label coverage
(which native labels were dropped as unmapped) — no silent truncation.

    python scripts/curate_ai4privacy.py --language en --limit 2000 --out artifacts/europriv/en.jsonl

Requires network/HF access and the `datasets` library (a core dep).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import click

from klusai.privacy.datasets.data.curate import map_ai4privacy_row
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("curate")

# RES-93: the 500k repo is Llama-license-bound (excluded by the gate); the openpii-1m repo is the
# verified-clean CC-BY-4.0 open core (no Llama clause). See conf/datasets.yaml + the manifest.
SOURCE = "ai4privacy/pii-masking-openpii-1m"


@click.command()
@click.option("--language", default="en", help="ISO language code to filter (source `language` field).")
@click.option("--split", default="validation", help="HF split to draw the held-out gold from.")
@click.option("--limit", type=int, default=0, help="Cap rows (0 = all).")
@click.option("--out", required=True, help="Output JSONL path.")
def main(language: str, split: str, limit: int, out: str) -> None:
    from datasets import load_dataset

    ds = load_dataset(SOURCE, split=split)
    if "language" in ds.column_names:
        ds = ds.filter(lambda r: r.get("language") == language)
    if limit:
        ds = ds.select(range(min(limit, len(ds))))

    dropped: Counter = Counter()
    kept = 0
    bad = 0
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in ds:
            text = r.get("source_text") or r.get("text")
            mask = r.get("privacy_mask") or []
            try:
                row = map_ai4privacy_row(text, mask, dropped=dropped)
            except ValueError as e:
                bad += 1
                logger.warning("skipping misaligned row: %s", e)
                continue
            row["language"] = language
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            kept += 1

    logger.info("wrote %d rows -> %s (%d skipped misaligned)", kept, out_path, bad)
    if dropped:
        logger.info("dropped unmapped native labels (extend taxonomy crosswalk to capture): %s",
                    dict(dropped.most_common()))


if __name__ == "__main__":
    main()
