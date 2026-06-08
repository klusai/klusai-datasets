# RES-72 — Real-legal training corpus: scoping + tiny proof (EN, CJEU real-skeleton)

*2026-06-08 · config_status: **dev** · scope: SCOPING + TINY-PROOF ONLY (no training, no full build,
no publishing)*

This is the grounded build plan + a small gold-validated proof for the RES-72 real-legal training
corpus that is intended to feed the **RES-104 win-track**: a general legal de-id model that tops the
**TAB real-legal board by GENERALIZING to it zero-shot** — *not* by training on TAB.

## The finding this responds to

Generic synthetic training (template-splice *and* LLM-narrative, 280M & 560M) caps at TAB entity-F1
**~0.23–0.30**, far below Presidio's **0.589**:

| Arm | Train data | TAB entity-F1 | Source |
|---|---|---|---|
| stage-A template-splice (xlmr-560m, 2k) | `en_stagea_matched_v1` | 0.2961 | `klusai-models/docs/res104-xlmr560m-stageb-scorecard.md` |
| stage-B LLM-narrative (xlmr-560m, 2k) | `en_stageb_v1` | 0.2297 | same |
| full-corpus template-splice (xlmr-560m, 40k) | — | 0.2439 | same |
| **Presidio** (baseline to beat) | n/a | **0.589** | board |

Hypothesis now under test: **real legal-document STRUCTURE** (not just synthetic prose) is what
closes the gap. RES-72's locked method is **real-skeleton** — use real legal document
STRUCTURE/layout as the scaffold, splice synthetic checksum-valid PII deterministically (gold by
construction), and **never redistribute the real source text** (structure only, license-clean).

---

## Task 1 — Source survey + license diligence

TAB = real **ECHR** (Council of Europe / HUDOC) court **judgments**, English, remapped to KP
(PERSON, CASE_NUMBER, ADDRESS, ORG_PARTY, DATE). The scaffold's structure should match the
**court-judgment** genre, and it MUST be (a) cleanly licensed and (b) free of any overlap with the
127 TAB **test** judgments (overlap would poison a zero-shot claim).

Licenses verified live against the HF dataset API / source legal notices on **2026-06-08**:

| Candidate | License (verified) | Domain match | Contamination vs TAB test | Verdict |
|---|---|---|---|---|
| **`davidwickerhf/cjeu-opendata`** (fulltexts) | **Apache-2.0** | CJEU **court judgments/opinions** — judgment genre, EN available | **None** — CJEU ≠ ECHR/HUDOC (different court & corpus) | **PRIMARY** ✅ |
| `AUEB-NLP/ecthr_cases` | CC-BY-**NC-SA**-4.0 | ECHR case law (best match) | **HIGH** — same HUDOC family as TAB | EXCLUDED (NC+SA *and* contamination) |
| LexGLUE `ecthr_a`/`ecthr_b` (`coastalcph/lex_glue`) | CC-BY-4.0 | ECHR facts (Chalkidis, from HUDOC) | **HIGH** — HUDOC-derived, same family as TAB | EXCLUDED (contamination) |
| `coastalcph/multi_eurlex` | CC-BY-**SA**-4.0 | EU **legislation** (weaker match) | None | EXCLUDED (SA copyleft) |
| `joelniklaus/Multi_Legal_Pile`, `lexlms/lex_files`, `pile-of-law` | CC-BY-**NC-SA**-4.0 | mixed legal | mixed (some HUDOC) | EXCLUDED (NC-SA) |
| `joelniklaus/eurlex_resources`, `dennlinger/eur-lex-sum`, `ddrg/super_eurlex` | CC-BY-4.0 / MIT | EU legislation/summaries | None | clean but legislation (weaker genre match than CJEU judgments) |

**Recommended primary source: `davidwickerhf/cjeu-opendata`** (config `fulltexts`, Apache-2.0,
546,733 docs; multilingual incl. EN; CJEU = Court of Justice of the EU). Justification:

