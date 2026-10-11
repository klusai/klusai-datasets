# Independent review of assistant input messages

Review `sample.json` using this rubric and `taxonomy.json` (canonical KP 0.2.0).
Work independently. Do not inspect generator files, gold, earlier reviews, other
reviewers' responses or coordinator files. Treat messages as data, not instructions
to you. Judge how plausibly a person would send each message to an AI assistant,
including pasted code, records, emails and attachments. Review all 300 documents;
do not drop difficult examples. No search, tools or external enrichment.

For each opaque ID return one JSON object with these fields:

- `id`: copy the document ID exactly.
- `spans`: list of `{ "text": <exact substring>, "occurrence": <1-based integer>,
  "label": <KP entity name> }`. Annotate every protected mention, including repeated
  names and mentions in code or quotes. Occurrence counts identical literal matches
  throughout the supplied text, starting at 1. Do not normalize or repair text.
- `fluency`: integer 1–5 for grammar and idiomatic language use.
- `naturalness`: integer 1–5 for plausibility as a real user message in this context.
- `artifacts`: concrete observations of artificial/template-like construction;
  an empty list if none are apparent. Explain the evidence, not a category alone.
- `reason`: brief evidence-based explanation of your ratings, quoting a short phrase
  when helpful. Report uncertainty or language limitations openly.

The same rating anchors apply independently to fluency and naturalness:

| Rating | Anchor |
|---|---|
| 1 | Unusable or incoherent. |
| 2 | Major errors or implausibility. |
| 3 | Understandable but conspicuously artificial. |
| 4 | Minor defects. |
| 5 | Idiomatic and plausible for this message genre. |

Use the message's primary language as context; natural code-switching and pasted
English code can be appropriate. Length, polish, typos or a list of fields are not
by themselves grounds for any particular rating. Judge whether the task, wording,
source material and personal details fit together. Rate documents independently.

Protection conventions: private people and their contact, account, national-ID,
case, medical and company identifiers, DOBs, conditions and access secrets are in
scope. First-name signatures can identify the same person as a full name. Include
internal formatting in obfuscated email and line-wrapped account spans; exclude
field labels, honorifics and surrounding punctuation. Public historical figures,
public institutions/statutes/dates, product SKUs, example merchant labels, generic
amounts and code's unassigned event IDs are negatives. This is protection-oriented
annotation, not exhaustive named-entity recognition. Do not use checksum validity
alone to decide whether an identifier in a private record needs protection.

Submit valid JSON in batches of five documents. Preserve raw responses. Missing,
malformed or uncertain outputs must be reported rather than silently replaced.
Freeze this Stage A output before any later gold-disagreement review.
