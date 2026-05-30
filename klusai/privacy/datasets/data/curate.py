"""Map source PII datasets onto the harmonized KP taxonomy (validated).

Currently: AI4Privacy open core (CC-BY-4.0). Each source row carries a ``privacy_mask`` of
``{label, start, end}`` in AI4Privacy's native labels; we map each via the shared crosswalk
(`europriv_bench.crosswalk`), keep KP-labeled char spans, and validate alignment so a bad row
fails loudly. Output rows are ``{text, spans:[{start,end,label}], language}`` — the exact
shape `europriv_bench.runner._rows_to_gold` consumes.

The mapping is a pure function (``map_ai4privacy_row``) so it's unit-tested without network.
"""

from __future__ import annotations

from collections import Counter

from europriv_bench.crosswalk import to_kp
from europriv_bench.spans import Span, char_spans_to_bioes

SCHEME = "ai4privacy"


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
