# Gateway hard-negative TRAIN augmentation

15,000 original synthetic prompts: DE/PL 3,000 each; RO/EN/FR/ES/IT/NL 1,500 each.
Original KlusAI / Codex prose, CC-BY-4.0; source and attribution are in
`conf/gateway_hardneg_manifest.json`. No external corpus or real PII is imported.

Eight new train-only task families cover catalogue filtering, packaging layout,
museum-shop indexing, receipt OCR column recovery, stock UI wording, supplier field
mapping, workshop picking and bookshop displays. Each has three authored variants
per language. These tasks do not invoke heldout or parent TRAIN prose renderers.
Public words and historical figures are deliberately eligible utility negatives;
their recurrence is distinct from private subject or template leakage.

Each language preserves the parent's 20/40/30/10 percent subject-count mix:
zero, one–two, three–five and six subjects. Contact blocks occur before, inside or
after the product material. PERSON, EMAIL, PHONE and ADDRESS positives are fictional
delivery/workshop contacts. Other labels and long-form coverage remain in parent TRAIN;
this augmentation does not claim its 50/35/15 length quota or all-label coverage.
Use together with parent TRAIN, not as a replacement for it.

Product/article codes, fictional merchant labels, table/receipt headers, status
phrases, packaging instructions and public historical figures carry no protected
span. Historical figures occur on clearly described historical display cards.
The metadata preserves their exact Unicode ranges so the audit can reject masking
them. All positive occurrences are generated with exact Unicode start/end offsets.
KP rows have exactly `text`, `spans`, `language`, `domain`; each span has exactly
`start`, `end`, `label`. Metadata is a separate train-only sidecar, not a model feature.

64 new subjects per language exclude normalized private identifying surfaces in all
9,600 current dev/test and 40,000 parent TRAIN rows. Checks include family/subject IDs,
subject values, exact texts, raw and PII-masked/numeric-normalized five-word Jaccard
overlap at 0.8, with MinHash candidates supplemented by a complete prefix join.
Shared subjects across generated rows and translated tasks are not independent samples.
Provider-secret scanning includes generated artifacts, pools, prose and source code.

Reproduce locally under Python 3.13, with parent TRAIN artifacts and the cached tokenizer:

```sh
PYTHONPATH=. .venv/bin/python scripts/author_gateway_hardneg.py --resume
PYTHONPATH=. .venv/bin/python scripts/audit_gateway_hardneg.py
PYTHONPATH=. make check
```

Resume verifies the existing prefix before appending and rejects incompatible inputs.
Generated JSONL stays local/ignored under repository policy; source, manifest and
hash-bound census receipt are committed. No paid API, GPU, training or publishing is used.
One generation seed (12715), zero scoring seeds. Census counts have no sampling CI.
No harness-scored improvement, performance CI, independent native review or semantic
disjointness certification is claimed. Gold remains construction-derived and provisional.
