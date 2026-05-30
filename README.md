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
