# RES-124 gateway traffic — data revision 4

**8,000 test + 1,600 dev**, status **dev**. The manifest advances `data_revision` to
4 while schema version, all 9,600 IDs, family/scenario/translation/subject assignments,
per-document strata, split reservations and exact quotas remain frozen.
This is original template-authored synthetic material, not collected gateway traffic.
No release or model-performance improvement is claimed; nothing is published.

[Diagnosis](diagnosis-v3.md) and [complete cluster mapping](clusters-v3.json) account
for all 108 prior flags: repeated scaffolds 63, missing task material 20, inconsistent
context 9, forced quotations 5, inappropriate/unused PII 11. Version 3 replaces
constant-sized fixtures with runnable retry tests; varies receipt lengths/cents and
supplies merchant comparisons; removes arbitrary versions; supplies account/ticket
mapping; restricts national IDs to payroll intake; uses the queue token; and gives
mixed-language handovers an explicit purpose. New localized prose covers all eight
languages. These are corrections, not independently verified artifact-rate reductions.

## Files and reproduction

- `gateway_authoring_v3.py`, `prose-v3.json`, `annotation-guide-v3.md`: generator and draft gold conventions.
- `artifacts/gateway-traffic-v1/originals/v3/{test,dev}.jsonl`: credential-sanitized authored input revision.
- `artifacts/gateway-traffic-v1/{test,dev}.jsonl`: current strict Conversation records, each pinning its input Git blob/file SHA.
- `invariants-v3.json`: census checks of schema, token limits, offsets, IDs and encoded DOB.
- `audit-v3.json`: full pinned training-inventory scan and append-only ledger, parent `audit-v2.json`.
- `docs/validation/gateway-r1-sample/`: separate blind reviewer's input only; no author scores or gold.
- `review-v3/`: coordinator-only mapping, panel rows, sampling hashes and execution notes.

Run locally under Python 3.13, with `PYTHONPATH=.` and the repository dependencies:

```sh
python scripts/author_gateway_traffic_v3.py author --resume
# Finalize stores and pins the input blob, so squashing cannot invalidate provenance.
python scripts/author_gateway_traffic_v3.py finalize
python scripts/check_gateway_tranche_v3.py
python scripts/prepare_gateway_r1.py
make check
```

The census and handoff commands create new receipts and refuse overwrites. Existing
receipts are historical evidence, not inputs to regenerate casually. Author `--resume`
checks every existing draft before appending. Long commands log to assigned scratch.
The final audit uses every path in RES-123's pinned training inventory and imports
`audit-v2.json`; an incomplete inventory is never treated as clearance.

Input Git blob IDs and SHA-256 values are recorded in `invariants-v3.json`.
See [credential remediation](credential-remediation.md) for the authorized history rewrite.

## Revision 3 census results

| Check | Result | 95% CI / scope |
|---|---|---|
| Exact IDs, quotas, offsets and token counts | 9,600 docs; 86,664 spans; 32–1,449 tokens | Complete corpus census |
| National IDs | 20/20 valid per country across eight locales | Wilson 83.89–100% each; UK format only, others harness checksum/structure |
| Encoded DOB comparisons | RO/PL 40 full dates; FR 20 month/year; IT 20 day/month/year | All applicable comparisons agree; no invented precision |
| Training inventory | 14 pinned corpora, 446,326 rows, zero normalized exact matches | Semantic family disjointness unverified |
| Independent panel outcomes | Not measured | Scores, confidence intervals and agreement pending |

Final validation is recorded in the credential-remediation report.
One generation seed (124); one sampling seed (12403); zero new scoring seeds.
Identifier Wilson intervals describe the census check, not population accuracy.

## Separate review, pending

The fresh packet has 300 documents, sampling seed 12403: RO/EN/DE/FR 38 each and
ES/IT/NL/PL 37 each; 148 test and 152 dev. Two per eligible language/split/workflow
cell plus random extras. Every scenario/translation group from BOTH earlier samples
is excluded across all languages, irrespective of its score. The reviewer receives
opaque IDs, raw text, a neutral rubric and canonical KP taxonomy only. Gold/mapping,
generator context, prior scores and desired gate thresholds remain coordinator-only.
Do not provide the rest of this repository to a Stage A reviewer.

No independent reviewer has returned results yet. Naturalness, artifact rate, CIs
and agreement for revision 3 are unmeasured. Europriv-bench's panel procedure is
adapted explicitly in the coordinator README; a one-reviewer handoff is not a passed
three-family panel or native double annotation. Prior [tranche 1](tranche1.md) and
[tranche 2](tranche2.md) outcomes are retained as historical; credential strings and their hash bindings were sanitized without rescoring.

Long positives remain billing exports and long negatives code repros; family reuse
and language adaptations limit independence. Exact-text inventory clearance does not
establish semantic family disjointness. No real registry assignment, exact address
geography, real-traffic representativeness, native review or harness model win is
verified. One generation seed; one sampling seed; zero new scoring seeds.
Original source remains KlusAI / Codex, CC-BY-4.0; no external source was added.
