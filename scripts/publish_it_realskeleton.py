#!/usr/bin/env python3
"""Publish the Italian real-skeleton config (it-realskeleton-v1) to EuroPriv-Bench.

A citable-track candidate (config_status=dev; not yet validated — pending native-speaker review +
IAA) and the THIRD decode-bearing measurement (after RO/CNP and PL/PESEL): faithful real-structure
documents (discharge letter `LETTERA DI DIMISSIONE OSPEDALIERA`, services contract `CONTRATTO DI
PRESTAZIONE DI SERVIZI`, self-declaration `DICHIARAZIONE SOSTITUTIVA DI CERTIFICAZIONE`,
administrative letter) with synthetic PII (valid-checksum **codice fiscale** — base AND omocode
forms, CF-consistent DOB, partita IVA / IBAN / +39 phones / addresses), Italian gender agreement.
Authored skeletons → no residual real PII → GDPR-clean, CC-BY. Published PRIVATE; immutable config
name. Carries CF spans + ``country='IT'`` → enables the national_id_leakage headline, where a leaked
CF discloses DATE_OF_BIRTH + SEX + PLACE_OF_BIRTH (the richest of the three identifiers).

    python scripts/publish_it_realskeleton.py --n 1500 --private
"""

from __future__ import annotations

import click
from datasets import Dataset

from klusai.privacy.datasets.data.it_skeletons import generate_dataset
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-it-rs")

REPO = "klusai/europriv-bench"
CONFIG = "it-realskeleton-v1"

CARD_NOTE = """

## Italian config: `it-realskeleton-v1`

A **citable-track candidate** (currently `config_status=dev`; not yet validated — pending
native-speaker review + IAA) and the **third decode-bearing measurement** (after `ro-realskeleton-v1`
and `pl-realskeleton-v1`): documents that mirror the STRUCTURE and boilerplate of real Italian
official document types — a hospital discharge letter `LETTERA DI DIMISSIONE OSPEDALIERA`, a services
contract `CONTRATTO DI PRESTAZIONE DI SERVIZI`, a self-declaration (autocertificazione) `DICHIARAZIONE
SOSTITUTIVA DI CERTIFICAZIONE`, and an administrative letter — populated with **synthetic** Italian
identifiers (valid-checksum **codice fiscale**, **CF-consistent date of birth**, partita IVA, Italian
IBAN, +39 phones, addresses), with Italian gender agreement. Because the skeletons are authored
faithful reproductions of *public document structure* and all identifiers are synthetic, the artifact
carries **no real personal data** and is CC-BY-redistributable (no scraped real Italian documents).

Every row carries `country="IT"` so the country-dispatched `national_id_leakage` metric validates and
decodes the gold IDs with the **codice fiscale** validator. The codice fiscale is the **richest** of
the three decode-bearing identifiers: a missed (un-redacted) CF deterministically discloses
**DATE_OF_BIRTH + SEX + PLACE_OF_BIRTH** (the Belfiore comune/country of birth), so the
re-identification leak counts place-of-birth, not just DOB+sex.

**Omocodia.** When two people would collide, the tax authority substitutes the variable numeric
positions with designated letters; a documented fraction (~17%) of subjects therefore carry an
*omocode* CF. The benchmark decoder reverses omocodia before decoding, so a leaked omocode discloses
the same quasi-identifiers as a leaked base CF — the leak is not fooled by the letter substitution.
Place-of-birth is decoded against a **pinned, versioned Belfiore snapshot** (`belfiore` module);
foreign-born CFs (`Z`+country) resolve to a country (a coarser place disclosure than a comune).

All four templates are **one authored skeleton family** sharing a single fill path — a leak headline
from a single template family is not validated generalization, so a second independent template family
is required before this is cited (the KLU-101 RO hardening, replicated for IT). The discharge letter
legitimately repeats the patient CF (identity header + `Identificativo paziente (CF)`);
re-identification is counted **per distinct subject**, so the repeat collapses to one subject (KLU-49
dedup) and never double-counts.

Together with `ro-realskeleton-v1` (CNP) and `pl-realskeleton-v1` (PESEL) this measures the
detection≠re-identification dissociation across **3 identifiers in 3 languages** (RO/PL/IT).
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
    # Distinct codice-fiscale subjects (per-doc dedup) — the denominator the leak-rate is reported
    # over. A CF is 16 alphanumeric chars (the repeated CF in a discharge letter dedups to one).
    subjects = {
        (i, r["text"][s["start"]:s["end"]])
        for i, r in enumerate(rows) for s in r["spans"]
        if s["label"] == "NATIONAL_ID" and len(r["text"][s["start"]:s["end"]]) == 16
    }
    logger.info("generated %d docs by domain: %s; distinct CF subjects: %d",
                len(rows), by_domain, len(subjects))
    Dataset.from_list(rows).push_to_hub(REPO, config_name=CONFIG, split="test", private=private)

    from huggingface_hub import DatasetCard
    card = DatasetCard.load(REPO, repo_type="dataset")
    if "it-realskeleton-v1" not in (card.text or ""):
        card.text = (card.text or "") + CARD_NOTE
    card.push_to_hub(REPO, repo_type="dataset")
    logger.info("pushed config %s (%d rows, private=%s)", CONFIG, len(rows), private)


if __name__ == "__main__":
    main()
