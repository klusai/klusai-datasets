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

from klusai.privacy.datasets.data.ro_skeletons import (
    family_5gram_jaccard,
    generate_combined_dataset,
)
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-ro-rs")

REPO = "klusai/europriv-bench"
CONFIG = "ro-realskeleton-v1"

CARD_NOTE = """

## Romanian config: `ro-realskeleton-v1`

The **citable Romanian track**: documents that mirror the STRUCTURE and boilerplate of real RO
official document types, populated with **synthetic** RO identifiers (valid-checksum CNP,
**CNP-consistent date of birth**, RO IBAN/CUI/CI, county addresses, +40 phones), with Romanian
gender agreement. Because the skeletons are authored faithful reproductions of *public document
structure* (RO official texts are non-copyright; Law 8/1996 art. 9(b)) and all identifiers are
synthetic, the artifact carries **no real personal data** and is CC-BY-redistributable.

**Two independent template families** (KLU-101 — each row is tagged `family` + `genre`):

* **family A — official correspondence**: CNAS `SCRISOARE MEDICALĂ` discharge letter, services
  contract, `DECLARAȚIE PE PROPRIA RĂSPUNDERE`, administrative letter.
* **family B — academic registry**: `ADEVERINȚĂ DE STUDENT`, `FOAIE MATRICOLĂ`,
  `SUPLIMENT LA DIPLOMĂ` (student matriculation context for the CNP).

Independence is **hard-gated** (asserted in `make check`): different genre, different field
layout, **disjoint synthetic-subject pools** (no CNP/name shared across families), and a token
5-gram **Jaccard overlap of 0.00** between the two families' PII-masked skeletons (threshold ≤ 0.10).
The dissociation is reported **per family** as a difference-of-proportions (Newcombe/Wilson CI on
the gap), removing the single-family generalization caveat (still `dev` until KLU-27 sign-off).

Pair with `ro-synthetic-v1` (toy-template development track): the F1 / CNP-leakage gap between
the two is the **synthetic-context vs real-context** measurement (Paper 2). Scored with
`cnp_leakage` (a missed CNP deterministically discloses DOB + sex + county).
"""


@click.command()
@click.option("--n-per-family", "n_per_family", type=int, default=200,
              help="Distinct subjects per family (KLU-101 pre-registered N: ≥150–200 → leak Wilson UB ≤ 0.02).")
@click.option("--seed", type=int, default=20260531)
@click.option("--private/--public", default=True)
def main(n_per_family: int, seed: int, private: bool) -> None:
    # KLU-101: ship TWO independent template families (A = official correspondence,
    # B = academic registry) tagged per-row with `family`/`genre`. Assert the independence hard
    # gate (5-gram Jaccard ≤ 0.10) at publish time so a contaminated artifact never reaches the hub.
    overlap = family_5gram_jaccard()
    assert overlap <= 0.10, f"family A/B 5-gram Jaccard {overlap:.4f} > 0.10 — not independent"
    rows = list(generate_combined_dataset(n_per_family, seed=seed))
    by_family: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    for r in rows:
        by_family[r.get("family", "?")] = by_family.get(r.get("family", "?"), 0) + 1
        by_domain[r["domain"]] = by_domain.get(r["domain"], 0) + 1
    logger.info("generated %d docs (5-gram Jaccard A/B=%.4f) by family: %s by domain: %s; CNP-bearing: %d",
                len(rows), overlap, by_family, by_domain,
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
