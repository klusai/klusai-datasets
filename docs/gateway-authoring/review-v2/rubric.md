# Naturalness and fluency review

Review every document in packet.json in the language shown, in packet order.
Use only the text supplied. Do not look up authoring code, gold, earlier judgments,
comparison results, quota assignments, or acceptance targets.

Score fluency and naturalness separately on the unchanged panel scale:
1 = unusable; 2 = major errors; 3 = understandable but conspicuously artificial;
4 = minor defects; 5 = idiomatic/plausible for this document genre.

Judge whether this could be a real user request to an AI assistant with pasted
supporting material. A batch task can reasonably mention several people. Inspect
whether those people have roles, whether fields match the task, whether the input
contains what is needed to answer, and whether the local phrasing is idiomatic.
Do not penalize a reserved fictional domain solely for being reserved.
Give a concrete reason and list any template artifacts for each document.
Do not infer scores from length, language, workflow, or the presence of personal data.

Output one record per opaque ID with fluency, naturalness, reason and artifacts.
This packet asks for no PII annotation; gold agreement cannot be estimated from it.
Naturalness-only use adapts the europriv-bench panel protocol rather than claiming
its three-family annotation/adjudication procedure has been completed.
