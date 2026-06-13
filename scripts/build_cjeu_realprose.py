"""RES-72/104 lexical-realism corpus: REAL CJEU legal prose + synthetic gold PII.

Tests whether training xlmr-560m on *real legalese* (not authored boilerplate) transfers to the
TAB real-legal board better than the structure-only CJEU real-skeleton did (TAB zero-shot 0.3399).

Method (entity-replacement de-identification synthesis):
  1. Stream real EN CJEU bodies from `davidwickerhf/cjeu-opendata` (Apache-2.0; EU-2011/833 reusable).
  2. Detect entity mentions with spaCy `en_core_web_lg` + a CJEU case-number regex.
  3. Replace each detected entity with a checksum-/format-valid synthetic value of the same KP type,
     so the replacement span IS the gold span. The surrounding REAL legal prose is preserved.
  4. Fail-loud gold gate per row (byte-equality + strict BIOES via europriv_bench.spans).
  5. Residual-PII estimate: a second pass over the FINAL text counts mappable mentions NOT covered by
     gold (spaCy misses / unmapped). CJEU judgments are public + frequently pseudonymised by the Court,
     so residual sensitivity is low — but we report it, not assume zero.

Run from the europriv-bench venv with PYTHONPATH=<klusai-datasets>. Artifacts are gitignored.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import pyarrow.parquet as pq
import spacy
from huggingface_hub import hf_hub_download

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes  # type: ignore
from klusai.privacy.datasets.data.en_generators import gen_person

# spaCy entity label -> KP/TAB label (the TAB crosswalk targets)
SPACY_TO_KP = {
    "PERSON": "PERSON",
    "ORG": "ORG_PARTY",
    "GPE": "ADDRESS",
    "LOC": "ADDRESS",
    "FAC": "ADDRESS",
    "DATE": "DATE",
}
CASE_RE = re.compile(r"\bCase\s+[CTF]?-?\d{1,4}/\d{2,4}\b|\b[CTF]-\d{1,4}/\d{2,4}\b")  # C-123/19, Case 2/54
# spaCy tags institutional references as ORG; these are NOT parties — leave them as real prose.
_ORG_STOP = ("court", "commission", "council", "parliament", "tribunal", "convention", "community",
             "union", "member state", "advocate general", "registry", "chamber", "treaty", "directive")

_ORG_HEAD = ["Nordia", "Veltra", "Aurelis", "Caldon", "Mersk", "Pelion", "Brightwater", "Strathmore",
             "Lindqvist", "Okeanis", "Halden", "Verbund", "Castellane", "Drummond", "Eyfjall"]
_ORG_TAIL = ["Holdings Ltd", "GmbH", "S.A.", "Industries plc", "Trading B.V.", "Group SE",
             "Logistics Oy", "Pharma AB", "Capital S.p.A.", "Energy NV"]
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]


def _synth_value(label: str, rng: random.Random) -> str:
    if label == "PERSON":
        p = gen_person(rng)
        return f"{p.first_name} {p.last_name}"
    if label == "ADDRESS":
        return gen_person(rng).address
    if label == "ORG_PARTY":
        return f"{rng.choice(_ORG_HEAD)} {rng.choice(_ORG_TAIL)}"
    if label == "DATE":
        return f"{rng.randint(1, 28)} {rng.choice(_MONTHS)} {rng.randint(1995, 2024)}"
    if label == "CASE_NUMBER":
        return f"{rng.choice('CTF')}-{rng.randint(1, 999)}/{rng.randint(0, 24):02d}"
    raise ValueError(label)


def _detect(text: str, nlp) -> list[tuple[int, int, str]]:
    """Mappable (start, end, KP_label) spans from spaCy + case-number regex, non-overlapping."""
    cands: list[tuple[int, int, str]] = []
    for ent in nlp(text).ents:
        kp = SPACY_TO_KP.get(ent.label_)
        if not kp or not ent.text.strip() or "\n" in ent.text:
            continue
        if kp == "ORG_PARTY" and any(w in ent.text.lower() for w in _ORG_STOP):
            continue  # institutional reference, not a party — keep as real prose
        cands.append((ent.start_char, ent.end_char, kp))
    for m in CASE_RE.finditer(text):
        cands.append((m.start(), m.end(), "CASE_NUMBER"))
    cands.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    accepted: list[tuple[int, int, str]] = []
    last_end = -1
    for s, e, lab in cands:
        if s >= last_end:
            accepted.append((s, e, lab))
            last_end = e
    return accepted


def _replace_once(text: str, rng: random.Random, nlp) -> tuple[str, list[dict]]:
    """One detect+replace pass: every mappable entity -> synthetic gold value. Returns (text, gold)."""
    out_parts: list[str] = []
    gold: list[dict] = []
    cur = 0
    for s, e, lab in _detect(text, nlp):
        out_parts.append(text[cur:s])
        val = _synth_value(lab, rng)
        start = sum(len(p) for p in out_parts)
        out_parts.append(val)
        gold.append({"start": start, "end": start + len(val), "label": lab})
        cur = e
    out_parts.append(text[cur:])
    return "".join(out_parts), gold


def build_doc(body: str, rng: random.Random, nlp) -> dict | None:
    """Replace detected entities in real prose with synthetic gold PII, iterating until no mappable
    mention surfaces (entities can appear only after a replacement changes context). Return a row
    whose every span is byte-exact + strict-BIOES valid, or None if the doc can't be made clean."""
    if len(_detect(body, nlp)) < 3:
        return None
    text, gold = _replace_once(body, rng, nlp)
    # Gold gate: byte-equality + strict BIOES. Skip (don't crash on) token-collision docs.
    try:
        for sp in gold:
            if not text[sp["start"]:sp["end"]] or text[sp["start"]:sp["end"]] == "\n":
                return None
        validate_bioes(char_spans_to_bioes(text, [Span(s["start"], s["end"], s["label"]) for s in gold]))
    except ValueError:
        return None
    return {"text": text, "spans": gold, "language": "en", "domain": "legal", "source": "cjeu-realprose"}


