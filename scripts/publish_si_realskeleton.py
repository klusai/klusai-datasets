#!/usr/bin/env python3
"""Publish the Slovenian real-skeleton config (si-realskeleton-v1) to EuroPriv-Bench.

A citable-track candidate (config_status=dev; not yet validated — pending native-speaker review +
IAA) and a decode-bearing measurement (RES-85, after RO/CNP, PL/PESEL, IT/codice-fiscale, SE/CZ,
DK/FI, EE/LT): faithful real-structure documents (odpustnica/discharge summary, services agreement,
sworn declaration, administrative decision) with synthetic PII (checksum-valid EMŠO, EMŠO-consistent
DOB, davčna številka/IBAN/+386 phones/addresses). Authored skeletons → no residual real PII →
GDPR-clean, CC-BY. Published PRIVATE; immutable config name. Carries EMŠO spans + ``country='SI'`` →
enables the national_id_leakage headline. EMŠO is a RICHER surface than the Baltic family — it also
discloses REGION OF BIRTH.

    python scripts/publish_si_realskeleton.py --n 1500 --private
"""

from __future__ import annotations

import click
from datasets import Dataset

from klusai.privacy.datasets.data.si_skeletons import generate_dataset
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-si-rs")

REPO = "klusai/europriv-bench"
CONFIG = "si-realskeleton-v1"

CARD_NOTE = """

## Slovenian config: `si-realskeleton-v1`

A **citable-track candidate** (currently `config_status=dev`; not yet validated — pending
native-speaker review + IAA) and a **decode-bearing measurement** (RES-85, extending the
detection≠re-id dissociation beyond RO/PL/IT/SE/CZ/DK/FI/EE/LT): documents that mirror the STRUCTURE
and boilerplate of real Slovenian official document types — a discharge summary (`Odpustnica`), a
services agreement (`Pogodba o opravljanju storitev`), a sworn declaration (`Izjava`), and an
administrative decision (`Odločba`) — populated with **synthetic** Slovenian identifiers
(checksum-valid **EMŠO**, **EMŠO-consistent date of birth**, davčna številka/IBAN, +386 phones,
addresses). Because the skeletons are authored faithful reproductions of *public document structure*
and all identifiers are synthetic, the artifact carries **no real personal data** and is
CC-BY-redistributable.

Every row carries `country="SI"` so the country-dispatched `national_id_leakage` metric validates and
decodes the gold IDs with the **EMŠO** validator: a missed (un-redacted) EMŠO deterministically
discloses **DATE_OF_BIRTH + SEX + REGION_OF_BIRTH** — a **richer surface** than the Baltic family (it
also leaks region of birth, like the IT codice fiscale's place). The full date is recoverable (the
ex-YU century convention makes the 3-digit year unambiguous); the serial encodes sex (000–499 male /
500–999 female); the RR field is the region of birth (50 = Slovenia); the final digit is a weighted
mod-11 check. All four templates are **one authored skeleton family** sharing a single fill path — a
leak headline from a single template family is not validated generalization, so a second independent
template family is required before this is cited. The discharge summary legitimately repeats the
patient EMŠO (identity header + `EMŠO (identifikator pacienta)`); re-identification is counted **per
distinct subject**, so the repeat collapses to one subject (KLU-49 dedup) and never double-counts.
Every ex-YU country shares the EMŠO/JMBG structure, so the validator is country-keyed (RR encodes the
country) and never auto-detects; the only national id emitted is the Slovenian EMŠO (the 8-digit
davčna številka is structurally disjoint and never mis-decodes as a re-id subject).

Pair with `sk-realskeleton-v1` and the EE/LT + SE/CZ/DK/FI + RO/PL/IT configs: together they test
whether the train-for-protection result holds on additional decode-bearing identifiers and languages
(here EMŠO / Slovenian, scored zero-shot for the RO-trained kp-deid).
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
    logger.info("generated %d docs by domain: %s; distinct EMŠO subjects: %d",
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
