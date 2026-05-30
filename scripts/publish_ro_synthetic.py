#!/usr/bin/env python3
"""Publish the Romanian localized-synthetic config (ro-synthetic-v1) to EuroPriv-Bench.

Development track (pure localized synthetic — RO-native identifiers incl. CNP). Offset-
deterministic generation. Published PRIVATE; immutable config name so it never mixes with the
later real-skeleton gold. Carries CNP spans → enables the cnp_leakage headline metric.

    python scripts/publish_ro_synthetic.py --n 1500 --private
"""

from __future__ import annotations

import click
from datasets import Dataset

from klusai.privacy.datasets.data.ro_documents import generate_dataset
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-ro")

REPO = "klusai/europriv-bench"
CONFIG = "ro-synthetic-v1"

CARD_NOTE = """

## Romanian config: `ro-synthetic-v1`

**Localized-synthetic development track** for Romanian (RO is absent from AI4Privacy). Documents
are template-generated with RO-native identifiers — **CNP** (valid mod-11 checksum, encodes
DOB+sex+county), **RO IBAN** (mod-97), **CUI**, county addresses, +40 phones — spliced
offset-deterministically (`text[start:end] == value` by construction). Labeled in the KP taxonomy
(incl. `NATIONAL_ID`, `COMPANY_ID`).

Scored with **`cnp_leakage`**: a missed CNP deterministically discloses date-of-birth + sex +
county. This is a *development* track (synthetic distribution); the real-skeleton gold
(`ro-realskeleton-v1`) is the citable one. Synthetic data carries no data subject.
"""


@click.command()
@click.option("--n", type=int, default=1500, help="Number of documents.")
@click.option("--seed", type=int, default=20260530, help="Generation seed (held-out gold).")
@click.option("--private/--public", default=True)
def main(n: int, seed: int, private: bool) -> None:
    rows = list(generate_dataset(n, seed=seed))
    logger.info("generated %d RO docs; CNP-bearing: %d", len(rows),
                sum(1 for r in rows for s in r["spans"] if s["label"] == "NATIONAL_ID"))
    Dataset.from_list(rows).push_to_hub(REPO, config_name=CONFIG, split="test", private=private)

    from huggingface_hub import DatasetCard
    card = DatasetCard.load(REPO, repo_type="dataset")
    if "ro-synthetic-v1" not in (card.text or ""):
        card.text = (card.text or "") + CARD_NOTE
    if "ro" not in (card.data.language or []):
        card.data.language = list(card.data.language or []) + ["ro"]
    card.push_to_hub(REPO, repo_type="dataset")
    logger.info("pushed config %s (%d rows, private=%s)", CONFIG, len(rows), private)


if __name__ == "__main__":
    main()
