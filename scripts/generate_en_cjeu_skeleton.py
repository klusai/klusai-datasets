#!/usr/bin/env python3
"""RES-72 / RES-104 — build the EN CJEU real-skeleton corpus for the decisive TAB transfer test.

The decisive bounded test for the RES-104 win-track: does training xlmr-560m on a REAL
legal-STRUCTURE corpus (CJEU real-skeleton: mined layout signatures + authored connective prose +
checksum-valid synthetic PII) transfer to the TAB real-legal board ZERO-SHOT *better* than generic
synthetic (which caps ~0.30)? This script produces the training corpus for that test.

It reuses the merged, validated generator verbatim
(:func:`klusai.privacy.datasets.data.en_skeletons_legal.generate_dataset`) — gold by construction
(byte-equality + strict BIOES), checksum-valid PII (mod-97 IBAN). It then:
  * re-validates EVERY row (byte-equality + strict BIOES) and counts invalid IBANs — failing loud;
  * computes the unique-document-skeleton ratio with the EXACT RES-94 method (imported from
    ``europriv-bench/analysis/synthetic_realism_gap.py``: ``template_repetition``);
  * writes the JSONL artifact (gitignored — PoC corpus, not pushed to HF) + a metrics JSON.

Single process, one output/log — no concurrency (RES-97 lesson). The generator is NOT LLM-backed so
this is fast.

    python scripts/generate_en_cjeu_skeleton.py --n 20000 --seed 20260608
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import click

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from klusai.privacy.datasets.data import en_skeletons_legal as sk
from klusai.privacy.datasets.data.en_generators import iban_gb_valid
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("en-cjeu-skeleton")

_GAP_PATH = (
    Path(__file__).resolve().parents[2] / "europriv-bench" / "analysis" / "synthetic_realism_gap.py"
)


def _load_gap_module():
    if not _GAP_PATH.exists():
        raise FileNotFoundError(
            f"RES-94 skeleton-ratio script not found at {_GAP_PATH}. The sibling europriv-bench repo "
            "must be checked out next to klusai-datasets so diversity uses the same method."
        )
    spec = importlib.util.spec_from_file_location("synthetic_realism_gap", _GAP_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _validate_row(row: dict) -> None:
    """Fail loud on any gold-integrity violation: byte-equality, strict BIOES, mod-97 IBAN."""
    text = row["text"]
    for s in row["spans"]:
        assert text[s["start"] : s["end"]], "empty span"
        if s["label"] == "IBAN":
            assert iban_gb_valid(
                text[s["start"] : s["end"]]
            ), f"invalid IBAN reached gold: {text[s['start']:s['end']]!r}"
    validate_bioes(
        char_spans_to_bioes(text, [Span(s["start"], s["end"], s["label"]) for s in row["spans"]])
    )


@click.command()
@click.option("--n", type=int, default=20000, help="Corpus size (>=10k per the run brief).")
@click.option("--seed", type=int, default=20260608)
@click.option("--outdir", default="artifacts/europriv", help="Where to write the JSONL + metrics.")
@click.option("--name", default="en_cjeu_skeleton_20k", help="Artifact basename.")
def main(n: int, seed: int, outdir: str, name: str) -> None:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    gap = _load_gap_module()
    sigs = sk.load_signatures()
    logger.info("RES-72: generating %d EN CJEU real-skeleton docs (seed=%d, %d signatures)",
                n, seed, len(sigs))

    t0 = time.time()
    rows: list[dict] = []
    for i, row in enumerate(sk.generate_dataset(n, seed=seed, signatures=sigs)):
        _validate_row(row)  # fail loud on the first misaligned span / invalid IBAN
        rows.append(row)
        if (i + 1) % 2000 == 0:
            logger.info("  ... %d/%d (%.1fs elapsed)", i + 1, n, time.time() - t0)
    dt = time.time() - t0
    logger.info("generated + validated %d rows in %.1fs (%.4fs/doc)",
                len(rows), dt, dt / max(len(rows), 1))

    # ---- gold integrity summary ----------------------------------------------------------------
    iban_spans = [(r, s) for r in rows for s in r["spans"] if s["label"] == "IBAN"]
    invalid_iban = sum(1 for r, s in iban_spans if not iban_gb_valid(r["text"][s["start"] : s["end"]]))
    total_spans = sum(len(r["spans"]) for r in rows)
    labels = sorted({s["label"] for r in rows for s in r["spans"]})
    logger.info("IBAN spans: %d; invalid: %d | total spans: %d | labels: %s",
                len(iban_spans), invalid_iban, total_spans, labels)

    # ---- diversity: RES-94 method --------------------------------------------------------------
    div = gap.template_repetition([{"text": r["text"], "spans": r["spans"]} for r in rows])
    logger.info("unique-skeleton ratio = %.4f  (%d/%d unique, top-share %.4f)",
                div["unique_ratio"], div["unique_skeletons"], div["n_docs"], div["top_skeleton_share"])

    # ---- write artifacts (gitignored — PoC corpus, not pushed to HF) ---------------------------
    jsonl = out / f"{name}.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    metrics = {
        "issue": "RES-72",
        "win_track": "RES-104",
        "config_status": "dev",
        "language": "en",
        "country": "GB",
        "genre": sk.GENRE,
        "approach": "CJEU real-STRUCTURE skeleton: mined layout signatures (structure only) + "
        "authored connective prose + checksum-valid synthetic PII spliced offset-deterministically.",
        "real_pii": False,
        "n": len(rows),
        "seed": seed,
        "n_signatures": len(sigs),
        "seconds": round(dt, 2),
        "seconds_per_doc": round(dt / max(len(rows), 1), 5),
        "labels": labels,
        "total_spans": total_spans,
        "gold_integrity": {
            "iban_spans": len(iban_spans),
            "invalid_iban": invalid_iban,
            "misaligned_spans": 0,  # _validate_row would have raised otherwise
            "all_rows_byte_equal_and_bioes_valid": True,
        },
        "diversity_unique_skeleton_ratio": {
            "method": "europriv-bench analysis/synthetic_realism_gap.py::template_repetition",
            "result": div,
            "generic_synthetic_reference_ratio_res94": 0.004,
        },
    }
    (out / f"{name}_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n"
    )
    logger.info("wrote %s (%d rows) and %s_metrics.json", jsonl, len(rows), name)
    print(json.dumps(
        {"n": len(rows), "diversity": div, "gold_integrity": metrics["gold_integrity"]},
        indent=2, ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
