#!/usr/bin/env python3
"""Publish the Polish real-skeleton config (pl-realskeleton-v1) to EuroPriv-Bench.

A citable-track candidate (config_status=dev; not yet validated — pending native-speaker review +
IAA, KLU-27) and the SECOND, zero-shot decode-bearing measurement (after RO/CNP): faithful
real-structure documents (hospital discharge card `KARTA INFORMACYJNA LECZENIA SZPITALNEGO`,
services contract `UMOWA O ŚWIADCZENIE USŁUG`, declaration `OŚWIADCZENIE`, administrative letter)
with synthetic PII (valid PESEL, PESEL-consistent DOB, PL NIP/REGON/IBAN/dowód/addresses).
Authored skeletons → no residual real PII → GDPR-clean, CC-BY. Published PRIVATE; immutable config
name. Carries PESEL spans + ``country='PL'`` → enables the national_id_leakage headline.

    python scripts/publish_pl_realskeleton.py --n 1500 --private
"""

from __future__ import annotations

import click
from datasets import Dataset

from klusai.privacy.datasets.data.pl_skeletons import generate_dataset
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-pl-rs")

REPO = "klusai/europriv-bench"
CONFIG = "pl-realskeleton-v1"

CARD_NOTE = """

## Polish config: `pl-realskeleton-v1`

A **citable-track candidate** (currently `config_status=dev`; not yet validated — pending
native-speaker review + IAA, KLU-27) and the **second, zero-shot decode-bearing measurement**
(after `ro-realskeleton-v1`): documents that mirror the STRUCTURE and boilerplate of real Polish
official document types — the hospital discharge card `KARTA INFORMACYJNA LECZENIA SZPITALNEGO`, a
services contract `UMOWA O ŚWIADCZENIE USŁUG`, a declaration `OŚWIADCZENIE`, and an administrative
letter — populated with **synthetic** Polish identifiers (valid-checksum **PESEL**,
**PESEL-consistent date of birth**, NIP/REGON/IBAN, dowód osobisty, addresses, +48 phones), with
Polish gender agreement. Because the skeletons are authored faithful reproductions of *public
document structure* (Polish official documents/materials — *dokumenty i materiały urzędowe* — are
excluded from copyright under Art. 4 of the Polish Copyright Act, ustawa o prawie autorskim i
prawach pokrewnych; the document *structure* is therefore non-copyright) and all identifiers are
synthetic, the artifact carries **no real personal data** and is CC-BY-redistributable.

Every row carries `country="PL"` so the country-dispatched `national_id_leakage` metric validates
and decodes the gold IDs with the **PESEL** validator (a missed PESEL deterministically discloses
DATE_OF_BIRTH + SEX). The protection result here is **zero-shot**: `kp-deid-mdeberta-280m` leaks
0% PESEL on PL despite being RO-trained and never having seen Polish (zero-shot transfer, not
PL-trained performance). The protection-vs-leak contrast on PL is carried by **GLiNER (~58%)** and
**tabularisai (~31%)**; note `openai/privacy-filter` also leaks ~0% PESEL on PL, so the
"type-accurate detectors leak" story holds for **2 of 4** baselines here, not universally. All four
templates are **one authored skeleton family** sharing a single fill path — a leak headline from a
single template family is not validated generalization, so a second independent template family is
required before this is cited. The discharge card legitimately repeats the patient PESEL (identity
header + `Identyfikator pacjenta`); re-identification is counted **per distinct subject**, so the
repeat collapses to one subject (KLU-49 dedup) and never double-counts.

Pair with `ro-realskeleton-v1` (the first decode-bearing track): together they test whether the
train-for-protection result holds on a SECOND identifier (PESEL) in a SECOND language (PL).
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
    # Distinct PESEL subjects (per-doc dedup) — the denominator the leak-rate is reported over.
    subjects = {
        (i, r["text"][s["start"]:s["end"]])
        for i, r in enumerate(rows) for s in r["spans"]
        if s["label"] == "NATIONAL_ID" and r["text"][s["start"]:s["end"]].isdigit()
        and len(r["text"][s["start"]:s["end"]]) == 11
    }
    logger.info("generated %d docs by domain: %s; distinct PESEL subjects: %d",
                len(rows), by_domain, len(subjects))
    Dataset.from_list(rows).push_to_hub(REPO, config_name=CONFIG, split="test", private=private)

    from huggingface_hub import DatasetCard
    card = DatasetCard.load(REPO, repo_type="dataset")
    if "pl-realskeleton-v1" not in (card.text or ""):
        card.text = (card.text or "") + CARD_NOTE
    card.push_to_hub(REPO, repo_type="dataset")
    logger.info("pushed config %s (%d rows, private=%s)", CONFIG, len(rows), private)


if __name__ == "__main__":
    main()
