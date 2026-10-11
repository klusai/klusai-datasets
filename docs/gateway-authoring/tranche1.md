Historical first-tranche report. Its current-record paths refer to commit d20d272,
not the subsequently rewritten v2 records. Original v1 inputs and receipts remain in place.

# RES-124 gateway-traffic-v1 — local first tranche

**2,240 test + 480 dev**, 280/60 per RO/EN/DE/FR/ES/IT/NL/PL; status **dev**.
This is an original, template-authored synthetic tranche, not recorded gateway traffic
or 2,720 independent scenarios. Sixteen separately authored dev/test workflow premises
have eight language adaptations. Shared prose is confined to its assigned split;
translations share family/scenario/translation identities. Full targets remain 8,000/1,600.

Source: KlusAI / Codex, https://github.com/klusai/klusai-datasets, CC-BY-4.0,
https://creativecommons.org/licenses/by/4.0/legalcode.en . Existing original-source
licence evidence in the manifest applies; no external data source was added.

## Artifacts and checks

- `artifacts/gateway-traffic-v1/originals/{test,dev}.jsonl`: committed authored inputs,
  including construction-time gold and intended strata. They are exempted explicitly
  from the repository's normal generated-data ignore rule for this requested handoff.
- `artifacts/gateway-traffic-v1/{test,dev}.jsonl`: strict RES-123 Conversation records.
  Each pins the real input-artifact commit and SHA-256; no self-referential hashes.
- `prose.json`: authored prompts, quoted correspondence, invoice/receipt/CV fragments.
- `annotation-guide.md`: protection policy and precision/coreference rules.
- `review/`: frozen final sample, explicit author judgments, upstream panel statistics.
- `audit.json`: final append-only split ledger, training inventory and coverage receipt.
- `invariants.json`: whole-tranche ID/decode and integrity summary.

Every split/language cell has exact 20/40/30/10 negative/small/medium/dense proportions
and exact 50/35/15 short/medium/long proportions. All 25 features and 12 required labels
occur in every cell. The frozen release targets/reservations have not been reduced.
Test uses 35 slots per family/language; dev uses 8 slots for the first four workflows
and 7 for the other four. Remaining slots are reserved, not reassigned.

Token counts sum independently encoded text parts, without role framing/special tokens,
using `FacebookAI/xlm-roberta-large` at `c23d21b0620b635a76227c604d44e43a9f0ee389`.
No truncation, model inference, training, paid API, GPU/cloud launch or publication.
English UK NINO is format-only; English legal rows also contain checksum-valid RO CNPs.
French DOB retains month/two-digit-year precision, Italian DOB day/month/two-digit-year.
Other decoded DOBs match the supplied IDs. Registry assignment, bank existence, exact
street geography and statutory eligibility of identifiers are not established.

## Self-review: descriptive, not a validation pass

The author inspected all 300 sampled variable bodies and their exact shared prose,
then corrected whitespace in Dutch email handles, ambiguous placement of secondary
names, and unverified postcode/city combinations (postcodes are omitted). Invoice/CV
excerpts were made explicit. Sample membership stayed fixed; final source hashes and
judgments were frozen after these iterative edits. This is **nonblind developmental
self-review**, not a pre-registered held-out validation of a repaired config. No pilot
rating was promoted or presented as an independent result. Inspection copies are in
RES-124 scratch. Frozen final judgments retain every accepted gold surface span.

Statistics execute europriv-bench's `panel.py` and `analysis/panel_report.py` from main
commit `14cfc44d5218e2f96081fc7ea8db5b07eb2880b3`. The RO/PL four-document-type protocol
is adapted to 8 languages × 2 splits × 8 workflow families: two draws per cell plus
random extras, 300 total, seed 77. Language/split-stratified document bootstrap uses
2,000 replicates, seed 7701. One sampling seed, one author, zero independent judges,
zero native human reviewers, zero model-scoring seeds. CIs omit family/judge uncertainty.

| Final author review metric | n | Estimate [95% CI] |
|---|---:|---|
| Exact-span nominal alpha vs construction gold | 300 docs | 1.000 [1.000, 1.000] |
| Fluency median, 1–5 | 300 docs | 4 [4, 4] |
| Naturalness median, 1–5 | 300 docs | 3 [3, 3] |
| Artifact-flagged documents, Wilson | 300 docs | 253/300, 84.33% [79.79%, 88.01%] |

Alpha is circular gold-aware approval, **not accuracy or human IAA**. Single-judge
panel-vs-panel alpha is undefined, and is recorded as null. The naturalness threshold
of 4 and artifact threshold of 5% are not met. Frequent problems: generic portal prose,
name-only alias quotations, weakly motivated extra people and short requests with too
little supporting material. No independent three-family panel or native double review
was attempted; neither can be inferred from zero span edits. Semantic training-family,
subject/alias and translation overlap against legacy corpora remains unverified.
The guide is draft, not frozen as human-adjudicated gold. No model win is claimed.

## Reproduce locally

Use Python 3.13, project/dev + `gateway` dependencies and the pinned tokenizer cached
locally. Set `PYTHONPATH=.` to select this worktree rather than a sibling editable install.

```sh
# A fresh worktree only; refuses existing data. --resume verifies every existing row.
python scripts/author_gateway_traffic.py author
# After make check and a local input commit:
python scripts/author_gateway_traffic.py finalize --source-revision INPUT_COMMIT
python scripts/review_gateway_traffic.py sample --output NEW_REVIEW_DIRECTORY
# Supply explicitly authored judgments; never fabricate a judge from gold silently.
PYTHONPATH=.:BENCH_SNAPSHOT/src python scripts/review_gateway_traffic.py score \
  --output NEW_REVIEW_DIRECTORY --panel-root BENCH_SNAPSHOT --judgments JUDGMENTS_JSON
make check
```

The scoring tool never changes status from `dev`. A release requires the remaining
volume, independent human review/adjudication, substantially more natural/diverse
prose, and documented semantic provenance clearance. Continue the existing ledger
with `--prior-ledger docs/gateway-authoring/audit.json`; never move siblings across splits.

## Final integrity and overlap receipts

Input commit: `a4646944a95db5e0cfe7ac89e6971001fdf38830`. Strict output records reconstruct
exactly from those committed inputs. There are 13,184 valid gold spans and 1,120 plain
email mentions. The cached tokenizer gives 48–804 tokens per conversation. All 14 pinned
training corpora (446,326 rows) were hash/count checked, with zero normalized exact-text
hits. This is **exact-text clearance only**, not semantic disjointness. The imported
RES-123 parent receipt is preserved in `parent-audit.json`; `audit.json` links its hash.

| Harness ID check | n | Validity [Wilson 95% CI] |
|---|---:|---|
| RO CNP, including English cross-border records | 83 | 100% [95.58%, 100%] |
| Each of DE/ES/FR/IT/NL/PL | 67 per country | 100% [94.58%, 100%] |
| UK NINO format only | 67 | 100% [94.58%, 100%] |

Decoded DOB comparisons: 72 full dates, 36 French month/year pairs, 36 Italian
day/month/two-digit-year values; all agree at the decoder's actual precision.
These are whole-tranche checks, not sampled model performance estimates. The Wilson
intervals are descriptive and do not turn deterministic synthetic validation into a
population claim. The local ID registry's checks do not prove administrative issuance.

Final verification: Python 3.13, `make check` (450 tests + ruff); whole-tranche checker;
real input-commit byte verification; final records-to-input equality; full inventory
hash/count/overlap scan. No independent recall/missed-entity score, human adjudication,
clinical/legal answer correctness, or model comparison was measured.