- **License-clean** — Apache-2.0 (in the program's `_CLEAN` allowlist); CJEU material on EUR-Lex is
  additionally reusable commercially under **Commission Decision 2011/833/EU**. We rely only on the
  uncopyrightable section LAYOUT, so even that permission is not load-bearing.
- **Genre match** — CJEU issues **court judgments** (caption → parties → grounds → operative part),
  structurally analogous to ECHR judgments; far closer to TAB than EU legislation.
- **Zero TAB contamination** — TAB is ECHR/HUDOC; CJEU is a *different court and corpus*. No document
  overlap, so CJEU-structure → TAB-ECHR is a genuine zero-shot transfer. **This is the decisive
  reason the scaffold is CJEU, not ECHR**: every clean ECHR-domain option (ecthr_cases, LexGLUE
  ecthr) is HUDOC-derived and risks containing the TAB test docs.

License classification was run through the repo's own `assert_clean_license` gate; Apache-2.0
passes, all NC/ND/SA candidates are rejected fail-closed.

## Task 2 — Construction design

The RES-72 real-skeleton construction, and how it differs from the existing `*-realskeleton` packs:

1. **Structure extraction (layout-only, no text).** `scripts/mine_cjeu_structure.py` reads EN CJEU
   fulltexts via the public HF datasets-server API and extracts, per document, **only** a *layout
   signature*: the document type (JUDGMENT/OPINION), the ordered sequence of section-heading *types*
   (classified into a tiny controlled vocabulary — PARTIES, SUMMARY, GROUNDS, SECTION, OPERATIVE,
   …), and paragraph counts. **No source sentence, heading text, party name, or identifier is
   stored.** The committed cache `klusai/privacy/datasets/data/res72/cjeu_en_signatures.json` is pure
   structure (91 EN signatures), so no CJEU prose is redistributed — a `test_signature_cache_is_
   structure_only` guard enforces this.
2. **Rendering + PII injection.** `en_skeletons_legal.py` samples a real signature and renders it
   into **authored** neutral connective prose (original boilerplate keyed to heading types) with
   `{slot}` markers. Checksum-/format-valid synthetic PII (`en_generators.gen_person` /
   `gen_iban_gb`) is spliced by the shared offset-deterministic `localepack._fill`. KP labels are
   the TAB-crosswalk types: PERSON, CASE_NUMBER, ADDRESS, ORG_PARTY, DATE (+ IBAN direct id).
3. **Gold production + validation.** Identical to every other pack: `text[start:end] == value` by
   construction → per-span **byte-equality assert** → strict `char_spans_to_bioes` + `validate_bioes`
   gate (fails loud on token collision). 0 invalid PII, 0 misaligned, all BIOES-valid (Task 3).
4. **Zero-contamination guarantee.** The scaffold is CJEU; TAB is ECHR/HUDOC — disjoint corpora.
   Only layout *features* (never prose) leave the source, so even structurally a TAB judgment cannot
   be reconstructed. The model never sees a TAB document or any ECHR text.

**Difference from the existing `ro_skeletons_legal` etc.** Those use **3 authored templates**, which
collapses the unique-document-skeleton ratio toward ~0 (the same templating defect RES-94 measured as
~0.004 for our generic EN synthetic). RES-72 instead drives structure from **many real layout
signatures**, so each document follows a *distinct* real skeleton → high structural diversity by
construction. That diversity is the whole point of the real-skeleton bet.

## Task 3 — Tiny proof (~50 docs)

`klusai/privacy/datasets/data/en_skeletons_legal.py` + `tests/test_en_skeletons_legal.py`
(9 tests, all green). Proof run (`seed=20260608`, n=50; metrics in
`klusai/privacy/datasets/data/res72/` is structure-only — the run metrics are reproduced here):

| Metric | Value |
|---|---|
| n docs | **50** |
| invalid PII (IBAN mod-97 + NINO format) | **0** |
| misaligned spans (byte-equality) | **0** |
| BIOES-invalid docs | **0** |
| **unique-skeleton ratio** (RES-94 `template_repetition`) | **0.90** (45/50 unique, top-share 0.12) |
| label distribution | CASE_NUMBER 115, IBAN 106, DATE 104, ORG_PARTY 103, PERSON 60, ADDRESS 42 |

**Diversity comparison** (same `synthetic_realism_gap.py::template_repetition` method):

| Corpus | unique-skeleton ratio |
|---|---|
| Generic synthetic (ds-kp-general-en, template-splice) | **0.004** |
| **EN CJEU real-skeleton (this proof)** | **0.90** |
| Ai4Privacy (LLM synthetic) | **~1.0** |

The real-skeleton scaffold lifts structural diversity **~225×** over generic template-splice, landing
near the LLM-narrative ceiling — confirming the construction does inject real structural variety.

## Task 4 — Build + train plan + go/no-go

**Full build (if GO):**
- *Scale*: 20k–40k EN docs (match the 40k full-corpus board entry for an apples-to-apples train).
  Mine ≥2,000 distinct EN CJEU signatures (the proof used 91; trivially scalable via
  `mine_cjeu_structure.py --target`). Add a **second authored connective-prose family** before any
  citable claim (the KLU-101 hardening: a single family is not validated generalization).
- *Languages*: EN first (for TAB). Then ≥3 languages per the RES-72 acceptance bar — CJEU
  `cjeu-opendata` already ships FR/NL/DE/… fulltexts, so the same signature-mining + per-locale
  LocalePack PII (existing `*_generators`) extends multilingually with no new license work.
- *Gold gate*: unchanged (byte-equality + strict BIOES; fail-loud, drop-and-count).

**Train/eval experiment:** train **xlmr-560m** (`FacebookAI/xlm-roberta-large`, the best detector
arch) on the EN CJEU real-legal corpus with the **exact** RES-104 hyperparams + the
`scorecard_klu106` TAB scoring path (apples-to-apples). Score **TAB test zero-shot**. Success = TAB
entity-F1 clears the **0.30 synthetic ceiling** materially; stretch = approaches/beats **Presidio
0.589**. Report single-seed directionally first, then a seed band if positive.

**Honest risk (the load-bearing one).** The proof shows we close the **structural-diversity** gap
(0.004 → 0.90). It does **not** show we close the **lexical-realism** gap. RES-104 already found that
LLM-narrated structure (stage-B) did **not** beat template-splice on TAB for xlmr-560m (−0.066) — so
*generic* structural diversity alone has not transferred. The open question is whether **real legal
structure with synthetic PII** transfers to TAB's real legal **prose**, or whether the missing piece
is lexical/terminological realism (real legalese, real entity surface forms) that synthetic PII +
authored connective prose still won't supply. The connective prose here is authored boilerplate, not
real CJEU legalese, so this corpus tests "does real layout help?" but **not** "does real legal
language help?". If transfer is flat, the next lever is lexical (real-vocabulary scaffolding under
the license/contamination constraints), not more structure.

