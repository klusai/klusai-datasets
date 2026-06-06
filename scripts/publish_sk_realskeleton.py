#!/usr/bin/env python3
"""Publish the Slovak real-skeleton config (sk-realskeleton-v1) to EuroPriv-Bench.

A citable-track candidate (config_status=dev; not yet validated — pending native-speaker review +
IAA) and a decode-bearing measurement (RES-85, after RO/CNP, PL/PESEL, IT/codice-fiscale, SE/CZ,
DK/FI, EE/LT): faithful real-structure documents (prepúšťacia správa/discharge summary, services
agreement, sworn declaration, administrative decision) with synthetic PII (checksum-valid rodné číslo,
rodné-číslo-consistent DOB, IČO/IBAN/+421 phones/addresses). Authored skeletons → no residual real PII
→ GDPR-clean, CC-BY. Published PRIVATE; immutable config name. Carries rodné-číslo spans +
``country='SK'`` → enables the national_id_leakage headline. SK uses the SAME algorithm as CZ.

    python scripts/publish_sk_realskeleton.py --n 1500 --private
"""

from __future__ import annotations

import click
from datasets import Dataset

from klusai.privacy.datasets.data.sk_skeletons import generate_dataset
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-sk-rs")

REPO = "klusai/europriv-bench"
CONFIG = "sk-realskeleton-v1"

CARD_NOTE = """

## Slovak config: `sk-realskeleton-v1`

A **citable-track candidate** (currently `config_status=dev`; not yet validated — pending
native-speaker review + IAA) and a **decode-bearing measurement** (RES-85, extending the
detection≠re-id dissociation beyond RO/PL/IT/SE/CZ/DK/FI/EE/LT): documents that mirror the STRUCTURE
and boilerplate of real Slovak official document types — a discharge summary (`Prepúšťacia správa`), a
services agreement (`Zmluva o poskytovaní služieb`), a sworn declaration (`Čestné vyhlásenie`), and an
administrative decision (`Rozhodnutie`) — populated with **synthetic** Slovak identifiers
(checksum-valid **rodné číslo**, **rodné-číslo-consistent date of birth**, IČO/IBAN, +421 phones,
addresses). Because the skeletons are authored faithful reproductions of *public document structure*
and all identifiers are synthetic, the artifact carries **no real personal data** and is
CC-BY-redistributable.

Every row carries `country="SK"` so the country-dispatched `national_id_leakage` metric validates and
decodes the gold IDs with the **SK rodné-číslo** validator: a missed (un-redacted) rodné číslo
deterministically discloses **DATE_OF_BIRTH + SEX** (the modern 10-digit form is fully date-recoverable
— female month +50; YY-century convention; the whole 10-digit number is divisible by 11). The Slovak
rodné číslo uses the **IDENTICAL algorithm as the Czech one** (SK Zákon č. 301/2000 Z. z. / the shared
Czechoslovak Zákon č. 133/2000 Sb. scheme), so the SK validator reuses the CZ decoder verbatim, tagged
SK. All four templates are **one authored skeleton family** sharing a single fill path — a leak
headline from a single template family is not validated generalization, so a second independent
template family is required before this is cited. The discharge summary legitimately repeats the
patient rodné číslo (identity header + `Rodné číslo (identifikátor pacienta)`); re-identification is
counted **per distinct subject**, so the repeat collapses to one subject (KLU-49 dedup) and never
double-counts. A CZ and an SK rodné číslo are structurally **identical** — only the row `country` tag
distinguishes them; the validator is country-keyed and never auto-detects, so an SK number is decoded
as SK (never mis-dispatched as CZ, or vice-versa). The only national id emitted is the rodné číslo
(the 8-digit IČO is structurally disjoint and never mis-decodes as a re-id subject).

Pair with `si-realskeleton-v1` and the EE/LT + SE/CZ/DK/FI + RO/PL/IT configs: together they test
whether the train-for-protection result holds on additional decode-bearing identifiers and languages
(here rodné číslo / Slovak, scored zero-shot for the RO-trained kp-deid).
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
