#!/usr/bin/env python3
"""Curate the EuroPriv-Bench TAB ECHR legal gold config from the Text Anonymization Benchmark.

TAB (Pilán et al., *Computational Linguistics* 48(4):1053-1101, 2022) is 1,268 REAL English ECHR
court judgments, manually annotated — the program's FIRST real-data gold anchor. We map TAB's
``entity_type`` onto the harmonized KP taxonomy via the shared ``tab`` crosswalk, keep DIRECT+QUASI
mentions (preserving ``identifier_type`` for the QI / re-id channel and ``entity_id`` co-reference),
select one canonical annotator per document, resolve nested mentions, and validate every row
byte-equal + strict BIOES via ``europriv_bench.spans`` (fail loud on misalignment).

⚠️ LICENSE: TAB-the-DATA is **MIT** (LICENSE.txt = verbatim MIT; GitHub spdx_id MIT). The
widely-repeated "CC-BY-4.0" is WRONG — CC-BY covers only the journal article, not the corpus. We
cite + tag the gold as **MIT**. Underlying ECHR judgments are upstream Council-of-Europe public
documents (provenance noted in the card / manifest).

    # report-only coverage across all splits (no push):
    python scripts/curate_tab.py --report
    # publish the test split as the held-out gold config:
    python scripts/curate_tab.py --publish --split test --private

Network: downloads echr_{train,dev,test}.json from the TAB GitHub repo (raw).
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from collections import Counter
from pathlib import Path

import click

from klusai.privacy.datasets.data.curate import map_tab_document
from klusai.privacy.datasets.data.licensing import assert_clean_license
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("curate-tab")

REPO = "klusai/europriv-bench"
CONFIG = "tab-echr-legal-en-v1"
LICENSE = "MIT"  # TAB DATA is MIT (NOT CC-BY — that covers only the journal article)
RAW_BASE = "https://raw.githubusercontent.com/NorskRegnesentral/text-anonymization-benchmark/master"
SPLITS = ("train", "dev", "test")

CARD = """---
language:
- en
license: mit
task_categories:
- token-classification
tags:
- pii
- privacy
- de-identification
- kp
- legal
- echr
- real-data
size_categories:
- n<1K
---

# EuroPriv-Bench — TAB ECHR legal gold (`tab-echr-legal-en-v1`)

