# Gateway v1 authoring guide — RES-124, draft 1

Original synthetic messages; CC-BY-4.0, KlusAI / Codex. No real traffic.
The frozen RES-123 schema, split reservations and KP 0.2.0 labels are authoritative.

Offsets are Unicode characters within a message text part. Annotate every mention,
including repetitions in quotes, JSON and tool payloads. Exclude field labels and
surrounding punctuation. An obfuscated email is one EMAIL span including internal
`[at]`/`[dot]`; a line-wrapped IBAN is one ACCOUNT_ID span including the newline.
A first-name alias shares the full name's entity ID. DOB is DATE; MRN is the local
patient-record number. Clinical conditions attached to a patient are protected.
Identifier classes come from the harness taxonomy, not a private remapping.

Protect copied private names, contacts, national IDs, financial account/card values,
DOBs, case/company/medical record identifiers and explicitly synthetic access tokens.
Mask values except PERSON, which is pseudonymized. Generic unassigned public product
codes, standard error codes, API field names, public statutes and public dates are
utility negatives, not private case IDs or dates. Public historical figures and EU
institutions in public documentation are not protected. They have no retained spans
or fictional subject IDs. This is a protection policy, not general-purpose NER.

Primary-locale identifiers use the existing locale packs and europriv-bench registry.
UK NINO has no checksum: verify format only, report separately. English legal messages
also carry an explicitly labelled Romanian CNP. Do not infer birthplace from current
address. Use decoded DOB precision: French NIR gives month/two-digit year only; Italian
CF gives day/month/two-digit year. Do not invent a day or century. Separately generated UK/DE/ES/NL DOBs have no encoded-ID claim.
Synthetic means invented, not guaranteed unassigned in real registries.

Private subjects introduced in each copied record are local to that conversation.
Language adaptations share scenario/translation-group IDs, never cross splits.
No existing training document prose or templates are used. Public scaffolding and
new prose are reused inside splits: these are template variants, not independent
realistic traffic draws. Human family/identity review remains outstanding.

QA uses a frozen sample of 300 documents, stratified across language, split and
workflow, seed 77. One Codex author self-review is explicitly nonblind and not native
human double annotation or three-family panel validation. Reuse the panel's exact-
span alpha, 2,000 document-cluster bootstrap replicates (seed 7701), rating rubric
(1 unusable, 2 major errors, 3 conspicuously artificial, 4 minor defects, 5 idiomatic),
and Wilson intervals. Bootstrap by language/split; retain individual judgments,
reasons, artifact flags and span differences. Missing judgments stay missing.
Self-review cannot establish accuracy or promote status above `dev`.

## Revision 2

Each participant now owns their own supplied fields. Public product codes, historic
biographical names, public statutory references and publication dates remain negatives.
The complete replacement revision retains the v1 IDs and split families; v1 input and
review receipts remain immutable. v2 input is under originals/v2/ and has its own commit.
Secrets have an inert opaque__ prefix; reserved example.invalid email addresses are fictional.
Repeated names in expense rows and quoted greetings resolve to the same local subject.
An IBAN wrapping across a line break is one span, including internal whitespace.
UK National Insurance numbers have no checksum; only format is tested.
No human or independent gold review is implied by this authoring guide.

## Credential-format remediation

Provider-shaped synthetic credentials were replaced with same-length provider-neutral
opaque tokens. Credential gold remains KP `SECRET`, with offsets, entity IDs and
protection unchanged. Clean inputs are pinned by Git blob ID plus file SHA-256;
`source_split` ends with `-git-blob`. This survives a single-commit history squash.
Earlier author ratings are historical and were not rerun on the sanitized text.
