# RES-127 gateway TRAIN authoring and annotation

Original KlusAI / Codex synthetic prose, CC-BY-4.0, source URL
https://github.com/klusai/klusai-datasets. No external text source is added.
TRAIN uses the eight previously empty train family reservations (000,003,…,021).
Frozen test/dev families, IDs, quotas, schema and data revision 4 remain unchanged.

The new tasks are warranty repair scheduling, invoice instalment allocation, payroll
registration, referral handover, bicycle-damage witness intake, employee offboarding,
diagnostic-log redaction, and ferry accessibility. Their language adaptations share
family/scenario/translation IDs. They do not call a heldout prose renderer.
The original 20/40/30/10 subject and 50/35/15 length quotas apply per language.
Long positives contain invoice-allocation tables; long negatives contain executable
histogram boundary tests, independently authored from heldout retry examples.

Names use three components from new explicit lexical pools in prose-train.json.
Each language has 512 persistent fictional subjects; identifiers are deterministically
rejection-sampled against *all* heldout identifying surfaces and other train pool values.
Dates and conditions may recur and are not global identity keys. Locale generators
supply checksum-bearing IDs, not prose; no real registry assignment is asserted.
The pool artifact preserves all selected values and stable subject IDs for reproduction.

Gold follows annotation-guide-v3.md: literal Unicode offsets, canonical KP labels,
PERSON pseudonymization and masking for other protected fields. An alias in a signed
witness quotation refers to that subject. Public product/configuration numbers, public
legislative references and dates are utility negatives. Secrets use only provider-neutral
opaque values. An obfuscated email and line-broken account retain their entity identity.
Construction-time annotations have not received independent/native review.

The model export is one JSON object per line with text, spans [{start,end,label}],
language and domain="gateway". Messages/parts are joined by two newlines and offsets
are rebased accordingly. This matches the encoder backend reached by scripts/train.py
and RES-100 prepare_res100_data.py / moe.load_rows. No training or inference runs here.
Use strict train.jsonl for metadata; train-kp.jsonl is the model input, in identical order.

Reproduce with Python 3.13, repository dependencies and the locally cached pinned tokenizer:
`PYTHONPATH=. .venv/bin/python scripts/author_gateway_train.py --resume`
Then `PYTHONPATH=. .venv/bin/python scripts/audit_gateway_train.py` and `make check`.
The author verifies existing rows before resuming and refuses incompatible inputs.
Generated JSONL remains local/ignored, as required by repository policy; source and
hash-bound audit receipts are committed. No HF publication is performed.
