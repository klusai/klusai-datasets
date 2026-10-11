# gateway-traffic-v1 contract (RES-123)

This is a **manifest and validation contract**, with no conversations generated.
RES-124 authors the data. All volumes below are targets, not measured results;
`n=0`, scoring seeds=0, CIs unavailable. No quality or held-out-clean claim is made.

`conf/gateway_traffic_manifest.yaml` pins licence evidence, source URLs/revisions,
coverage requirements, the training inventory and immutable family reservations.
The original-content revision is the repository baseline, explicitly not a hash of
future prose. RES-124 must record its actual authored artifact commit per record.
The source `permitted_train` flags describe licence rights; `allowed_gateway_splits`
is the separate program policy. TAB has no allowed gateway split: keep it frozen
as an independent anchor. OpenPII remains a separate external-synthetic stratum;
it cannot fill the original-data quotas, and admission needs a full overlap review.

## Frozen assignment

RO/EN/DE/FR/ES/IT/NL/PL each reserve 1,000 test and 200 dev conversations:
8,000 test / 1,600 dev total. Eight workflows each reserve distinct train/dev/test
families; per language each test family has 125 slots and each dev family 25.
Train volume is unspecified (zero reserved slots means no volume commitment).
These are identifiers, not templates. Author each family independently: renaming
an old template or translating a sibling does **not** create a disjoint family.

`extend_ledger` imports the entire previous ledger and rejects any split conflict
for conversation, scenario, family, source document, subject, translation group
or normalized text identity. IDs must be globally stable/namespaced, shared across
translations and aliases, never regenerated just to satisfy a split. Source-document
keys deliberately omit revision, so updating upstream cannot disguise a sibling.
Conflicting components are rejected, never moved. Empty-subject hard negatives
still carry family, scenario, source-document and translation-group identities.
Persist each resulting ledger receipt; pass it back with `--prior-ledger` when
extending the release. Receipts include a parent hash and cannot be overwritten.
Freeze the complete final ledger with the release. Editing reservations requires
a new dataset version, not changing v1 in place; the test suite pins its digest.

## Schema and coverage

`conf/gateway_traffic.schema.json` is exported from the Pydantic `Conversation`
model in `klusai/privacy/datasets/data/gateway_traffic.py`. Runtime checks add exact
Unicode character offsets within each message text part, nonoverlap, coreference,
subject consistency and canonical message-content hashes. KP labels come from
`europriv_bench.taxonomy`; DOB uses DATE and medical identifiers use MRN. Features
retain the more specific coverage concepts without inventing new KP labels.
Use 1–8 role-bearing messages, explicit text parts, 32–2,048 tokens and no truncation.
Pin the counting tokenizer. RES-124 must independently verify token counts and
feature tags: these cannot be inferred reliably from text by the schema alone.

The schema requires author/tool/session, generator version, seed, prompt/content
hashes, source revision/split/record ID, source artifact SHA-256, identity provenance,
annotation guide hash and annotators/reviewers. `file_sha256` hashes the **upstream
or authored input artifact**, not the output JSONL containing that field (which
would create a self-reference). Verify input bytes before ingestion. The separate
receipt hashes the final JSONL. Status remains `dev`; provenance must never claim
synthetic data is real traffic. Native review includes two distinct reviewers and
adjudication on at least 100 conversations per language across dev+test; guide
agreement/miss analysis is a further RES-124 review requirement.

Coverage checks enumerate all 16 split/language cells, require exact 20/40/30/10
negative/small/medium/dense subject quotas and 50/35/15 short/medium/long token
quotas. Short=32–128, medium=129–512, long=513–2,048. They also require every
specified PII/utility/format feature and KP label per cell, plus native review.
Dense positives may contain any positive subject count; >5 subjects must be dense.
Keep public DATE/ORG/statute utility negatives separate from protected spans.
Feature counts are coverage assertions, not automatic gold verification.

## Training-disjointness audit and its limits

The pinned inventory includes all eight cached 50k general-language pools and
six local Stage A/B, CJEU and conservatively excluded artifacts: **14 corpora,
446,326 rows**. It records file SHA-256, row counts, cached HF commit revisions or
local content revisions, model/dataset repo revisions and training receipt hashes.
Whole pools are excluded, including rows carved out by individual training runs.
This is the observed training inventory at the recorded revisions; new inputs,
changed files or undisclosed corpora invalidate completeness and require refresh.

The offline audit requires a path for **every** inventory entry, rehashes/counts
all rows, and compares NFKC/case/whitespace-normalized held-out message/full-text
hashes. It never treats an empty candidate set as a clean evaluation set. Legacy
training rows lack global subject/document/translation IDs. Exact-text clearance
cannot prove semantic/template, alias or subject disjointness; the CLI therefore
always reports `release_ready=false` pending a documented provenance review.
The current receipt establishes inventory integrity only. Full acceptance of
train-disjoint generated content remains open for RES-124; do not bypass this by
renaming family IDs or interpreting a zero-hit/zero-candidate scan as an audit win.
The legacy pools are exclusion evidence, not newly admitted gateway sources.

Run from the repository root (Python 3.13, installed project dependencies):

```bash
python scripts/audit_gateway_traffic.py \
  --training-paths /path/to/training-paths.json \
  --output /path/to/new-audit-receipt.json
# Future candidates: add --records gateway.jsonl --prior-ledger prior-receipt.json
# --require-complete exits nonzero for missing coverage or provenance review.
make check
```

The path-map JSON maps each exact inventory corpus ID to its local file. Fetch
missing HF files at the recorded revision with `hf_hub_download`; read parquet
with pyarrow, never `load_dataset(streaming=True)` for a single-file parquet.
The audit performs no network requests, generation, training or publication.
