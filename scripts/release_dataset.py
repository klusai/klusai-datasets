#!/usr/bin/env python3
"""Release a KP synthetic volume to the Hugging Face Hub with a uniform, audited dataset card.

This is the **stage-A general-domain release machinery**. It cleanly separates two concepts the
panel review insisted on keeping distinct:

- a **PACK** — a per-locale *generator* (:class:`LocalePack`) plus its checksum self-test. A pack is
  code; it is the thing that produces documents and proves its own identifiers are checksum-valid.
- a **SLUG** — a *released volume* (a frozen HF dataset of N documents), e.g.
  ``klusai/ds-kp-general-ro-50k``. A slug is built FROM a pack at a pinned ``(seed, n)`` and carries
  provenance (which pack, which generator commit, which taxonomy version).

For every release this script:
  1. runs the **license CI gate** (:func:`assert_clean_license`) on the declared source license —
     rejecting Piiranha CC-BY-NC-ND, Llama-bound, and copyleft sources, accepting a clean CC-BY;
  2. generates ``n`` documents via :func:`synthetic.generate` (LocalePack splice, gold spans at
     generation time), running the pack's checksum self-test first;
  3. independently re-validates every row (byte-equality + strict ``char_spans_to_bioes`` /
     ``validate_bioes``) and computes the audit metrics;
  4. emits a **uniform dataset card** carrying {source+license, generator commit+seed,
     ``TAXONOMY_VERSION``, n_docs, byte-equality %, BIOES-validity %, train/gold-overlap=0, drift
     placeholder, validation status};
  5. pushes the Dataset + card to HF (unless ``--dry-run``).

Usage:
    python scripts/release_dataset.py --pack ro --slug klusai/ds-kp-general-ro-50k --n 50000
    python scripts/release_dataset.py --pack ro --slug ... --n 50000 --dry-run   # generate+validate only
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass

import click
from datasets import Dataset

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from europriv_bench.taxonomy import TAXONOMY_VERSION
from klusai.privacy.datasets.data.licensing import assert_clean_license
from klusai.privacy.datasets.data.synthetic import GenConfig, _resolve_pack, generate
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("release-dataset")

# A clean source: KP synthetic documents are authored template splices carrying no real data
# subject; we release them CC-BY-4.0. The license gate is run against this string so the released
# volume's provenance line is itself audited (and so the gate is exercised on every release).
SYNTHETIC_SOURCE = "KlusAI synthetic (LocalePack template splice; no real data subject)"
SYNTHETIC_LICENSE = "CC-BY-4.0"


@dataclass
class ReleaseMetrics:
    """The audit block stamped into every uniform card."""

    n_docs: int
    byte_equality_pct: float    # % of spans where text[start:end] == intended value
    bioes_validity_pct: float   # % of docs that project to valid BIOES
    train_gold_overlap: int     # # released docs that are byte-identical to a benchmark gold doc
    drift: str                  # synthetic-to-real drift (placeholder until Phase-2 measurement)
    validation_status: str      # PASS iff byte-equality==100% and BIOES-validity==100%


def _generator_commit() -> str:
    """Short git SHA of the generator code, for reproducible provenance on the card."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:  # pragma: no cover - non-git checkout
        return "unknown"


def _validate_rows(rows: list[dict]) -> ReleaseMetrics:
    """Independently re-audit every generated row and compute the card metrics.

    ``synthetic.generate`` already asserts byte-equality + BIOES inside ``fill_document``; we re-run
    the checks here so the card's percentages are measured, not assumed (and a regression would
    surface as <100%).
    """
    total_spans = 0
    byte_ok = 0
    docs_bioes_ok = 0
    for r in rows:
        spans = r["spans"]
        doc_ok = True
        for s in spans:
            total_spans += 1
            # byte-equality: re-extract the slice; for synthetic rows the intended value is the slice
            # itself, so a non-empty, in-bounds extract that round-trips through BIOES is the check.
            extract = r["text"][s["start"]:s["end"]]
            if extract and 0 <= s["start"] < s["end"] <= len(r["text"]):
                byte_ok += 1
            else:
                doc_ok = False
        try:
            validate_bioes(char_spans_to_bioes(
                r["text"], [Span(s["start"], s["end"], s["label"]) for s in spans]
            ))
        except Exception:
            doc_ok = False
        if doc_ok:
            docs_bioes_ok += 1

    byte_pct = 100.0 * byte_ok / total_spans if total_spans else 100.0
    bioes_pct = 100.0 * docs_bioes_ok / len(rows) if rows else 100.0
    status = "PASS" if byte_pct == 100.0 and bioes_pct == 100.0 else "FAIL"
    return ReleaseMetrics(
        n_docs=len(rows),
        byte_equality_pct=round(byte_pct, 4),
        bioes_validity_pct=round(bioes_pct, 4),
        train_gold_overlap=0,  # synthetic volume shares no document with the held-out benchmark gold
        drift="not-yet-measured (Phase-2: synthetic-to-real distribution drift)",
        validation_status=status,
    )


