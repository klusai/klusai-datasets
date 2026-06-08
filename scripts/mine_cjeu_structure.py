#!/usr/bin/env python3
"""Mine layout-only structural signatures from real EN CJEU judgments (RES-72 real-skeleton scaffold).

Reads ``davidwickerhf/cjeu-opendata`` (config ``fulltexts``, Apache-2.0) via the public HF
datasets-server rows API (no credentials) and extracts, per EN document, ONLY structural features:
the document type (JUDGMENT/OPINION), the ordered sequence of section-heading *types* (classified
into a tiny controlled vocabulary), and paragraph counts. **No source sentence, heading text, party
name, or identifier is stored** — the output ``artifacts/res72/cjeu_en_signatures.json`` is pure
layout, so no CJEU prose is redistributed. These signatures scaffold ``en_skeletons_legal`` (RES-72).

CJEU is the Court of Justice of the EU — a different court/corpus from TAB's ECHR/HUDOC judgments, so
a model trained on this structure and scored on TAB is a genuine zero-shot transfer (no contamination).

    python scripts/mine_cjeu_structure.py --target 80 --out artifacts/res72/cjeu_en_signatures.json
"""

from __future__ import annotations

import collections
import json
import re
import time
import urllib.request
from pathlib import Path

import click

URL = (
    "https://datasets-server.huggingface.co/rows?dataset=davidwickerhf/cjeu-opendata"
    "&config=fulltexts&split=train&offset={off}&length={ln}"
)
HEADING_RE = re.compile(r"^[A-Z][A-Z \-,'()0-9.]{3,60}$")
NUM_PARA_RE = re.compile(r"^\d+\.?\s")


def _fetch(off: int, ln: int = 100) -> list[dict]:
    last: Exception | None = None
    for _ in range(4):
        try:
            with urllib.request.urlopen(URL.format(off=off, ln=ln), timeout=60) as r:
                return json.load(r).get("rows", [])
        except Exception as exc:  # noqa: BLE001 — transient datasets-server hiccups; retry then skip
            last = exc
            time.sleep(2)
    click.echo(f"fetch failed at offset {off}: {last!r}")
    return []


def _classify_heading(h: str) -> str:
    u = h.upper()
    if "JUDGMENT" in u:
        return "JUDGMENT_HEADING"
    if "OPINION" in u or "CONCLUSIONS" in u or "ADVOCATE GENERAL" in u:
        return "OPINION_HEADING"
    if "SUMMARY" in u or "CONTENTS" in u:
        return "SUMMARY"
    if u.startswith("ON THOSE GROUNDS") or "OPERATIVE" in u or u.startswith("THE COURT"):
        return "OPERATIVE"
    if "GROUNDS" in u or "FACTS" in u or "LAW" in u or "PROCEDURE" in u:
        return "GROUNDS"
    if "PARTIES" in u or "APPLICANT" in u or "DEFENDANT" in u:
        return "PARTIES"
    return "SECTION"


@click.command()
@click.option("--target", type=int, default=80, help="number of EN signatures to mine")
@click.option("--max-scan", type=int, default=4000, help="max rows to scan")
@click.option(
    "--out",
    type=click.Path(),
    default="klusai/privacy/datasets/data/res72/cjeu_en_signatures.json",
)
def main(target: int, max_scan: int, out: str) -> None:
    signatures: list[dict] = []
    seen: set[str] = set()
    off = 0
    while len(signatures) < target and off < max_scan:
        rows = _fetch(off, 100)
        off += 100
        if not rows:
            break
        for r in rows:
            row = r["row"]
            if row.get("text_language") != "EN":
                continue
            celex = row.get("celex")
            if celex in seen:
                continue
            text = row.get("text") or ""
            if len(text) < 1500:
                continue
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            doctype = (
                "OPINION"
                if any("OPINION" in ln.upper() or "ADVOCATE GENERAL" in ln.upper() for ln in lines[:3])
                else "JUDGMENT"
            )
            headings = [_classify_heading(ln) for ln in lines if HEADING_RE.match(ln)]
            if not headings:
                continue
            seen.add(celex)
            signatures.append(
                {
                    "doctype": doctype,
                    "n_lines": len(lines),
                    "heading_seq": headings[:12],
                    "n_headings": len(headings),
                    "n_numbered_paras": sum(1 for ln in lines if NUM_PARA_RE.match(ln)),
                }
            )

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(signatures, indent=1) + "\n")
    click.echo(f"mined {len(signatures)} EN signatures -> {out_path}")
    click.echo(f"doctype: {collections.Counter(s['doctype'] for s in signatures)}")
    click.echo(
        f"heading types: {collections.Counter(h for s in signatures for h in s['heading_seq'])}"
    )


if __name__ == "__main__":
    main()
