# Gateway v1, data revision 3 — draft gold guide

Original synthetic conversations, CC-BY-4.0, KlusAI / Codex. KP taxonomy 0.2.0;
RES-123 schema and frozen split IDs remain authoritative. Status remains dev.
Offsets are Unicode character positions within message text parts. Every repeat,
quote, code and tool-payload mention is annotated. A first-name signature shares
its full name’s entity ID. Obfuscated email and wrapped IBAN spans retain internal
whitespace and punctuation. PERSON is pseudonymized; other protected fields masked.

Protect personal contacts, names, national identifiers, bank/card accounts, birth
dates, private case/company/patient references, conditions and synthetic tokens.
Generic receipt line numbers, example merchant labels, product SKUs, event IDs,
amounts and public historical figures/statutes/publication dates are negatives.
These are protection annotations, not exhaustive named-entity recognition.
Each person's fields and aliases belong to their explicit local subject.

National identifiers are copied from payroll onboarding forms; routine clinical
records use MRN, condition and DOB instead. Existing locale packs generate values;
the europriv-bench registry checks them. UK NINO has format validation, no checksum.
RO/PL encoded DOB is compared in full; FR month/two-digit year and IT day/month/
two-digit year preserve encoded precision. DE/EN/ES/NL DOB is independently drawn.
No English cross-border CNP occurs in this revision. Values may coincide with real
registries; no assignment, account existence or exact street geography is verified.

Source revisions 1 and 2 and their scored reviews remain immutable. Revision 3
retains all 9,600 conversation/family/scenario/translation/subject IDs and quotas.
The new 300-document Stage A packet is for a separate reviewer; the author supplies
no scores. The coordinator mapping holds gold outside the reviewer directory.
Independent gold agreement, naturalness, artifact rates and native double review
remain unmeasured for this revision. Missing review cannot promote dev status.

## Credential-format remediation

Provider-shaped synthetic credentials were replaced with same-length provider-neutral
opaque tokens. Credential gold remains KP `SECRET`, with offsets, entity IDs and
protection unchanged. Clean inputs are pinned by Git blob ID plus file SHA-256;
`source_split` ends with `-git-blob`. This survives a single-commit history squash.
Earlier author ratings are historical and were not rerun on the sanitized text.
