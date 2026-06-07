#!/usr/bin/env python3
"""RES-102 — generate the matched stage-A (template-splice) arm for the structural ablation.

This is the control arm of the RES-102 matched-pair structural ablation. Arm B (stage-B,
LLM-narrated bodies) already exists as ``artifacts/europriv/en_stageb_v1.jsonl`` (RES-95, seed
20260607). This script builds **arm A**: the SAME per-document PII *values* spliced into fixed
template-splice **stage-A** bodies, so the ONLY thing that differs between the two arms is the
document *structure* (templated vs narrative). Matched size (2000), matched PII values, matched seed.

Why we lift bundles from the artifact (and not a pure rng replay)
-----------------------------------------------------------------
``en_stageb.generate_stageb`` advances its RNG per document as ``genre = rng.choice(GENRES)`` then
``fields = _fields(rng)``. One *could* replay that stream to regenerate the bundles. But stage-B's
**fallback path** (``_stage_a_fallback``) calls ``_fields(rng)`` a SECOND time, and whether a doc
fell back depended on the live LLM output — which is not captured in the seed. So the shipped
artifact's per-doc rng stream is NOT reproducible from the seed alone (verified: a clean replay
desyncs from the artifact at the first fallback, mean value-jaccard ~0.002).

A matched-pair ablation demands the PII be **identical per document** so structure is the only
variable. The faithful way to get that is to take the exact PII values stage-B actually emitted —
read straight from ``en_stageb_v1.jsonl`` gold spans — and re-render each through a stage-A template
via the SAME offset-deterministic ``localepack.fill_document`` gate stage-A / the stage-B fallback
use. Byte-for-byte identical PII, byte-equality + strict-BIOES validated identically to arm B; only
the body structure differs. Determinism is preserved: template choice per doc is seeded.

Slot reconstruction
-------------------
Each stage-B row's gold spans carry the emitted values by label. We take, per row, the FIRST value
of each label and map labels -> stage-A slot names (PERSON->person, NATIONAL_ID->nino,
ADDRESS->address, PHONE->phone, ACCOUNT_ID->iban, EMAIL->email, DATE->date). For each doc we then
pick, seeded, among the stage-A templates whose required slots are all present in that doc's bundle
(the same two REQUIRED_SLOTS-subset templates the stage-B fallback draws from: the ``legal``
declaration and the ``admin`` payment notice). Every doc's bundle contains a renderable template by
construction (the stage-B fallback domains map onto exactly these two).

Single process, one output/log — no concurrency (RES-97 lesson).

    python scripts/generate_en_stagea_matched_v1.py --n 2000 --seed 20260607
"""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

import click

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from klusai.privacy.datasets.data.en_generators import iban_gb_valid, nino_format_valid
from klusai.privacy.datasets.data.en_stageb import REQUIRED_SLOTS, STAGE_A_TEMPLATES
from klusai.privacy.datasets.data.localepack import fill_document
from klusai.privacy.datasets.logger import get_logger

logger = get_logger("en-stagea-matched-v1")

_SLOT_RE = re.compile(r"\{([a-z_]+)\}")

# Gold label -> stage-A slot name. The stage-B bundle maps card-less (no {card}/{company}/{condition}).
_LABEL_TO_SLOT = {
    "PERSON": "person",
    "NATIONAL_ID": "nino",
    "ADDRESS": "address",
    "PHONE": "phone",
    "ACCOUNT_ID": "iban",
    "EMAIL": "email",
    "DATE": "date",
}

# The stage-A template pool eligible for the coherent stage-B PII bundle: those whose slots are a
# subset of REQUIRED_SLOTS. This is the SAME pool en_stageb._stage_a_fallback draws from.
_POOL = tuple(
    (dom, tmpl)
    for dom, tmpl in STAGE_A_TEMPLATES
    if set(_SLOT_RE.findall(tmpl)) <= set(REQUIRED_SLOTS)
)


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


def _bundle_from_stageb_row(sb_row: dict) -> dict[str, tuple[str, str]]:
    """Reconstruct a coherent slot -> (value, label) bundle from a stage-B gold row.

    Takes the FIRST occurrence of each label (a doc may repeat a person/id; every occurrence carried
    the same value, so the first is canonical). Only labels in _LABEL_TO_SLOT are kept.
    """
    fields: dict[str, tuple[str, str]] = {}
    text = sb_row["text"]
    for sp in sb_row["spans"]:
        label = sp["label"]
        slot = _LABEL_TO_SLOT.get(label)
        if slot is None or slot in fields:
            continue
        fields[slot] = (text[sp["start"]:sp["end"]], label)
    return fields


