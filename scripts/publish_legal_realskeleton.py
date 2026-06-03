#!/usr/bin/env python3
"""Publish the legal-domain real-skeleton config (legal-realskeleton-v1) to EuroPriv-Bench (KLU-111).

The under-served, differentiating DOMAIN bet: faithful real-STRUCTURE legal documents — an
EUR-Lex-style legal instrument (recitals → articles → "done at/on"), an ECHR-style court judgment
(caption → ÎN FAPT / ÎN DREPT / PENTRU ACESTE MOTIVE), and a GDPR Article 15 DSAR response — with
synthetic CNP-bearing PII (valid-checksum CNP, CNP-consistent DOB). Authored skeletons reproduce only
the public SECTION LAYOUT of these document types; NO copyrighted EUR-Lex/ECHR source text is
included or redistributed (EUR-Lex reuse under Decision 2011/833/EU is not even relied on; ECHR/HUDOC
reuse is restricted, so no HUDOC text is used). All identifiers are synthetic → GDPR-clean, CC-BY.
Published PRIVATE; immutable config name. Rows carry country='RO' → national_id_leakage dispatches to
the CNP validator (a leaked CNP discloses DATE_OF_BIRTH + SEX + COUNTY).

    python scripts/publish_legal_realskeleton.py --n 1500 --private
"""

from __future__ import annotations

import click
from datasets import Dataset

from klusai.privacy.datasets.data.ro_skeletons_legal import generate_dataset
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("publish-legal-rs")

REPO = "klusai/europriv-bench"
CONFIG = "legal-realskeleton-v1"

CARD_NOTE = """

## Legal-domain config: `legal-realskeleton-v1`

A **citable-track candidate** (currently `config_status=dev`; not yet validated — pending
native-speaker review + IAA) and the program's first **legal-domain** real-skeleton track (KLU-111):
documents that mirror the public **STRUCTURE** of the legal-document types the EU privacy world runs
on — an **EUR-Lex-style legal instrument** (titled act → numbered recitals → numbered articles →
"adoptată la … "), an **ECHR-style court judgment** (case caption `CAUZA … ÎMPOTRIVA ROMÂNIEI`,
application number, then `ÎN FAPT` / `ÎN DREPT` / `PENTRU ACESTE MOTIVE, INSTANȚA`), and a **GDPR
Article 15 DSAR response** (identification → categories of data → recipients → retention → rights) —
populated with **synthetic** Romanian identifiers (valid-checksum **CNP**, CNP-consistent date of
birth, CUI, +40 phones, addresses).

**Cleanly-licensed — structure only, no redistributed text.** These are authored skeletons that
reproduce the (uncopyrightable) public section *layout* of these document types; **no copyrighted
EUR-Lex or ECHR/HUDOC source text is included or redistributed**. EUR-Lex general reuse is authorised
under **Commission Decision 2011/833/EU**, but we do not rely on it (we redistribute no EUR-Lex text);
**ECHR/HUDOC reuse is restricted** ("private use or information and education", `© ECHR-CEDH`;
translations are copyright-protected), so **no HUDOC text is used** — only the judgment structure.
Because all identifiers are synthetic, the artifact carries **no real personal data** and is
CC-BY-redistributable.

Every row carries `country="RO"` so the country-dispatched `national_id_leakage` metric validates and
decodes the gold CNPs with the **CNP** validator: a missed (un-redacted) CNP deterministically
discloses **DATE_OF_BIRTH + SEX + COUNTY**. Re-identification is counted **per distinct subject**
`(document, country, normalized value)` — the DSAR response legitimately repeats the applicant CNP
(identity block + identity-confirmation line), so the repeat collapses to one subject (KLU-49 dedup)
and never double-counts.

All three templates are **one authored skeleton family** (the legal genre, tagged `family="L"`)
sharing a single fill path — a leak headline from a single template family is not validated
generalization, so a **second independent legal template family** is required before this is cited
(the KLU-101 RO hardening, replicated for the legal track). This is a bounded proof-of-concept (1
language, 3 legal document types) proving the EuroPriv-Bench harness generalizes to the **legal
domain** — not a full legal corpus.
"""


@click.command()
@click.option("--n", type=int, default=1500)
@click.option("--seed", type=int, default=20260603)
@click.option("--private/--public", default=True)
def main(n: int, seed: int, private: bool) -> None:
    rows = list(generate_dataset(n, seed=seed))
    by_domain: dict[str, int] = {}
    for r in rows:
        by_domain[r["domain"]] = by_domain.get(r["domain"], 0) + 1
    # Distinct CNP subjects (per-doc dedup) — the denominator the leak-rate is reported over. A CNP
    # is 13 digits; the repeated CNP in a DSAR response dedups to one subject.
    subjects = {
        (i, r["text"][s["start"]:s["end"]])
        for i, r in enumerate(rows) for s in r["spans"]
        if s["label"] == "NATIONAL_ID" and len(r["text"][s["start"]:s["end"]]) == 13
    }
    logger.info("generated %d docs by domain: %s; distinct CNP subjects: %d",
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
