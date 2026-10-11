# klusai-datasets

Data layer for the **KlusAI Privacy (KP)** program: sourcing, **synthetic generation**,
crawling, normalization, span-alignment, and Hugging Face publishing.

Publishes:
- `klusai/ds-kp-{domain}-{lang}-{size}` — training/eval datasets (e.g. `ds-kp-legal-ro-50k`).
- `klusai/europriv-bench` — the benchmark's held-out gold data (see the `europriv-bench` repo).

## Principles

- **Cleanly-licensed only.** Build the redistributable benchmark from clean sources
  (TAB/ECHR, CC-BY AI4Privacy *open core*, MEDDOCAN, EUR-Lex, KlusAI synthetic). Exclude
  Llama-bound / NC-ND material. License is tracked per source in `conf/datasets.yaml`.
- **Synthetic generation is infrastructure, not the claim.** The research contribution is
  closing the **synthetic-to-real drift** and **multilingual legal synthesis** (Phase 2).
- **Fail loudly on bad spans.** Every example is validated by `europriv_bench.spans` (the
  shared source of truth) so an off-by-one annotation can't silently corrupt downstream F1.

## Layout

```
klusai/privacy/datasets/   package (logger, data/{synthetic,loaders,normalizers})
scripts/                   prepare_data.py, upload_dataset.py  (run: python scripts/x.py)
conf/datasets.yaml         source + synthetic dataset registry
tests/                     cross-repo contract tests (shared taxonomy/spans)
```

Import root is the PEP 420 namespace `klusai.privacy.datasets`. Shared taxonomy + span
alignment come from `europriv_bench` (installed as a dependency), never copied.

## Usage

```bash
make install && source .venv/bin/activate
make check                                   # ruff + pytest
python scripts/upload_dataset.py --help      # publish a prepared dataset to HF
```

Naming: `ds-kp-{domain}-{lang}-{size}`. Cards carry YAML frontmatter
(`language`, `license`, `task_categories: [token-classification]`, `tags: [pii, privacy, kp, {domain}]`).

## RES-77 local real-skeleton v2 candidates

Generate new RO/PL configs (1,500 documents each) and disjoint self-review/held-out
samples without HF access:

```bash
PYTHONPATH=. .venv/bin/python scripts/generate_realskeleton_v2.py --output /path/to/scratch/v2
```

Outputs are JSONL test sets, 100-document self-review samples, 300-document reserved
review samples and hashed manifests with harness integrity counts. Identical builds
resume; changed artifacts are refused. Existing v1 publishing scripts/config names
are untouched. The supplied RES-77 punctuation/contact/gender patch changes legacy
RO source generation, not published v1 artifacts; the substantive rewrite has separate
`ro_skeletons_v2.py` / `pl_skeletons_v2.py` entrypoints.

The v2 candidates cover four correspondence types in one authored family; RO's education
family B is not included. Clinical letters now describe outpatient consultations rather
than inpatient discharges. Names are adult-only, roles distinct, RO localities explicit,
and PL names use nominative identity fields. Random PL postcodes and unvalidated PL
identity-card numbers are omitted. Clinical PERSON/ORG_PARTY labels retain the v1 policy
pending independent taxonomy adjudication. Neither lexical diversity nor the old panel
and model scores transfer to these revisions. See the frozen
[self-review protocol](docs/res77-v2-review-protocol.md); both configs remain `dev`.

## Gateway traffic contract

RES-123 defines the source manifest, frozen split reservations, conversation schema
and offline coverage/training-overlap gates for `gateway-traffic-v1`.
See [the contract and audit instructions](docs/gateway-traffic-v1.md).
RES-124 now contains the full local 8,000 test / 1,600 dev conversations (status `dev`).
See [authoring and QA](docs/gateway-authoring/README.md); independent blind/native review remains open.
RES-127 adds a local 40,000-prompt TRAIN split (5,000 per language), independent train
families and subject pools, and a KP-label model export. See [train reproduction and
limitations](docs/gateway-authoring/train.md) and the [census audit](docs/gateway-authoring/train-audit.json).
