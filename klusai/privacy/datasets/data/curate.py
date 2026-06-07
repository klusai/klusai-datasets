"""Map source PII datasets onto the harmonized KP taxonomy (validated).

Two sources today:

* **AI4Privacy open core** (CC-BY-4.0). Each source row carries a ``privacy_mask`` of
  ``{label, start, end}`` in AI4Privacy's native labels; we map each via the shared crosswalk
  (`europriv_bench.crosswalk`), keep KP-labeled char spans, and validate alignment so a bad row
  fails loudly.
* **TAB — Text Anonymization Benchmark** (Pilán et al. 2022, *Computational Linguistics* 48(4);
  MIT-licensed DATA, NOT CC-BY). 1,268 real ECHR English court judgments, manually annotated. See
  :func:`map_tab_document`.

Output rows are ``{text, spans:[{start,end,label, ...}], language}`` — the exact shape
``europriv_bench.runner._rows_to_gold`` consumes (it reads only start/end/label; any extra
per-span fields — e.g. TAB's ``identifier_type``/``entity_id`` — ride along untouched).

The mappings are pure functions so they're unit-tested without network.
"""

from __future__ import annotations

from collections import Counter

from europriv_bench.crosswalk import to_kp
from europriv_bench.spans import Span, char_spans_to_bioes

SCHEME = "ai4privacy"
TAB_SCHEME = "tab"

# TAB `identifier_type` values that must be masked (anonymisation targets). NO_MASK is NOT a
# detection target (the TAB scheme: "masked if DIRECT or QUASI, NO_MASK otherwise"), so we keep
# only DIRECT+QUASI as gold spans — including NO_MASK would penalise a model for not masking a
# non-identifier. We PRESERVE the per-span identifier_type so the QI channel (RES-88) can read it.
TAB_MASK_TYPES = frozenset({"DIRECT", "QUASI"})


def map_ai4privacy_row(text: str, privacy_mask: list[dict], dropped: Counter | None = None) -> dict:
    """Map one AI4Privacy row to a KP gold row. Unmapped native labels are dropped (counted).

    Raises ValueError (via span alignment) if the produced spans don't align to ``text``.
    """
    kp_spans: list[dict] = []
    for m in privacy_mask:
        native = m["label"]
        kp = to_kp(SCHEME, native)
        if kp is None:
            if dropped is not None:
                dropped[native] += 1
            continue
        kp_spans.append({"start": int(m["start"]), "end": int(m["end"]), "label": kp})

    # Validate alignment now (fail loud) — also catches overlaps/off-by-one.
    char_spans_to_bioes(text, [Span(s["start"], s["end"], s["label"]) for s in kp_spans])
    return {"text": text, "spans": kp_spans}


# --- TAB (Text Anonymization Benchmark) -------------------------------------------------------
# TAB stores per-document annotations keyed by annotator. dev/test docs carry up to 10 annotators;
# train docs are mostly single-annotator. TAB's own evaluation micro-averages recall over
# annotators, but our harness gold is a SINGLE non-overlapping BIOES tag sequence per doc, so we
# select ONE canonical annotator per document: the first quality-checked annotator (TAB's
# `quality_checked` = annotators whose work was revised/verified), falling back to the
# lexicographically-first annotator when none is flagged. This yields a clean single-annotator gold
# consistent with the strict (no-overlap) span→BIOES contract.


def pick_tab_annotator(doc: dict) -> str:
    """Pick the canonical annotator for a TAB document: first quality-checked, else first by name."""
    annotations = doc["annotations"]
    for ann in doc.get("quality_checked") or []:
        if ann in annotations:
            return ann
    return sorted(annotations)[0]


def _resolve_nested(spans: list[dict]) -> list[dict]:
    """Drop spans nested in / overlapping a longer kept span (longest-wins) → non-overlapping set.

    TAB legitimately nests mentions (e.g. ORG "Church of Sweden" inside DEM "...member of the
    Church of Sweden", or a short ORG inside a longer parenthetical ORG). Strict BIOES forbids
    char overlaps, so we keep the OUTERMOST (longest) mention — the full identifier span — and drop
    nested sub-spans. Deterministic: sort by start, then longest first; admit a span only if it
    overlaps no already-admitted span.
    """
    ordered = sorted(spans, key=lambda s: (s["start"], -(s["end"] - s["start"])))
    kept: list[dict] = []
    for s in ordered:
        if any(not (s["end"] <= k["start"] or s["start"] >= k["end"]) for k in kept):
            continue
        kept.append(s)
    return kept


def map_tab_document(
    doc: dict,
    dropped: Counter | None = None,
    annotator: str | None = None,
) -> dict:
    """Map one TAB ECHR document to a KP gold row (single canonical annotator).

    Keeps DIRECT+QUASI mentions (NO_MASK dropped — not a detection target), maps ``entity_type``
    via the shared ``tab`` crosswalk (unmapped types — DEM/QUANTITY/MISC — dropped + counted in
    ``dropped``), de-duplicates identical offsets, and resolves nested mentions (longest-wins) to a
    non-overlapping set. Each output span carries ``identifier_type`` (DIRECT/QUASI — the re-id /
    residual-distinctiveness signal) and ``entity_id`` (TAB co-reference) alongside start/end/label.

    Raises ValueError (via ``char_spans_to_bioes``) when the spans don't align to a single
    whitespace-token BIOES — e.g. two char-disjoint TAB mentions inside one whitespace token
    ("14553-14554/89"). That is a tokenisation limit, NOT an offset error (TAB offsets are exact);
    the caller drops + counts such documents rather than shipping misaligned gold.
    """
    ann = annotator or pick_tab_annotator(doc)
    text = doc["text"]
    seen: set[tuple[int, int]] = set()
    kp_spans: list[dict] = []
    for m in doc["annotations"][ann]["entity_mentions"]:
        if m["identifier_type"] not in TAB_MASK_TYPES:
            continue
        kp = to_kp(TAB_SCHEME, m["entity_type"])
        if kp is None:
            if dropped is not None:
                dropped[m["entity_type"]] += 1
            continue
        key = (int(m["start_offset"]), int(m["end_offset"]))
        if key in seen:  # same annotator repeats identical offsets across coref mentions
            continue
        seen.add(key)
        kp_spans.append({
            "start": key[0],
            "end": key[1],
            "label": kp,
            "identifier_type": m["identifier_type"],
            "entity_id": m.get("entity_id"),
        })

    kp_spans = _resolve_nested(kp_spans)
    kp_spans.sort(key=lambda s: s["start"])

    # Validate alignment now (fail loud): byte-equality is guaranteed by TAB (offsets are exact),
    # this also enforces strict no-overlap + whitespace-token BIOES integrity.
    char_spans_to_bioes(text, [Span(s["start"], s["end"], s["label"]) for s in kp_spans])
    return {"text": text, "spans": kp_spans, "doc_id": doc.get("doc_id"), "annotator": ann}
