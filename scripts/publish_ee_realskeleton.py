#!/usr/bin/env python3
"""Publish the Estonian real-skeleton config (ee-realskeleton-v1) to EuroPriv-Bench.

A citable-track candidate (config_status=dev; not yet validated — pending native-speaker review +
IAA) and a decode-bearing measurement (RES-84, after RO/CNP, PL/PESEL, IT/codice-fiscale, SE/CZ,
DK/FI): faithful real-structure documents (epikriis/discharge summary, services agreement, sworn
declaration, administrative decision) with synthetic PII (checksum-valid isikukood, isikukood-
consistent DOB, registrikood/IBAN/+372 phones/addresses). Authored skeletons → no residual real PII →
GDPR-clean, CC-BY. Published PRIVATE; immutable config name. Carries isikukood spans +
``country='EE'`` → enables the national_id_leakage headline.

    python scripts/publish_ee_realskeleton.py --n 1500 --private
"""

from __future__ import annotations

import click
from datasets import Dataset

from klusai.privacy.datasets.data.ee_skeletons import generate_dataset
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-ee-rs")

REPO = "klusai/europriv-bench"
CONFIG = "ee-realskeleton-v1"

CARD_NOTE = """

## Estonian config: `ee-realskeleton-v1`

A **citable-track candidate** (currently `config_status=dev`; not yet validated — pending
native-speaker review + IAA) and a **decode-bearing measurement** (RES-84, extending the
detection≠re-id dissociation beyond RO/PL/IT/SE/CZ/DK/FI): documents that mirror the STRUCTURE and
boilerplate of real Estonian official document types — a discharge summary (`Epikriis`), a services
agreement (`Teenuste osutamise leping`), a sworn declaration (`Kinnitus`), and an administrative
decision (`Otsus`) — populated with **synthetic** Estonian identifiers (checksum-valid **isikukood**,
**isikukood-consistent date of birth**, registrikood/IBAN, +372 phones, addresses). Because the
skeletons are authored faithful reproductions of *public document structure* and all identifiers are
synthetic, the artifact carries **no real personal data** and is CC-BY-redistributable.

Every row carries `country="EE"` so the country-dispatched `national_id_leakage` metric validates
and decodes the gold IDs with the **isikukood** validator: a missed (un-redacted) isikukood
deterministically discloses **DATE_OF_BIRTH + SEX** (the full date is recoverable — the century comes
from the 1st digit; the same digit's parity gives sex; the final digit is an ISO-7064-style two-pass
mod-11 check). All four templates are **one authored skeleton family** sharing a single fill path — a
leak headline from a single template family is not validated generalization, so a second independent
template family is required before this is cited. The discharge summary legitimately repeats the
patient isikukood (identity header + `Isikukood (patsiendi identifikaator)`); re-identification is
counted **per distinct subject**, so the repeat collapses to one subject (KLU-49 dedup) and never
double-counts. EE/LT/LV share the id structure, so the validator is country-keyed and never
auto-detects, and the only national id emitted is the isikukood (the 8-digit registrikood is
structurally disjoint and never mis-decodes as a re-id subject).

Pair with `lt-realskeleton-v1` and the SE/CZ/DK/FI + RO/PL/IT configs: together they test whether the
train-for-protection result holds on additional decode-bearing identifiers and languages (here
isikukood / Estonian, scored zero-shot for the RO-trained kp-deid).
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
    logger.info("generated %d docs by domain: %s; distinct isikukood subjects: %d",
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
