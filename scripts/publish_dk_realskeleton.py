#!/usr/bin/env python3
"""Publish the Danish real-skeleton config (dk-realskeleton-v1) to EuroPriv-Bench.

A citable-track candidate (config_status=dev; not yet validated — pending native-speaker review +
IAA) and a decode-bearing measurement (RES-83, after RO/CNP, PL/PESEL, IT/codice-fiscale, SE/CZ):
faithful real-structure documents (udskrivningsbrev/discharge summary, services agreement, sworn
declaration, administrative decision) with synthetic PII (format/century-valid CPR-nummer,
CPR-consistent DOB, CVR-nummer/IBAN/+45 phones/addresses). Authored skeletons → no residual real
PII → GDPR-clean, CC-BY. Published PRIVATE; immutable config name. Carries CPR spans +
``country='DK'`` → enables the national_id_leakage headline.

    python scripts/publish_dk_realskeleton.py --n 1500 --private
"""

from __future__ import annotations

import click
from datasets import Dataset

from klusai.privacy.datasets.data.dk_skeletons import generate_dataset
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-dk-rs")

REPO = "klusai/europriv-bench"
CONFIG = "dk-realskeleton-v1"

CARD_NOTE = """

## Danish config: `dk-realskeleton-v1`

A **citable-track candidate** (currently `config_status=dev`; not yet validated — pending
native-speaker review + IAA) and a **decode-bearing measurement** (RES-83, extending the
detection≠re-id dissociation beyond RO/PL/IT/SE/CZ): documents that mirror the STRUCTURE and
boilerplate of real Danish official document types — a discharge summary (`Udskrivningsbrev /
Epikrise`), a services agreement (`Aftale om tjenesteydelser`), a sworn declaration (`Erklæring på
tro og love`), and an administrative decision (`Afgørelse`) — populated with **synthetic** Danish
identifiers (format/century-valid **CPR-nummer**, **CPR-consistent date of birth**, CVR-nummer/IBAN,
+45 phones, addresses). Because the skeletons are authored faithful reproductions of *public
document structure* and all identifiers are synthetic, the artifact carries **no real personal
data** and is CC-BY-redistributable.

Every row carries `country="DK"` so the country-dispatched `national_id_leakage` metric validates
and decodes the gold IDs with the **CPR-nummer** validator: a missed (un-redacted) CPR
deterministically discloses **DATE_OF_BIRTH + SEX** (the full date is recoverable — the century
comes from the 7th-digit/YY CPR-kontoret table; the last-digit parity gives sex). NOTE: the
historical **mod-11 check was abolished in 2007** (the day's sequence numbers ran out), so a valid
CPR is **format + century-table + plausible date**, NOT a checksum. All four templates are **one
authored skeleton family** sharing a single fill path — a leak headline from a single template
family is not validated generalization, so a second independent template family is required before
this is cited. The discharge summary legitimately repeats the patient CPR (identity header +
`CPR-nummer (patientidentitet)`); re-identification is counted **per distinct subject**, so the
repeat collapses to one subject (KLU-49 dedup) and never double-counts.

Pair with `se-realskeleton-v1` / `cz-realskeleton-v1` and the RO/PL/IT configs: together they test
whether the train-for-protection result holds on additional decode-bearing identifiers and
languages (here CPR-nummer / Danish, scored zero-shot for the RO-trained kp-deid).
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
    logger.info("generated %d docs by domain: %s; distinct CPR subjects: %d",
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
