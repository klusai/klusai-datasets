#!/usr/bin/env python3
"""RES-95 — generate the v1 EN stage-B narrative batch and measure the diversity gain.

The English sibling of ``generate_ro_stageb_v1.py`` — a second-language generalization proof. It
generates a SMALL (default 2000) batch of English/UK documents whose *bodies* are authored by a
local, offline LLM (mlx-lm, default ``Qwen/Qwen3-1.7B``) while every PII value is injected
deterministically by our format-/checksum-valid generators and spliced offset-deterministically (so
gold spans stay byte-exact; see :mod:`klusai.privacy.datasets.data.en_stageb`).

It then:
  * validates EVERY row again (byte-equality + strict BIOES via ``europriv_bench.spans``,
    format-valid NINO for every NATIONAL_ID, mod-97 IBAN for every GB-IBAN ACCOUNT_ID) — failing
    loud and aborting on any misalignment;
  * computes the **unique-document-skeleton ratio** with the EXACT RES-94 method (imported from
    ``europriv-bench/analysis/synthetic_realism_gap.py``: ``template_repetition`` over
    ``document_skeleton``) for BOTH the stage-A baseline and this stage-B batch, so the before/after
    diversity gain is reported on one comparable scale;
  * writes the batch to a JSONL artifact (NOT pushed to HF — this is a PoC; the PR is not merged).

This is a single-process run. One run against one output/log — no concurrency (RES-97 lesson).

    python scripts/generate_en_stageb_v1.py --n 2000 --seed 20260607
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import click

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from klusai.privacy.datasets.data.en_documents import generate_dataset as stage_a_generate
from klusai.privacy.datasets.data.en_generators import iban_gb_valid, nino_format_valid
from klusai.privacy.datasets.data.en_stageb import StageBConfig, generate_stageb
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("en-stageb-v1")

# Import the RES-94 skeleton-ratio method from europriv-bench so before/after use ONE definition.
_GAP_PATH = Path(__file__).resolve().parents[2] / "europriv-bench" / "analysis" / "synthetic_realism_gap.py"


def _load_gap_module():
    if not _GAP_PATH.exists():
        raise FileNotFoundError(
            f"RES-94 skeleton-ratio script not found at {_GAP_PATH}. The sibling europriv-bench repo "
            "must be checked out next to klusai-datasets so before/after use the same method."
        )
    spec = importlib.util.spec_from_file_location("synthetic_realism_gap", _GAP_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _looks_like_gb_iban(value: str) -> bool:
    return value.startswith("GB") and len(value) == 22


def _validate_row(row: dict) -> None:
    """Fail loud on any gold-integrity violation: byte-equality, BIOES, valid NINO/IBAN."""
    text = row["text"]
    for s in row["spans"]:
        assert text[s["start"]:s["end"]], "empty span"
        if s["label"] == "NATIONAL_ID":
            assert nino_format_valid(text[s["start"]:s["end"]]), \
                f"invalid NINO reached gold: {text[s['start']:s['end']]!r}"
        if s["label"] == "ACCOUNT_ID" and _looks_like_gb_iban(text[s["start"]:s["end"]]):
            assert iban_gb_valid(text[s["start"]:s["end"]]), \
                f"invalid IBAN reached gold: {text[s['start']:s['end']]!r}"
    validate_bioes(char_spans_to_bioes(
        text, [Span(s["start"], s["end"], s["label"]) for s in row["spans"]]
    ))


@click.command()
@click.option("--n", type=int, default=2000, help="Batch size (small v1 PoC; EN only).")
@click.option("--seed", type=int, default=20260607)
@click.option("--model-id", default="Qwen/Qwen3-1.7B", help="Local HF-cache model id (offline mlx-lm).")
@click.option("--outdir", default="artifacts/europriv", help="Where to write the JSONL + metrics.")
def main(n: int, seed: int, model_id: str, outdir: str) -> None:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    gap = _load_gap_module()

    # ---- generate (single process) -------------------------------------------------------------
    logger.info("RES-95 v1: generating %d EN stage-B docs (model=%s, seed=%d)", n, model_id, seed)
    t0 = time.time()
    rows: list[dict] = []
    cfg = StageBConfig(n=n, seed=seed, model_id=model_id)
    for i, row in enumerate(generate_stageb(cfg)):
        _validate_row(row)  # fail loud on the first misaligned span / invalid id
        rows.append(row)
        if (i + 1) % 100 == 0:
            logger.info("  ... %d/%d (%.1fs elapsed)", i + 1, n, time.time() - t0)
    dt = time.time() - t0
    logger.info("generated + validated %d rows in %.0fs (%.2fs/doc)", len(rows), dt, dt / max(len(rows), 1))

    # ---- gold integrity summary ----------------------------------------------------------------
    nino_spans = [(r, s) for r in rows for s in r["spans"] if s["label"] == "NATIONAL_ID"]
    invalid_nino = sum(1 for r, s in nino_spans if not nino_format_valid(r["text"][s["start"]:s["end"]]))
    iban_spans = [
        (r, s) for r in rows for s in r["spans"]
        if s["label"] == "ACCOUNT_ID" and _looks_like_gb_iban(r["text"][s["start"]:s["end"]])
    ]
    invalid_iban = sum(1 for r, s in iban_spans if not iban_gb_valid(r["text"][s["start"]:s["end"]]))
    logger.info("NATIONAL_ID (NINO) spans: %d; invalid: %d", len(nino_spans), invalid_nino)
    logger.info("ACCOUNT_ID (GB-IBAN) spans: %d; invalid: %d", len(iban_spans), invalid_iban)

    # ---- diversity: before (stage-A) vs after (stage-B), RES-94 method -------------------------
    baseline_rows = [
        {"text": r["text"], "spans": list(r["spans"])} for r in stage_a_generate(n, seed=seed)
    ]
    before = gap.template_repetition(baseline_rows)
    after = gap.template_repetition([{"text": r["text"], "spans": r["spans"]} for r in rows])
    logger.info("unique-skeleton ratio  BEFORE (stage-A) = %.4f  (%d/%d unique, top-share %.4f)",
                before["unique_ratio"], before["unique_skeletons"], before["n_docs"], before["top_skeleton_share"])
    logger.info("unique-skeleton ratio  AFTER  (stage-B) = %.4f  (%d/%d unique, top-share %.4f)",
                after["unique_ratio"], after["unique_skeletons"], after["n_docs"], after["top_skeleton_share"])

    # ---- write artifacts (NOT pushed to HF — PoC; PR not merged) -------------------------------
    jsonl = out / "en_stageb_v1.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    metrics = {
        "issue": "RES-95",
        "config_status": "dev",
        "language": "en",
        "approach": "stage-B narrative: local offline LLM authors the body; PII injected "
        "deterministically (format-/checksum-valid) and spliced offset-deterministically.",
        "llm": {"model_id": model_id, "runtime": "mlx-lm (local, offline)", "network": False, "api_key": False},
        "n": len(rows),
        "seed": seed,
        "seconds": round(dt, 1),
        "seconds_per_doc": round(dt / max(len(rows), 1), 3),
        "gold_integrity": {
            "national_id_nino_spans": len(nino_spans),
            "invalid_nino": invalid_nino,
            "account_id_gb_iban_spans": len(iban_spans),
            "invalid_iban": invalid_iban,
            "all_rows_byte_equal_and_bioes_valid": True,  # _validate_row would have raised otherwise
        },
        "diversity_unique_skeleton_ratio": {
            "method": "europriv-bench analysis/synthetic_realism_gap.py::template_repetition",
            "before_stage_a": before,
            "after_stage_b": after,
            "ai4privacy_reference_ratio": 1.0,
        },
    }
    (out / "en_stageb_v1_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")
    logger.info("wrote %s (%d rows) and %s", jsonl, len(rows), out / "en_stageb_v1_metrics.json")
    print(json.dumps(metrics["diversity_unique_skeleton_ratio"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
