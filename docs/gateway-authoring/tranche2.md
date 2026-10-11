# RES-124 gateway-traffic-v1 — full second tranche

**8,000 test + 1,600 dev**, exactly 1,000/200 per RO/EN/DE/FR/ES/IT/NL/PL.
Status remains **dev**. This is original template-authored synthetic traffic, not
collected gateway traffic or 9,600 independent scenarios. Nothing was published.
The [first-tranche report](tranche1.md), original inputs and review receipts are preserved.

The [diagnosis](diagnosis-v2.md) identifies five overlapping causes from the earlier
review: forced aliases (139/300), people without roles (107/300), annotation-like
negatives (56/300), generic long correspondence (53/300), and thin source material /
stiff register (25–29/300). `prose-v2.json` and `gateway_authoring_v2.py` replace the
prose, add task-specific participant notes, executable debugging examples, public
source material and expense exports. National IDs are concentrated in copied intake
and onboarding fields; dense cases have six explicit participants and no short rows.
The scored revision still has documented defects; the diagnosis is not a claim that
every instance of all five causes has been eliminated.

## Contract and provenance

The RES-123 manifest, taxonomy, split plan, licences and reservations are unchanged.
Every split/language cell meets exact 20/40/30/10 negative/small/medium/dense proportions,
50/35/15 short/medium/long lengths, all 12 required labels and all 25 coverage features.
Each test family uses 125 slots/language; each dev family uses 25. Existing conversation,
family, scenario, translation and subject keys retain their split. The append-only
`audit-v2.json` imports and hashes `audit.json`; old source and text identities remain.
Long positive documents are accounting exports; long negatives are code reproductions.
This workflow/length correlation and shared language adaptations limit independence.

Original source attribution: KlusAI / Codex, https://github.com/klusai/klusai-datasets,
CC-BY-4.0, https://creativecommons.org/licenses/by/4.0/legalcode.en . No external prose
or new data source was added; the manifest's original-source licence applies.

- `artifacts/gateway-traffic-v1/originals/v2/{test,dev}.jsonl`: authored inputs, gold and intended strata.
- `artifacts/gateway-traffic-v1/{test,dev}.jsonl`: current strict Conversation records.
- Input provenance was re-pinned to clean artifact Git blobs during credential remediation; see `credential-remediation.md`.
- `annotation-guide-v2.md`: draft gold conventions; no human-adjudication claim.
- `review-v2/`: score-free packet, private mapping, explicit judgments, rubric and panel statistics.
- `invariants-v2.json`: whole-corpus offset, tokenizer, ID and decoded-DOB checks.
- `audit-v2.json`: full training-inventory scan, exact quotas and append-only ledger receipt.

Version-specific clarification of the inherited guide: its seed-77, exact-span-alpha
and English cross-border-CNP paragraphs describe tranche 1. In v2, English rows use
NINO only; the naturalness sample uses seed 12402 and no new gold-agreement estimate.
The procedure and limitations below supersede those inherited methodological details.

## Fresh review and its limits

The sample contains 300 documents, seed 12402: two per eligible language/split/family
cell plus random extras, then shuffled with opaque IDs. Every scenario/translation
group appearing in the earlier sample is excluded across all languages. RO/EN/DE/FR
have 38 documents each; ES/IT/NL/PL have 37 each. The packet contains only ID, language
and text. Earlier per-document ratings were not consulted while assigning new ratings.

**This is same-author self-review, not an independent blind review.** The author knew
the earlier aggregate and wrote the templates. Permission for a fresh-context agent
was requested because session instructions prohibit spawning one without explicit
user authorization; none was received during this run. No paid judge was called.
All 300 variable bodies and their shared authored context were inspected; already-read
shared paragraphs were represented by context references in the inspection view.
An initial 20-document inspection caught expense-field ownership and CSV quoting
problems before ratings. The population was corrected, sample membership retained,
and final packet/input hashes frozen before the 300 explicit judgments. There were
no exclusions or text changes after ratings. This is developmental review, not a
held-out independent validation of the authoring process. The packet is available
for a separately authorized blind reviewer; supply only packet.json and rubric.md.

The scorer executes europriv-bench main snapshot
`14cfc44d5218e2f96081fc7ea8db5b07eb2880b3`, `analysis/panel_report.py` bootstrap:
2,000 document-cluster draws stratified by language/split, seed 7701. One generation
seed, one sampling seed, zero independent judges, zero native human reviewers and
zero model-scoring seeds. CIs omit template-family, author and judge uncertainty.

| Self-review metric | n | Estimate [95% CI] |
|---|---:|---|
| Naturalness median | 300 | 4 [4, 4] |
| Fluency median | 300 | 5 [5, 5] |
| Artifact-flagged documents (Wilson) | 300 | 108/300, 36.0% [30.8%, 41.6%] |
| Each language: naturalness median | 37 or 38 | 4 [4, 4] |
| Independent annotation agreement | 0 raters | Not measured |

The descriptive naturalness threshold is met in this self-review. The artifact gate
is not met, and the requested strict blinding remains unverified. No CI-disjoint win,
independent delta, three-family panel pass, native approval or human agreement is
claimed. Alpha is null: this naturalness packet requested no new span annotation.

Residual flags include mechanical amounts (23), oversized code fixtures (22), public
version strings (14), contradictory shared context (6), forced quotation fragments (5),
missing source details and identifiers inappropriate to a workflow (e.g. tax/NINO in
clinic records). Full reasons are retained per opaque ID. Do not silently discard
these rows, replace the sample, or reuse these ratings for another text revision.

## Integrity and reproduction

All 114,056 spans match exact Python character slices. Cached pinned XLM-R token counts
are 32–1,649, without truncation or role/special-token framing. All 41 national IDs per
country pass the harness registry (UK: format only, no checksum exists), descriptive
Wilson CI [91.43%, 100%] per country. All 82 full-date, 41 FR month/year and 41 IT
partial-year DOB comparisons agree at the decoder's actual precision. Card Luhn,
subject ownership at expense-block boundaries and rectangular CSV are tested.

All 14 pinned training corpora, 446,326 rows, were hash/count checked: zero normalized
exact-text hits. Semantic family/subject/translation disjointness against legacy data
remains unverified. Native double annotation/adjudication, unannotated-entity recall,
registry issuance, bank existence, real address/postcode geography, and clinical/legal
answer correctness were not verified. No training or model-performance run occurred.

Python 3.13, existing local dependencies and the pinned cached tokenizer are required.
Use `PYTHONPATH=.` to select this worktree instead of a sibling editable installation.

```sh
python scripts/author_gateway_traffic_v2.py author --resume
python scripts/author_gateway_traffic_v2.py finalize --records-dir <scratch>/sanitized-v2
# Checker and audit receipts use exclusive output creation; keep previous receipts.
python scripts/check_gateway_tranche_v2.py
PYTHONPATH=.:BENCH_SNAPSHOT/src python scripts/review_gateway_traffic_v2.py score \
  --output docs/gateway-authoring/review-v2 --panel-root BENCH_SNAPSHOT \
  --judgments docs/gateway-authoring/review-v2/judgments.json
make check
```

For a repeated score/audit, copy the frozen inputs to a new receipt directory instead
of overwriting recorded outcomes. Final verification includes `make check`, actual
Git input-byte equality, source-to-final reconstruction, exact quotas, checksum/decode
checks and the full overlap scan. Everything remains local on res-124-gateway-traffic.