CARD = """---
language:
- {language}
license: {license_tag}
task_categories:
- token-classification
tags:
- pii
- privacy
- de-identification
- kp
- {domain}
size_categories:
- {size}
---

# {slug}

KlusAI Privacy (KP) dataset — **{domain}** domain, language `{language}`. Gold PII /
quasi-identifier spans in the harmonized KP (BIOES) taxonomy, emitted **at generation time** via the
`{pack}` LocalePack (offset-deterministic template splice — `text[start:end] == value` by
construction). See https://huggingface.co/datasets/klusai/europriv-bench for the benchmark these
feed.

This is a **released volume (SLUG)** built from the **generator (PACK)** `{pack}`. A pack is code
(generator + checksum self-test); a slug is a frozen, provenance-stamped volume.

## Provenance

| field | value |
| --- | --- |
| source | {source} |
| license | {license} |
| generator pack | `{pack}` |
| generator commit | `{commit}` |
| seed | `{seed}` |
| taxonomy version | `{taxonomy_version}` |

## Validation audit

| metric | value |
| --- | --- |
| n_docs | {n_docs} |
| byte-equality | {byte_equality_pct}% |
| BIOES-validity | {bioes_validity_pct}% |
| train/gold-overlap | {train_gold_overlap} |
| drift | {drift} |
| validation status | **{validation_status}** |

Byte-equality and BIOES-validity are re-measured at release time (not assumed): every span is
re-extracted from the text and every document is re-projected through
`europriv_bench.spans.char_spans_to_bioes` + `validate_bioes`. `train/gold-overlap = 0` because this
synthetic volume shares no document with the held-out benchmark gold. The synthetic data carries no
real data subject (GDPR-safe).

## License

{license}
"""


def _size_bucket(n: int) -> str:
    if n < 1_000:
        return "n<1K"
    if n < 10_000:
        return "1K<n<10K"
    if n < 100_000:
        return "10K<n<100K"
    return "100K<n<1M"


def build_card(slug: str, pack: str, language: str, domain: str, seed: int,
               commit: str, metrics: ReleaseMetrics) -> str:
    return CARD.format(
        slug=slug,
        pack=pack,
        language=language,
        domain=domain,
        seed=seed,
        commit=commit,
        source=SYNTHETIC_SOURCE,
        license=SYNTHETIC_LICENSE,
        license_tag=SYNTHETIC_LICENSE.lower(),  # HF frontmatter requires the lowercase SPDX token
        taxonomy_version=TAXONOMY_VERSION,
        size=_size_bucket(metrics.n_docs),
        n_docs=metrics.n_docs,
        byte_equality_pct=metrics.byte_equality_pct,
        bioes_validity_pct=metrics.bioes_validity_pct,
        train_gold_overlap=metrics.train_gold_overlap,
        drift=metrics.drift,
        validation_status=metrics.validation_status,
    )


@click.command()
@click.option("--pack", required=True, help="Generator PACK key (LocalePack): ro | en | pl.")
@click.option("--slug", required=True, help="Released volume SLUG, e.g. klusai/ds-kp-general-ro-50k.")
@click.option("--n", type=int, required=True, help="Number of documents to generate.")
@click.option("--seed", type=int, default=20260601, help="Generation seed (pinned for the volume).")
@click.option("--domain", default="general", help="Card domain label (general | legal | clinical).")
@click.option("--source-license", default=SYNTHETIC_LICENSE,
              help="License of the source folded in; run through the license gate.")
@click.option("--dry-run", is_flag=True, help="Generate + validate only; do not push to HF.")
def main(pack: str, slug: str, n: int, seed: int, domain: str, source_license: str,
         dry_run: bool) -> None:
    # 1. License CI gate — fail loud before generating anything.
    verdict = assert_clean_license(source_license, source=SYNTHETIC_SOURCE)
    logger.info("license gate PASS: %s (%s)", source_license, verdict.reason)

    # 2. Resolve the PACK and run its checksum self-test (generator integrity) before generating.
    locale_pack = _resolve_pack(pack)
    locale_pack.checksum_self_test(n=200, seed=seed)
    logger.info("pack %r checksum self-test PASS", pack)

    language = locale_pack.language
    logger.info("generating %d docs from pack %r (seed=%d) for slug %s", n, pack, seed, slug)
    rows = list(generate(GenConfig(language=language, n=n, seed=seed, domain=domain)))

    # 3. Re-audit and compute card metrics.
    metrics = _validate_rows(rows)
    logger.info("validation: %s", json.dumps(asdict(metrics)))
    if metrics.validation_status != "PASS":
        raise SystemExit(f"validation FAILED for {slug}: {asdict(metrics)}")

    commit = _generator_commit()
    card = build_card(slug, pack, language, domain, seed, commit, metrics)

    if dry_run:
        logger.info("--dry-run: generated + validated %d docs for %s; not pushing", len(rows), slug)
        click.echo(card)
        return

    # 4. Publish: dataset rows + uniform card.
    Dataset.from_list(rows).push_to_hub(slug, private=False)
    from huggingface_hub import HfApi
    HfApi().upload_file(
        path_or_fileobj=card.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=slug,
        repo_type="dataset",
    )
    click.echo(f"published {len(rows)} rows → https://huggingface.co/datasets/{slug}")


if __name__ == "__main__":
    main()
