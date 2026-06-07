# RES-95 v1 — stage-B narrative generator (Romanian): the templating fix, proven

**Status: `config_status=dev`. v1 proof-of-concept (Romanian only).** Closes the RES-94 root cause
(our synthetic is template-splice) via LLM-authored narrative bodies, **without** weakening the
gold-integrity moat. Not a SOTA/citable claim. Machine-readable companion:
[`res95-v1-stageb-metrics.json`](res95-v1-stageb-metrics.json).

## The fix

The template-splice generator emitted only ~6 distinct document skeletons (RES-94: unique-skeleton
ratio ~0.004), which saturates detection F1 (RES-97) and is why a synthetic-trained model fails to
transfer to real data. **Stage-B** has a **local, offline LLM** (`Qwen/Qwen3-1.7B` via `mlx-lm` —
already the `anon` LoRA base; no network, no API key, no creds) author the *surrounding narrative*,
while the **PII values stay deterministically generated + offset-spliced** by the existing
checksum-valid RO generators.

## Result (2000 RO docs, seed 20260607)

| | unique-skeleton ratio | unique skeletons / 2000 | top-skeleton share |
|---|---:|---:|---:|
| **before** (stage-A template-splice) | **0.003** | 6 | 18.0% |
| **after** (stage-B narrative) | **0.909** | 1,817 | 3.2% |
| Ai4Privacy reference | 1.0 | — | — |

The gap to Ai4Privacy-class document diversity is **almost entirely closed** (0.003 → 0.909). Measured
by the same `europriv-bench analysis/synthetic_realism_gap.py::template_repetition` method as RES-94.

## Gold integrity — byte-for-byte intact (the load-bearing constraint)

- **NATIONAL_ID spans: 2,186; invalid CNPs: 0.** The LLM **never authors a PII value** — its output
  is constrained to contain no braces and no digit runs, so it cannot smuggle a literal ID/date/phone.
- PII values come from the deterministic checksum-valid `ro_generators` and are spliced at known
  offsets; **every row passes `char_spans_to_bioes` + `validate_bioes`** (a misaligned span fails
  loud and the row is discarded — never shipped misaligned).
- 17 unit tests cover the module (gold-safety, no-digit-run constraint, span alignment).

## Reading

This is the empirical fix for the program's central data weakness: a generator that produces
**structurally diverse** documents (0.909 vs 0.004) while preserving exact gold + valid IDs. It
should de-saturate detection F1 (RES-97) and is the path to synthetic that a model can train on and
still transfer to real data.

## Scope / follow-ups

- **v1 = Romanian only, 2000 docs.** Rollout to the other languages + larger volumes, and **publishing
  the upgraded `ds-kp-general-*` to HF**, is the follow-up — the HF publish needs write creds (RES-62).
- A confirmatory **F1-de-saturation** check (train/score on a stage-B held-out) is the natural next
  measurement once rolled out.
- `config_status=dev`; cleanly-licensed (LLM-authored synthetic context, no real data subject, no
  copyrighted text); citable gated on RES-77.
