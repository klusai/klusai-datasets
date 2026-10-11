# RES-77 v2 local self-review protocol

Final-build protocol frozen before generation or inspection of final-build documents, 2026-10-11.
The rubric is inherited from europriv-bench, branch res-77-panel-validation,
`docs/validation/panel-protocol.md`: 1 unusable, 2 major errors, 3 understandable
but conspicuously artificial, 4 minor defects, 5 idiomatic/plausible for the genre.
Target: median naturalness and fluency >=4 per language. No outcome-based exclusions.

Generate 1,500 documents/config with seeds 2026101277 (RO), 2026101278 (PL).
Four equally likely types: clinical letter, service contract, declaration, admin notice.
Review 100/config: 25 random documents/type without replacement, sampling seed 7711.
Reserve a further 75/type (300/config) from the remaining documents, seed 7712,
for independent re-review; do not inspect these in the author self-review.
The held-out reservation is a document holdout, not an unseen-template test.
Both sample selections are frozen and hashed before reviewing.

One Codex author/judge, one generation seed/language, one sampling seed, no paid
inference, no model training. Record per-document naturalness, fluency, artifact
flags and explanations, tied to source index and text SHA256. This is a requested
self-review, not the three-family panel, human/native-speaker review, or independent
validation. Entity extraction/adjudication/IAA from the original panel is NOT repeated.
All v2 configs remain dev. The original 300-document v1 panel outcomes remain unchanged.

Report medians with 95% percentile CIs, 2,000 document bootstrap replicates
stratified by the four types, seed 7701 (as in the original rubric); report the
artifact rate with a Wilson 95% CI. CIs capture sample variation conditional on this
judge and these templates, not author bias, template or model uncertainty. No win or
v1-v2 improvement significance claim without an independent CI-disjoint held-out delta.

Validate every generated document using strict harness BIOES projection and harness
CNP/PESEL parsing, including raw-text numeric ID coverage and explicit clinical DOB/sex
agreement. Validate generated company IDs and IBANs using existing repository validators.
Record counts and Wilson CIs. Offsets are asserted against inserted values by the shared
splice function before values are removed. No postprocessing of rendered text.

No new external data sources: original authored templates and existing local synthetic
identifier generators; no v1 text or panel sample is reused. Record source URLs,
CC-BY-4.0 data license, code/protocol hashes and file hashes in the local manifest.
No publication, independent legal/clinical review, registry/address/bank validation,
model-performance scoring, or real-record representativeness claim.

## Development-build deviation, disclosed before the final review

An initial build used seeds 2026101177/2026101178. Inspection of the fixed templates
and 150 sampled documents (100 RO, 50 PL; no held-out documents) found a Polish
preposition defect, `w Wrocławiu`, corrected to `we Wrocławiu`. That initial author
review was stopped incomplete, with no scores or pass claim. The development
protocol and artifacts are retained in scratch (`development-protocol.md`, `v2/`).
This is an explicit restart, not a claim that the original preregistration was
followed unchanged. Final seeds above are fresh, chosen before inspecting final
outputs. The final build lives in `v2-final/`; no initial artifact is overwritten.
No document will be excluded/replaced or generator edited after this final review.
Only final-build 100/config scores are reported; the failed development attempt
remains disclosed. Seed count: two builds/language, one scored final seed/language.
