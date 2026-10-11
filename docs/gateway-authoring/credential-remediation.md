# Provider-neutral credential remediation

GitHub push protection rejected synthetic provider-shaped credentials. No bypass,
allowlist approval or push was attempted here. Every affected tranche 2/3 token
was regenerated as `opaque__` plus the same deterministic 24 hexadecimal digits:
96 bits of synthetic token material, no provider prefix, same character length.
These are fixtures, not cryptographically secure credentials for deployment.

Each input revision changes 216 test and 48 dev documents (264 credential spans).
The 9,600 current records retain all 264 credential spans under canonical KP
`SECRET` (the frozen taxonomy's credential label), including masking, subject/entity
IDs and exact offsets. All split IDs, memberships, subject/length quotas and review
sample membership stay fixed. Manifest data revision advances to 4. Token counts,
artifact/content hashes, guide hashes, inventory audits and review bindings were
recomputed. Tranche 1's already provider-neutral values remain unchanged.

The seven affected historical review-v2 judgments retain their original text hash
in `pre_sanitization_text_sha256` and explicitly say they were not rescored. Their
old ratings are historical observations, not new scores for cleaned text. The
300-document independent Stage A packet stays unscored, with the same opaque IDs
and membership; its one affected message and gold mapping were sanitized together.

`credential_scan.py` conservatively mirrors the requested families: Stripe secret
and restricted keys (including test), AWS access IDs, GitHub tokens, Slack tokens,
Google API keys, OpenAI tokens, signed JWTs and PEM private keys. Only the exact
AWS-documented example named in the task is exempt. The regression tests construct
positive examples at runtime so they do not commit another scanner-triggering key.
The census scans every file under `artifacts/` plus every tracked file, including
JSONL and review packets; findings show location/family, never secret values.
[GitHub's supported-pattern documentation](https://docs.github.com/en/code-security/reference/secret-security/supported-secret-scanning-patterns)
lists detector families, not its complete production regexes. Local coverage is
not proof of server-side acceptance; no new GitHub push was performed.

## Provenance and history

The requested single commit cannot contain its own commit hash. Clean tranche 2/3
inputs are therefore pinned by Git blob object ID in `source_revision`, alongside
SHA-256 in `file_sha256`; `source_split` explicitly ends with `-git-blob`. Git stores
those same blobs in the final commit, so the pins survive cloning and history
rewrites. Historical tranche-1 commit/path pins remain supported. No obsolete local
commit is required to validate the cleaned inputs. This changes no schema fields.

The final branch contains one new commit atop `origin/res-124-gateway-traffic`
(`d20d2722e65e001491b86a28c484cc4e6d792d32`), replacing all local tranche 2/3 commits.
Only this branch's reachable history is rewritten; no shared worktree, remote ref,
reflog, or repository object store is purged. Removed commits must not be pushed
through another ref. No backup tag or branch was created for contaminated history.

Validation: `scripts/scan_artifact_credentials.py`, both census checks and full
training-inventory audits, `make check`, and scans of `git log -p` before/after the
single clean commit. Assigned scratch holds command logs and the five-line report.
No new quality score, model-performance claim or independent panel result is made.