def _renderable_pool(fields: dict[str, tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """Stage-A templates whose every slot is present in this doc's reconstructed bundle."""
    present = set(fields)
    return tuple(
        (dom, tmpl) for dom, tmpl in _POOL if set(_SLOT_RE.findall(tmpl)) <= present
    )


def generate_stagea_matched(sb_rows: list[dict], seed: int) -> list[dict]:
    """Render each stage-B doc's exact PII bundle through a seeded stage-A template choice."""
    rng = random.Random(seed)
    rows: list[dict] = []
    for sb_row in sb_rows:
        fields = _bundle_from_stageb_row(sb_row)
        pool = _renderable_pool(fields)
        if not pool:
            raise RuntimeError(
                f"no stage-A template renderable from bundle slots {sorted(fields)}; "
                "stage-B row is missing a required slot value"
            )
        # Seeded template choice + the shared offset-deterministic gate. The builder ignores its rng
        # arg and returns this doc's fixed (byte-identical-to-stage-B) bundle.
        doc = fill_document(rng, pool, lambda _r, _f=fields: _f)
        rows.append({
            "text": doc.text,
            "spans": doc.spans,
            "language": "en",
            "domain": doc.domain,
            "family": "stagea_matched",
            "genre": "en-stagea-template-v1",
        })
    return rows


@click.command()
@click.option("--n", type=int, default=2000, help="Batch size (matched to the stage-B arm).")
@click.option("--seed", type=int, default=20260607, help="Seed for the template choice.")
@click.option("--outdir", default="artifacts/europriv", help="Where to write the JSONL + metrics.")
@click.option("--stageb-path", default="artifacts/europriv/en_stageb_v1.jsonl",
              help="Stage-B artifact whose exact PII bundles arm A reuses.")
def main(n: int, seed: int, outdir: str, stageb_path: str) -> None:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    sb_path = Path(stageb_path)
    if not sb_path.exists():
        raise FileNotFoundError(f"stage-B artifact not found at {sb_path}")
    sb_rows = [json.loads(line) for line in sb_path.open(encoding="utf-8")][:n]
    logger.info("RES-102 arm A: matched stage-A from %d stage-B bundles (seed=%d)", len(sb_rows), seed)
    logger.info("eligible stage-A template pool (slots subset of REQUIRED_SLOTS): %d templates", len(_POOL))

    t0 = time.time()
    rows = generate_stagea_matched(sb_rows, seed)
    for r in rows:
        _validate_row(r)  # fail loud on the first misaligned span / invalid id
    dt = time.time() - t0
    logger.info("generated + validated %d rows in %.2fs", len(rows), dt)

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

    # ---- matched-pair PII audit: every arm-A bundle's values are a subset of the stage-B doc's ---
    docs_pii_subset = 0
    for arm_a, sb_row in zip(rows, sb_rows, strict=True):
        a_vals = {arm_a["text"][s["start"]:s["end"]] for s in arm_a["spans"]}
        b_vals = {sb_row["text"][s["start"]:s["end"]] for s in sb_row["spans"]}
        if a_vals <= b_vals:
            docs_pii_subset += 1
    logger.info("matched-pair PII: %d/%d arm-A docs have all PII values present in their stage-B pair",
                docs_pii_subset, len(rows))

    # ---- write artifacts -----------------------------------------------------------------------
    jsonl = out / "en_stagea_matched_v1.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    metrics = {
        "issue": "RES-102",
        "arm": "A (stage-A template-splice control)",
        "config_status": "dev",
        "language": "en",
        "approach": "matched stage-A: reuse each stage-B doc's EXACT gold PII values; render through a "
        "stage-A template via the shared offset-deterministic gate. Only body structure differs.",
        "matched_to": str(sb_path),
        "n": len(rows),
        "seed": seed,
        "seconds": round(dt, 2),
        "gold_integrity": {
            "national_id_nino_spans": len(nino_spans),
            "invalid_nino": invalid_nino,
            "account_id_gb_iban_spans": len(iban_spans),
            "invalid_iban": invalid_iban,
            "all_rows_byte_equal_and_bioes_valid": True,  # _validate_row would have raised otherwise
        },
        "matched_pair_pii": {
            "docs_compared": len(rows),
            "docs_all_pii_values_in_stageb_pair": docs_pii_subset,
        },
        "eligible_stage_a_templates": [t for _d, t in _POOL],
    }
    (out / "en_stagea_matched_v1_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")
    logger.info("wrote %s (%d rows) and %s", jsonl, len(rows), out / "en_stagea_matched_v1_metrics.json")
    print(json.dumps({k: metrics[k] for k in ("gold_integrity", "matched_pair_pii")},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
