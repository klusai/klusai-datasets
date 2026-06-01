#!/usr/bin/env python3
"""Publish the Romanian real-skeleton config (ro-realskeleton-v1) to EuroPriv-Bench.

The *citable* RO track: faithful real-structure documents (CNAS discharge letter, services
contract, declarație, administrative letter) with synthetic PII (valid CNP, CNP-consistent DOB,
RO IBAN/CUI/CI/addresses). Authored skeletons → no residual real PII → GDPR-clean, CC-BY.
Published PRIVATE; immutable config name. Carries CNP spans → enables the cnp_leakage headline.

    python scripts/publish_ro_realskeleton.py --n 1500 --private
"""

from __future__ import annotations

import click
from datasets import Dataset

from klusai.privacy.datasets.data.ro_skeletons import generate_dataset
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-ro-rs")

REPO = "klusai/europriv-bench"
CONFIG = "ro-realskeleton-v1"

CARD_NOTE = """

## Romanian config: `ro-realskeleton-v1`

The **citable Romanian track**: documents that mirror the STRUCTURE and boilerplate of real RO
official document types — the CNAS `SCRISOARE MEDICALĂ` discharge letter, a services contract, a
`DECLARAȚIE PE PROPRIA RĂSPUNDERE`, and an administrative letter — populated with **synthetic** RO
identifiers (valid-checksum CNP, **CNP-consistent date of birth**, RO IBAN/CUI/CI, county
addresses, +40 phones), with Romanian gender agreement. Because the skeletons are authored
faithful reproductions of *public document structure* (RO official texts are non-copyright; Law
8/1996 art. 9(b)) and all identifiers are synthetic, the artifact carries **no real personal
data** and is CC-BY-redistributable.

Pair with `ro-synthetic-v1` (toy-template development track): the F1 / CNP-leakage gap between
the two is the **synthetic-context vs real-context** measurement (Paper 2). Scored with
`cnp_leakage` (a missed CNP deterministically discloses DOB + sex + county).
"""


@click.command()
@click.option("--n", type=int, default=1500)
@click.option("--seed", type=int, default=20260531)
@click.option("--private/--public", default=True)
def main(n: int, seed: int, private: bool) -> None:
    rows = list(generate_dataset(n, seed=seed))
    by_domain: dict[str, int] = {}
    for r in rows:
        by_domain[r["domain"]] = by_domain.get(r["domain"], 0) + 1
    logger.info("generated %d docs by domain: %s; CNP-bearing: %d", len(rows), by_domain,
                sum(1 for r in rows for s in r["spans"] if s["label"] == "NATIONAL_ID"))
    Dataset.from_list(rows).push_to_hub(REPO, config_name=CONFIG, split="test", private=private)

    from huggingface_hub import DatasetCard
    card = DatasetCard.load(REPO, repo_type="dataset")
    if "ro-realskeleton-v1" not in (card.text or ""):
        card.text = (card.text or "") + CARD_NOTE
    card.push_to_hub(REPO, repo_type="dataset")
    logger.info("pushed config %s (%d rows, private=%s)", CONFIG, len(rows), private)


if __name__ == "__main__":
    main()
