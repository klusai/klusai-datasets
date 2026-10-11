# Coordinator-only record — do not distribute with Stage A

The separate reviewer receives only `docs/validation/gateway-r1-sample/`.
`mapping.json` links opaque IDs to frozen source IDs and gold. `panel-rows.json`
uses opaque IDs and is ready for `europriv_bench.panel.validate_annotation`,
`candidates` and `analysis/panel_report.py:bootstrap` after real responses arrive.
Do not give these files, earlier outcomes or generator context to a Stage A judge.
No separate reviewer has yet returned responses; no new scores are assigned here.

This adapts europriv-bench main protocol at
14cfc44d5218e2f96081fc7ea8db5b07eb2880b3 (`docs/validation/panel-protocol.md`).
Adaptation: 300 gateway messages spanning eight languages and both splits replace
the protocol's 300-per-config RO/PL four-document-type samples. Seed 12403 replaces
77 for membership. Two documents per eligible language/split/workflow cell plus
random extras give 38 documents in RO/EN/DE/FR and 37 in ES/IT/NL/PL. Both earlier
samples' scenario/translation groups are excluded across all languages, irrespective
of scores. Families remain shared. This is not a population-weighted estimate.

Freeze independent Stage A outputs; align literal span occurrences with the upstream
validator (no fuzzy matching). At least one separate reviewer is necessary for the
requested handoff; a release panel still needs three independent model families,
complete A/B annotations and votes, exact-span nominal alpha >=0.80, each median
fluency/naturalness >=4 and majority artifact rate <=5%. No paid API is authorized
by this task. The coordinator must separately arrange any permitted panel execution.

Use upstream bootstrap with strata `language/split`, 2,000 replicates, seed 7701;
report each language, n, actual judge/model IDs, seed counts, medians and 95% CIs,
Wilson artifact CIs and all disagreements. Do not run its RO/PL-specific CLI's
sampling or decode path unmodified on this eight-language packet. National-ID
census checks use `scripts/check_gateway_tranche_v3.py` and the harness registry.
A single separate review cannot establish three-family panel agreement. Missing
responses stay missing; status remains dev. No replacement sample after outcomes.

Clean input Git blob IDs are in `invariants-v3.json`. The protocol and
panel/statistics files are byte-identical at europriv-bench origin/main
`4e1d64097ff761db0256ad4f3f523c42a071ccc4` (read-only check).
