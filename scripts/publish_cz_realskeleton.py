#!/usr/bin/env python3
"""Publish the Czech real-skeleton config (cz-realskeleton-v1) to EuroPriv-Bench.

A citable-track candidate (config_status=dev; not yet validated — pending native-speaker review +
IAA) and a decode-bearing measurement (RES-80, after RO/CNP, PL/PESEL, IT/codice-fiscale):
faithful real-structure documents (propouštěcí zpráva/discharge report, services contract, sworn
declaration, administrative decision) with synthetic PII (valid mod-11 rodné číslo,
rodné-číslo-consistent DOB, IČO/IBAN/+420 phones/addresses), Czech gender agreement. Authored
skeletons → no residual real PII → GDPR-clean, CC-BY. Published PRIVATE; immutable config name.
Carries rodné-číslo spans + ``country='CZ'`` → enables the national_id_leakage headline.

    python scripts/publish_cz_realskeleton.py --n 1500 --private
"""

from __future__ import annotations

import click
from datasets import Dataset

from klusai.privacy.datasets.data.cz_skeletons import generate_dataset
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-cz-rs")

REPO = "klusai/europriv-bench"
CONFIG = "cz-realskeleton-v1"

CARD_NOTE = """

## Czech config: `cz-realskeleton-v1`

A **citable-track candidate** (currently `config_status=dev`; not yet validated — pending
native-speaker review + IAA) and a **decode-bearing measurement** (RES-80, extending the
detection≠re-id dissociation beyond RO/PL/IT): documents that mirror the STRUCTURE and boilerplate
of real Czech official document types — a discharge report (`Propouštěcí zpráva`), a services
contract (`Smlouva o poskytování služeb`), a sworn declaration (`Čestné prohlášení`), and an
administrative decision (`Rozhodnutí`) — populated with **synthetic** Czech identifiers
(valid-mod-11 **rodné číslo**, **rodné-číslo-consistent date of birth**, IČO/IBAN, +420 phones,
addresses), with Czech gender agreement (the -ová feminine surname). Because the skeletons are
authored faithful reproductions of *public document structure* and all identifiers are synthetic,
the artifact carries **no real personal data** and is CC-BY-redistributable.

Every row carries `country="CZ"` so the country-dispatched `national_id_leakage` metric validates
and decodes the gold IDs with the **rodné číslo** validator: a missed (un-redacted) rodné číslo
deterministically discloses **DATE_OF_BIRTH + SEX** (the modern 10-digit form is fully
date-recoverable; female births carry month +50; century by the YY≥54→19YY convention). All four
templates are **one authored skeleton family** sharing a single fill path — a leak headline from a
single template family is not validated generalization, so a second independent template family is
required before this is cited. The discharge report legitimately repeats the patient rodné číslo
(identity header + `Rodné číslo (identifikace pacienta)`); re-identification is counted **per
distinct subject**, so the repeat collapses to one subject (KLU-49 dedup) and never double-counts.

Pair with `ro-realskeleton-v1`, `pl-realskeleton-v1` and `it-realskeleton-v1`: together they test
whether the train-for-protection result holds on additional decode-bearing identifiers and
languages (here rodné číslo / Czech, scored zero-shot for the RO-trained kp-deid).
"""


@click.command()
@click.option("--n", type=int, default=1500)
@click.option("--seed", type=int, default=20260606)
@click.option("--private/--public", default=True)
def main(n: int, seed: int, private: bool) -> None:
    rows = list(generate_dataset(n, seed=seed))
    by_domain: dict[str, int] = {}
    for r in rows:
        by_domain[r["domain"]] = by_domain.get(r["domain"], 0) + 1
    subjects = {
        (i, r["text"][s["start"]:s["end"]])
        for i, r in enumerate(rows) for s in r["spans"]
        if s["label"] == "NATIONAL_ID"
    }
    logger.info("generated %d docs by domain: %s; distinct rodné-číslo subjects: %d",
                len(rows), by_domain, len(subjects))
    Dataset.from_list(rows).push_to_hub(REPO, config_name=CONFIG, split="test", private=private)

    from huggingface_hub import DatasetCard
    card = DatasetCard.load(REPO, repo_type="dataset")
    if CONFIG not in (card.text or ""):
        card.text = (card.text or "") + CARD_NOTE
    card.push_to_hub(REPO, repo_type="dataset")
    logger.info("pushed config %s (%d rows, private=%s)", CONFIG, len(rows), private)


if __name__ == "__main__":
    main()
