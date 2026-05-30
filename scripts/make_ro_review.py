#!/usr/bin/env python3
"""Generate a self-contained HTML review page for ro-realskeleton-v1 — easy native-speaker QA.

Each document is shown with its synthetic PII spans highlighted/labeled. The reviewer scans for:
(1) does it read like natural Romanian, (2) are the highlighted spans correct (right text + label).
There is no residual real PII to hunt (skeletons are authored, PII is synthetic). Flagged items +
notes are collected by a button into a text box to paste back.

    python scripts/make_ro_review.py --n 40 --out review.html && open review.html
"""

from __future__ import annotations

import html

import click

from klusai.privacy.datasets.data.ro_skeletons import generate_dataset

COLORS = {
    "PERSON": "#488EFF", "NATIONAL_ID": "#F97316", "ADDRESS": "#14B8A6", "PHONE": "#D946EF",
    "EMAIL": "#F59E0B", "DATE": "#64748B", "ACCOUNT_ID": "#8B5CF6", "COMPANY_ID": "#0EA5E9",
    "ORG_PARTY": "#10B981", "HEALTH_CONDITION": "#EF4444", "CASE_NUMBER": "#A16207",
}


def _render(text: str, spans: list[dict]) -> str:
    out, cur = [], 0
    for sp in sorted(spans, key=lambda s: s["start"]):
        out.append(html.escape(text[cur:sp["start"]]))
        seg = html.escape(text[sp["start"]:sp["end"]])
        c = COLORS.get(sp["label"], "#888")
        out.append(f'<mark style="background:{c}22;border-bottom:2px solid {c}" '
                   f'title="{sp["label"]}">{seg}<sub style="color:{c}">{sp["label"]}</sub></mark>')
        cur = sp["end"]
    out.append(html.escape(text[cur:]))
    return "".join(out).replace("\n", "<br>")


@click.command()
@click.option("--n", type=int, default=40)
@click.option("--seed", type=int, default=20260530)
@click.option("--out", default="review.html")
def main(n: int, seed: int, out: str) -> None:
    docs = list(generate_dataset(n, seed=seed))
    legend = " ".join(
        f'<span style="border-bottom:2px solid {c}">{lbl}</span>' for lbl, c in COLORS.items()
    )
    cards = []
    for i, d in enumerate(docs):
        cards.append(f"""
        <div class="card" data-i="{i}">
          <div class="hdr">#{i} · <em>{d['domain']}</em> · {len(d['spans'])} spans
            <label class="ok"><input type="checkbox" class="okbox" checked> reads OK</label></div>
          <div class="doc">{_render(d['text'], d['spans'])}</div>
          <input class="note" placeholder="flag a problem (wrong span/label, unnatural phrasing)…">
        </div>""")
    page = f"""<!doctype html><meta charset="utf-8"><title>EuroPriv RO real-skeleton review</title>
<style>
 body{{font:15px/1.5 -apple-system,Inter,sans-serif;max-width:900px;margin:24px auto;color:#0F172A}}
 .doc{{white-space:normal;background:#F8FAFC;padding:14px;border-radius:8px;border:1px solid #E2E8F0}}
 .card{{margin:18px 0}} .hdr{{font-size:13px;color:#475569;margin-bottom:6px}}
 mark{{padding:0 1px;border-radius:2px}} sub{{font-size:9px;margin-left:2px}}
 .note{{width:100%;margin-top:6px;padding:6px;border:1px solid #E2E8F0;border-radius:6px}}
 .legend{{font-size:12px;color:#475569;margin:8px 0 16px}} .legend span{{margin-right:10px}}
 .ok{{float:right;font-size:12px;color:#475569}} button{{padding:8px 14px;font-size:14px}}
 #fb{{width:100%;height:120px;margin-top:8px}}
</style>
<h2>EuroPriv-Bench — Romanian real-skeleton review ({n} docs)</h2>
<p>Skeletons are authored from real RO document structures; <b>all identifiers are synthetic</b>
(no real personal data). Just check: does it read like natural Romanian, and are the highlighted
spans the right text + right label? Untick "reads OK" and/or add a note for anything off.</p>
<div class="legend">{legend}</div>
{''.join(cards)}
<button onclick="collect()">Generate feedback to paste back</button>
<textarea id="fb" placeholder="feedback appears here"></textarea>
<script>
function collect(){{
  let out=[];
  document.querySelectorAll('.card').forEach(c=>{{
    const ok=c.querySelector('.okbox').checked, note=c.querySelector('.note').value.trim();
    if(!ok||note) out.push('#'+c.dataset.i+(ok?'':' [NOT OK]')+(note?' — '+note:''));
  }});
  document.getElementById('fb').value = out.length? out.join('\\n') : 'All '+{n}+' docs look OK.';
}}
</script>"""
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    click.echo(f"wrote {out} ({n} docs) — open it, skim, click 'Generate feedback'")


if __name__ == "__main__":
    main()