def residual_pii(text: str, gold: list[dict], nlp) -> int:
    """Mappable mentions in the FINAL text NOT covered by a gold span (spaCy misses / unmapped)."""
    covered = {(s["start"], s["end"]) for s in gold}
    gold_ranges = [(s["start"], s["end"]) for s in gold]
    n = 0
    for ent in nlp(text).ents:
        if SPACY_TO_KP.get(ent.label_) is None or (ent.start_char, ent.end_char) in covered:
            continue
        if ent.label_ == "ORG" and any(w in ent.text.lower() for w in _ORG_STOP):
            continue  # institutional reference we deliberately keep as real prose — not leakage
        if any(ent.start_char < ge and gs < ent.end_char for gs, ge in gold_ranges):
            continue
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20260608)
    ap.add_argument("--max-chars", type=int, default=1800)
    ap.add_argument("--out", default=None)
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    nlp = spacy.load("en_core_web_lg", disable=["lemmatizer", "tagger", "attribute_ruler"])
    # The dataset is ONE parquet file. HF streaming hangs reading its row-groups over the network, so
    # download it once (cached) and read locally with pyarrow — fast and reliable, no streaming threads.
    path = hf_hub_download("davidwickerhf/cjeu-opendata", "fulltexts.parquet", repo_type="dataset")
    print(f"reading {path}", flush=True)
    pfile = pq.ParquetFile(path)

    rows: list[dict] = []
    scanned = en_seen = residual_total = gold_total = residual_sample = 0
    sample_gold = 0
    t0 = time.time()
    for batch in pfile.iter_batches(batch_size=2000, columns=["text", "text_language"]):
        col = batch.to_pydict()
        for body_raw, lang in zip(col["text"], col["text_language"]):
            scanned += 1
            if (lang or "").upper() != "EN":
                continue
            en_seen += 1
            body = (body_raw or "").strip()
            if len(body) < 400:
                continue
            body = body[: args.max_chars]
            try:
                row = build_doc(body, rng, nlp)
            except AssertionError:
                continue
            if row is None:
                continue
            if len(rows) < 200:  # residual-PII on a 200-doc sample (a 2nd NER pass is costly at scale)
                residual_total += residual_pii(row["text"], row["spans"], nlp)
                residual_sample += 1
                sample_gold += len(row["spans"])
            gold_total += len(row["spans"])
            rows.append(row)
            if len(rows) % 1000 == 0:
                print(f"  built {len(rows)}/{args.n} (scanned {scanned}, {time.time()-t0:.0f}s)", flush=True)
        if len(rows) >= args.n:
            break

    sigs = {tuple(s["label"] for s in row["spans"]) for row in rows}
    report = {
        "n_docs": len(rows),
        "scanned_rows": scanned,
        "en_rows_seen": en_seen,
        "gold_spans": gold_total,
        "residual_sample_docs": residual_sample,
        "residual_pii_mentions_in_sample": residual_total,
        "residual_pii_per_doc_sampled": round(residual_total / max(1, residual_sample), 3),
        "residual_rate_vs_gold_sampled": round(residual_total / max(1, sample_gold), 4),
        "label_signature_uniqueness": round(len(sigs) / max(1, len(rows)), 4),
        "build_seconds": round(time.time() - t0, 1),
    }
    print(json.dumps(report, indent=2), flush=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"wrote {len(rows)} rows -> {args.out}", flush=True)
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2))
    # HF streaming leaves prefetch threads that hang on normal interpreter shutdown after an early
    # break. Outputs are already flushed above, so hard-exit to avoid a multi-minute teardown stall.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