The **first real-data gold config** of [EuroPriv-Bench](https://github.com/klusai/europriv-bench):
real English ECHR court judgments with **manually-annotated, peer-reviewed** privacy spans, remapped
to the harmonized KP (BIOES) taxonomy. A step up from synthetic `dev` configs — this is REAL,
externally-annotated human gold (it does NOT depend on the native-speaker IAA gate the synthetic
real-skeletons need).

Each row: `text`, `spans` (`{start, end, label, identifier_type, entity_id}`; KP labels;
`identifier_type` ∈ {DIRECT, QUASI} = the re-identification / residual-distinctiveness signal;
`entity_id` = TAB co-reference), `language` (`en`), `doc_id`, `annotator`.

```python
from datasets import load_dataset
ds = load_dataset("klusai/europriv-bench", "tab-echr-legal-en-v1", split="test")
```

## Source & license

Derived from the **Text Anonymization Benchmark (TAB)** — Pilán, Lison, Øvrelid, Papadopoulou,
Sánchez & Batet, *The Text Anonymization Benchmark (TAB): A Dedicated Corpus and Evaluation
Framework for Text Anonymization*, **Computational Linguistics 48(4):1053-1101 (2022)** —
distributed at <https://github.com/NorskRegnesentral/text-anonymization-benchmark>.

> **License is MIT, not CC-BY.** The TAB *data* (the `echr_*.json` corpus) is released under the
> **MIT License** (`LICENSE.txt` = verbatim MIT; the GitHub repo's SPDX id is MIT). The often-cited
> "CC-BY-4.0" applies only to the journal *article* via the ACL Anthology — NOT to the corpus.
> Cite the data as MIT.

The underlying judgments are public European Court of Human Rights documents (© Council of Europe /
ECHR-CEDH, available via HUDOC). TAB redistributes them under MIT; no additional redistribution
restriction is introduced here. The KP remap keeps only DIRECT/QUASI mentions (NO_MASK dropped) and
selects one canonical annotator per document; native TAB types DEM/QUANTITY/MISC have no clean KP
type and are dropped (counted, not silently truncated). See `conf/tab_echr_manifest.yaml` in
`klusai-datasets` for the full crosswalk, checksums, and coverage.
"""


def _download(split: str, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    dst = cache / f"echr_{split}.json"
    if not dst.exists():
        url = f"{RAW_BASE}/echr_{split}.json"
        logger.info("downloading %s -> %s", url, dst)
        urllib.request.urlretrieve(url, dst)  # noqa: S310 (trusted GitHub raw host)
    return dst


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def curate_split(path: Path) -> tuple[list[dict], dict]:
    """Curate one TAB split file → (rows, stats). Rows that don't align are dropped + counted."""
    docs = json.loads(path.read_text(encoding="utf-8"))
    dropped: Counter = Counter()
    kept_labels: Counter = Counter()
    idtypes: Counter = Counter()
    rows: list[dict] = []
    misaligned: list[str] = []
    for doc in docs:
        try:
            row = map_tab_document(doc, dropped=dropped)
        except ValueError as e:
            misaligned.append(doc.get("doc_id", "?"))
            logger.warning("dropping misaligned doc %s: %s", doc.get("doc_id"), e)
            continue
        for s in row["spans"]:
            kept_labels[s["label"]] += 1
            idtypes[s["identifier_type"]] += 1
        rows.append(row)
    stats = {
        "input_docs": len(docs),
        "rows": len(rows),
        "spans": sum(len(r["spans"]) for r in rows),
        "kept_labels": dict(kept_labels.most_common()),
        "identifier_type": dict(idtypes.most_common()),
        "dropped_unmapped_entity_type": dict(dropped.most_common()),
        "misaligned_docs_dropped": misaligned,
    }
    return rows, stats


def _rows_sha256(rows: list[dict]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@click.command()
@click.option("--cache", default="artifacts/tab", help="Where to cache downloaded TAB JSON.")
@click.option("--report", is_flag=True, help="Curate all splits + print coverage; do not push.")
@click.option("--publish", is_flag=True, help="Push the chosen split as the gold config.")
@click.option("--split", default="test", type=click.Choice(SPLITS), help="Split to publish.")
@click.option("--private/--public", default=True, help="Publish private (default) or public.")
@click.option("--out", default=None, help="Also write the curated split JSONL here.")
def main(cache: str, report: bool, publish: bool, split: str, private: bool, out: str | None) -> None:
    # License gate FIRST — MIT must pass (and is recorded MIT, never CC-BY).
    verdict = assert_clean_license(LICENSE, source="tab-echr (NorskRegnesentral)")
    logger.info("license gate: %s — %s", LICENSE, verdict.reason)

    cache_dir = Path(cache)
    all_stats: dict[str, dict] = {}
    files = {s: _download(s, cache_dir) for s in SPLITS}
    for s in SPLITS:
        rows, stats = curate_split(files[s])
        stats["file_sha256"] = _sha256(files[s])
        stats["rows_sha256"] = _rows_sha256(rows)
        all_stats[s] = stats
        logger.info("%s: %d/%d docs, %d spans, dropped_unmapped=%s, misaligned=%d",
                    s, stats["rows"], stats["input_docs"], stats["spans"],
                    stats["dropped_unmapped_entity_type"], len(stats["misaligned_docs_dropped"]))

    if report or not publish:
        click.echo(json.dumps(all_stats, ensure_ascii=False, indent=2))

    rows, _ = curate_split(files[split])
    if out:
        op = Path(out)
        op.parent.mkdir(parents=True, exist_ok=True)
        with op.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        click.echo(f"wrote {len(rows)} rows -> {op}")

    if publish:
        from datasets import Dataset
        from huggingface_hub import HfApi

        ds = Dataset.from_list(rows)
        ds.push_to_hub(REPO, config_name=CONFIG, split=split, private=private)
        HfApi().upload_file(
            path_or_fileobj=CARD.encode("utf-8"),
            path_in_repo=f"README_{CONFIG}.md",
            repo_id=REPO,
            repo_type="dataset",
        )
        click.echo(f"published {len(rows)} rows → {REPO} config={CONFIG} split={split}")


if __name__ == "__main__":
    main()
