# RES-77 RO/PL v2: local build and author self-review

The requested **median naturalness >=4** target is met in the author self-review,
but **neither config passes the full panel protocol**. Both remain `dev`.
Contract naturalness remains below target by stratum. No independent improvement,
model-performance win, native-speaker validation or gold-annotation accuracy claim.

## Artifacts and provenance

- Branch: `res-77-ro-generator-v2`; local commit only. No HF upload, push or PR.
- Main checked first: no existing v2 generation. Supplied RES-77 RO patch applied.
- Final configs: 1,500 documents each, seeds **2026101277 RO / 2026101278 PL**.
- Scratch root: `/Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/ro-gen-v2`.
  Final artifacts: `v2-final/{ro,pl}-realskeleton-v2/`: `test.jsonl`, `manifest.json`,
  `self-review.jsonl` and `heldout-review.jsonl`.
- Exactly 100 reviewed/config, 25 random/type, sampling seed 7711. A disjoint 300/config
  (75/type, seed 7712) is reserved for independent re-review and was not inspected.
  This is a document holdout inside each generated test corpus, not an unseen-family test.
- Two builds/language; **one scored final seed/language**, one author/judge, no repeated
  inference seeds. Initial development build retained under `v2/`; its incomplete review
  found Polish `w Wrocławiu`, fixed to `we Wrocławiu`. The restart is explicitly disclosed
  in the [frozen final protocol](../res77-v2-review-protocol.md). No final-sample substitutions.
- Reviewed fixed template prose and all sampled rendered variable lines, with the three
  clinical histories/plans read in full in source. Repeated literal text was suppressed
  by a scratch reading aid, not scored by a heuristic. Per-document judgments, reasons,
  excerpts and hashes are in the two `*-self-review.csv` files alongside this report.
- Independent stage-A extraction, stage-B adjudication and Krippendorff alpha were not run.
  PERSON/ORG_PARTY clinical labels retain v1 policy pending independent adjudication.

## Results

95% median CIs: 2,000 document-cluster bootstrap replicates stratified by type, seed 7701.
Proportion CIs: harness `wilson_interval`. These are equal-stratum sample estimates.

| Measure | RO | PL |
|---|---:|---:|
| Reviewed documents | 100 | 100 |
| Median naturalness, bootstrap CI | 4 [4, 4] | 4 [4, 4] |
| Median fluency, bootstrap CI | 5 [5, 5] | 5 [5, 5] |
| Naturalness >=4, Wilson CI | 75/100; 65.70–82.45% | 77/100; 67.85–84.16% |
| Author artifact flags, Wilson CI | 50/100; 40.38–59.62% | 49/100; 39.42–58.65% |
| Contract naturalness median, n=25 | 3 | 3 |
| Other three strata naturalness median, n=25 each | 4 | 4 |
| Strict harness BIOES, Wilson CI | 1500/1500; 99.745–100% | 1500/1500; 99.745–100% |
| Harness-valid decoded CNP/PESEL subjects, Wilson CI | 1130/1130; 99.661–100% | 1110/1110; 99.655–100% |
| Raw numeric ID mentions with exact NATIONAL_ID coverage | 1130/1130 | 1110/1110 |
| Clinical DOB/sex agreement, Wilson CI | 371/371; 98.975–100% | 352/352; 98.920–100% |
| Valid IBANs, Wilson CI | 417/417; 99.087–100% | 378/378; 98.994–100% |
| Valid company IDs, Wilson CI | 417/417; 99.087–100% | 756/756; 99.494–100% |

Every generated span also passed the shared splice `text[start:end] == inserted_value`
assertion. The harness parses every CNP/PESEL; checksum validators for IBAN and company
IDs come from the repository. No failures or dropped documents. Raw-ID coverage uses
standalone 13/11-digit sequences; it does not claim detection of arbitrary ID-like strings.
Degenerate median CIs reflect tied ordinal ratings and four fixed templates; they do
**not** establish certainty or cover author bias/model/family uncertainty. Artifact rates
are single-author flags, not three-judge majority votes; a full panel pass is unavailable,
and these flags already exceed the original <=5% threshold substantially.

## Remaining issues and practical limits

- **On-site contract geography:** all 25 RO and 23 PL sampled contracts pair different
  supplier/customer cities without a local branch or travel arrangement for a small fixed-fee
  computer setup. These received 3/5, not a passing rating. E.g. RO row 170: Iași/Constanța;
  PL row 35: Kraków/Poznań. PL rows 1128 and 1223 are same-city and received 4/5.
- **Clinical detail:** all 25 sampled letters/language omit objective measurements or a
  detailed examination and give generic follow-up advice. Specialty/diagnosis coherence is
  fixed, but a richer clinically reviewed case bank is still needed. These received 4/5
  with an artifact flag. No independent clinical plausibility review was performed.
- **Calendar:** dates are unconstrained. PL admin row 1068 is dated 25 December; routine
  processing without an automated-response explanation is questionable (flagged, 4/5).
- **Register/completeness:** RO declaration's own-responsibility heading is heavy for an
  address preference; identity-card apposition is compressed. Admin responses lack concrete
  file descriptions/timing. PL correspondence addresses omit postcodes. Minor defects, 4/5.
- **Distribution:** one family, four fixed templates, three clinical cases, small recurring
  name/company pools, uniform fees/dates and synthetic email conventions. No real-record
  representativeness, structural-diversity or cross-family generalization was measured.
- **Scope changed:** outpatient consultations replace discharge summaries; RO education
  family B and repeated CASS/PESEL mentions are not in v2. PL ID-card numbers were omitted
  rather than reusing v1's format-only generator. No v1 model scores transfer.
- **External validity:** checksum validity is not an assigned ID, bank code, telephone range,
  real facility, street-city pair, or legally sufficient document. None was registry-verified.
  No new external corpus was used; original prose plus existing synthetic generators,
  CC-BY-4.0 data provenance recorded with source URLs in each manifest.

## Reproduction and checks

From the repository root, with Python 3.13:

```bash
PYTHONPATH=. .venv/bin/python scripts/generate_realskeleton_v2.py --output <scratch>/v2-final
PYTHONPATH=. .venv/bin/python scripts/score_realskeleton_review.py \
  --samples <scratch>/v2-final --output <scratch>/review-results.json
make check
```

Generation resumes identical artifacts and refuses changed bytes. The scoring script
verifies annotation/sample hashes and only summarizes the fixed CSV ratings; it does
not replace the author judgment with automated rules. Build manifests with full source
and artifact hashes are copied beside this report. The initial full test run exposed
stage-B fallback incompatibility with the supplied gender patch; grammar slots were
added without changing narrator-required PII, and unsupported fallbacks now fail closed.