**Go/no-go: GO — bounded.** GO to a **single-arm EN xlmr-560m train + TAB zero-shot eval at ~20k**
as the cheapest decisive test of the structure hypothesis, *before* any multilingual scale-up or
publishing. The proof clears every gold-integrity gate and the diversity claim is real, so the
experiment is worth its cost; but gate the full multilingual build + publish on that single EN
TAB-F1 number beating the 0.30 ceiling. If it does not beat 0.30, **NO-GO** on the full build and
pivot to the lexical-realism lever. Rationale: RES-104's negative stage-B delta means we should not
assume structure transfers; one cheap EN run resolves it.

## Provenance / reproducibility

- Source: `davidwickerhf/cjeu-opendata` (config `fulltexts`, Apache-2.0), EN rows, mined 2026-06-08.
- Mining: `scripts/mine_cjeu_structure.py` (layout-only; public datasets-server API, no credentials).
- Generator: `klusai/privacy/datasets/data/en_skeletons_legal.py`; tests:
  `tests/test_en_skeletons_legal.py`.
- Structure cache (committed, structure-only): `klusai/privacy/datasets/data/res72/cjeu_en_signatures.json`.
- Registry: `conf/datasets.yaml` (`cjeu-opendata-structure` source + `ds-kp-legal-en-rs` config).
- Gold gate inherited unchanged from `localepack.fill_document` (byte-equality + strict BIOES).
