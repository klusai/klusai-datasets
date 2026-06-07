# RES-95 v1 — stage-B narrative generator (English): the templating fix generalises

**Status: `config_status=dev`. v1 proof-of-concept (English).** The English sibling of the
Romanian stage-B proof ([`res95-v1-stageb-scorecard.md`](res95-v1-stageb-scorecard.md)) — it shows
the stage-B upgrade is **language-agnostic**: the exact gold-safety design that closed the RO
templating gap applies to a second language by swapping only the *locale content*. Not a SOTA/citable
claim. Machine-readable companion: [`res95-v1-en-stageb-metrics.json`](res95-v1-en-stageb-metrics.json).

## The fix (same mechanism as RO)

The stage-A EN generator (`en_documents`) splices PII into ~6 fixed templates, so the
unique-document-skeleton ratio collapses exactly as RES-94 found for RO. **Stage-B** has a **local,
offline LLM** (`Qwen/Qwen3-1.7B` via `mlx-lm` — no network, no API key) author the *surrounding
narrative*, emitting our `{slot}` placeholders verbatim, while the **PII values stay deterministically
generated + offset-spliced** by the existing format-/checksum-valid EN generators. The
sanitizer/splice/validation path is byte-for-byte the same logic as `ro_stageb`.

## Result (2000 EN docs, seed 20260607)

| | unique-skeleton ratio | unique skeletons / 2000 | top-skeleton share |
|---|---:|---:|---:|
| **before** (stage-A template-splice) | **0.003** | 6 | 17.2% |
| **after** (stage-B narrative) | **0.715** | 1,430 | 13.5% |
| Ai4Privacy reference | 1.0 | — | — |

Diversity climbs **0.003 → 0.715** — a ~240× gain, measured by the same
`europriv-bench analysis/synthetic_realism_gap.py::template_repetition` method as RES-94/RO. The gain
is large but **lower than RO's 0.909**: the EN narrator settles into fewer distinct genre framings
under the identical prompt/decoding budget. Pushing EN toward RO-level diversity (genre/prompt
variety, sampling temperature, longer bodies) is a v1.1 follow-up — it does **not** touch gold.

## Gold integrity — byte-for-byte intact (the load-bearing constraint)

- **NATIONAL_ID (NINO) spans: 1,762; invalid: 0.** **ACCOUNT_ID (GB-IBAN) spans: 1,793; invalid: 0.**
  The LLM **never authors a PII value** — its body is constrained to contain no braces and no digit
  runs, so it cannot smuggle a literal NINO/IBAN/date/phone into the static prose.
- PII values come from the deterministic generators (`en_generators`; IBAN-GB mod-97 and card Luhn are
  genuinely checksum-valid, NINO format-valid as the scheme defines no checksum) and are spliced at
  known offsets; **every row passes `char_spans_to_bioes` + `validate_bioes`** (a misaligned span
  fails loud and the row is discarded — never shipped misaligned). Independent re-check: **0 of 2000
  rows misaligned.**
- Entity coverage (2000 docs): PERSON 2,323 · DATE 2,282 · EMAIL 1,975 · ACCOUNT_ID 1,793 ·
  ADDRESS 1,764 · NATIONAL_ID 1,762 · PHONE 1,763.
- 18 unit tests cover the EN module (gold-safety, no-digit-run constraint, span alignment, fallback).

## Reading

The generator-diversity fix is **not Romanian-specific** — the same gold-safe stage-B design lifts a
second language from template-collapse (0.003) to high structural diversity (0.715) with exact gold +
valid IDs. Combined with the RO F1-de-saturation confirmation, this is the empirical case that the
program's central data weakness is fixable across the language tiers, not just at home.

## Scope / follow-ups

- **v1 = English, 2000 docs, generation-only.** **Publishing** the upgraded `ds-kp-general-en` to HF
  is deferred to **RES-62** (org `HF_TOKEN` write secret).
- EN diversity (0.715) trails RO (0.909) — a v1.1 narrator-variety pass is the natural next step.
- Rollout to the remaining T1/T2 languages reuses this same locale-swap pattern.
- `config_status=dev`; cleanly-licensed (LLM-authored synthetic context, no real data subject, no
  copyrighted text); citable gated on RES-77.
