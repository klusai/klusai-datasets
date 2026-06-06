#!/usr/bin/env python3
"""Publish the Swedish real-skeleton config (se-realskeleton-v1) to EuroPriv-Bench.

A citable-track candidate (config_status=dev; not yet validated — pending native-speaker review +
IAA) and a decode-bearing measurement (RES-80, after RO/CNP, PL/PESEL, IT/codice-fiscale):
faithful real-structure documents (epikris/discharge note, services agreement, sworn declaration,
administrative decision) with synthetic PII (valid Luhn personnummer, personnummer-consistent DOB,
SE organisationsnummer/IBAN/+46 phones/addresses). Authored skeletons → no residual real PII →
GDPR-clean, CC-BY. Published PRIVATE; immutable config name. Carries personnummer spans +
``country='SE'`` → enables the national_id_leakage headline.

    python scripts/publish_se_realskeleton.py --n 1500 --private
"""

from __future__ import annotations

import click
from datasets import Dataset

from klusai.privacy.datasets.data.se_skeletons import generate_dataset
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-se-rs")

REPO = "klusai/europriv-bench"
CONFIG = "se-realskeleton-v1"

CARD_NOTE = """

## Swedish config: `se-realskeleton-v1`

A **citable-track candidate** (currently `config_status=dev`; not yet validated — pending
native-speaker review + IAA) and a **decode-bearing measurement** (RES-80, extending the
detection≠re-id dissociation beyond RO/PL/IT): documents that mirror the STRUCTURE and boilerplate
of real Swedish official document types — a discharge note (`Epikris / Utskrivningsmeddelande`), a
services agreement (`Avtal om tjänster`), a sworn declaration (`Försäkran på heder och samvete`),
and an administrative decision (`Beslut`) — populated with **synthetic** Swedish identifiers
(valid-Luhn **personnummer**, **personnummer-consistent date of birth**,
organisationsnummer/IBAN, +46 phones, addresses). Because the skeletons are authored faithful
reproductions of *public document structure* and all identifiers are synthetic, the artifact
carries **no real personal data** and is CC-BY-redistributable.

Every row carries `country="SE"` so the country-dispatched `national_id_leakage` metric validates
and decodes the gold IDs with the **personnummer** validator: a missed (un-redacted) personnummer
deterministically discloses **SEX + DATE_OF_BIRTH** (birth month + day; the bare 10-digit form's
century is carried only by the printed `-`/`+` separator, like the IT codice-fiscale 2-digit year).
All four templates are **one authored skeleton family** sharing a single fill path — a leak headline
from a single template family is not validated generalization, so a second independent template
family is required before this is cited. The discharge note legitimately repeats the patient
personnummer (identity header + `Personnummer (patientidentitet)`); re-identification is counted
**per distinct subject**, so the repeat collapses to one subject (KLU-49 dedup) and never
double-counts.

Pair with `ro-realskeleton-v1`, `pl-realskeleton-v1` and `it-realskeleton-v1`: together they test
whether the train-for-protection result holds on additional decode-bearing identifiers and
languages (here personnummer / Swedish, scored zero-shot for the RO-trained kp-deid).
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
    logger.info("generated %d docs by domain: %s; distinct personnummer subjects: %d",
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
