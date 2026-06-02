"""LocalePack: a reusable, per-locale bundle for checksum-valid synthetic PII document generation.

This is the abstraction extracted from the original Romanian generators (``ro_generators`` /
``ro_documents``). It captures, *generically*, the three quality-moat invariants the panel review
deemed P0 — preserved here **unchanged** and shared by every locale:

1. **Offset-deterministic ``_fill``** — values are spliced into template slots and char spans are
   computed from the splice positions, so ``text[start:end] == value`` holds BY CONSTRUCTION (no
   post-hoc NER, no LLM rewrite that could shift offsets).
2. **Byte-equality assert** — every produced span is re-extracted and asserted equal to its intended
   value (``text[start:end] == value``), catching any ``_fill`` bug, before the value is dropped.
3. **Strict ``char_spans_to_bioes`` gate** — the resulting spans are projected to BIOES via the
   shared ``europriv_bench`` aligner, which fails loud on token collisions / off-by-one, then
   validated with ``validate_bioes``.

A :class:`LocalePack` bundles, per locale:
  (a) **checksum-valid identifier generators** — declared as :class:`ChecksummedID` entries pairing a
      seeded generator with its own validator, so the pack can self-test;
  (b) the offset-deterministic **doc-fill** — a ``fields(rng)`` slot builder plus weighted templates,
      consumed by the shared :func:`fill_document`;
  (c) a **checksum self-test** (:meth:`LocalePack.checksum_self_test`) that asserts every generated
      checksummed ID validates against its own validator.

``_fill`` and ``Doc`` live here (the splice IS the abstraction's core) and are re-exported from
``ro_documents`` for backward compatibility, so there is exactly one byte-equal splice across locales.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes


@dataclass
class Doc:
    text: str
    spans: list[dict]
    domain: str


def _fill(template: str, fields: dict[str, tuple[str, str]]) -> tuple[str, list[dict]]:
    """Splice values into the template, recording exact char spans. Offset-correct by construction.

    Each span keeps the intended ``value`` so the caller can byte-equality-assert against the
    re-extracted ``text[start:end]`` (catches any _fill bug), then drop it before output.
    """
    text = ""
    spans: list[dict] = []
    i = 0
    while i < len(template):
        if template[i] == "{":
            j = template.index("}", i)
            value, label = fields[template[i + 1:j]]
            start = len(text)
            text += value
            spans.append({"start": start, "end": len(text), "label": label, "value": value})
            i = j + 1
        else:
            text += template[i]
            i += 1
    return text, spans


# A slot-fields builder: rng -> {slot_name: (value, KP-label)}. Label "O" marks a filled-but-not-PII
# slot (e.g. gender-agreement boilerplate), dropped before span projection.
FieldsBuilder = Callable[[random.Random], dict[str, tuple[str, str]]]


@dataclass(frozen=True)
class ChecksummedID:
    """A self-validating identifier generator for a locale.

    ``name`` is a human-readable id-type label (e.g. "CNP", "PESEL", "IBAN"). ``generate`` is a
    seeded, deterministic generator. ``validate`` returns True iff its argument passes the id type's
    own checksum/structural rules. The pack's self-test asserts ``validate(generate(rng))`` for many
    draws — so a generator that emits structurally-invalid checksums fails loud.
    """

    name: str
    generate: Callable[[random.Random], str]
    validate: Callable[[str], bool]


@dataclass(frozen=True)
class LocalePack:
    """Everything needed to generate offset-validated synthetic PII documents for one locale.

    The pack does NOT reimplement the splice/assert/BIOES gate — those are the shared invariants in
    :func:`fill_document`. The pack only supplies locale content: identifier generators, the slot
    builder, and the (domain, template) list.
    """

    language: str                                   # ISO code, e.g. "ro", "pl", "en"
    name: str                                       # human-readable, e.g. "Romanian"
    checksummed_ids: tuple[ChecksummedID, ...]      # for the checksum self-test
    fields: FieldsBuilder                           # rng -> slot -> (value, label)
    templates: tuple[tuple[str, str], ...]          # (domain, template) — {slot} markers
    no_checksum_ids: tuple[str, ...] = field(default_factory=tuple)  # documented id types w/o checksum
    # Optional template-family identity (KLU-101): when a locale ships ≥2 *independent* template
    # families on one config, each pack tags its rows so downstream scoring can break the result
    # down per family. ``family`` is a short stable id ("A"/"B"); ``genre`` is the human label.
    family: str = ""
    genre: str = ""

    def gen_document(self, rng: random.Random) -> Doc:
        """Generate one offset-validated document via the shared splice + byte-equality + BIOES gate."""
        return fill_document(rng, self.templates, self.fields)

    def generate_dataset(self, n: int, seed: int = 0) -> Iterator[dict]:
        """Yield ``n`` offset-validated rows ({text, spans, language, domain}).

        When the pack declares a template ``family``/``genre`` (KLU-101), every row also carries
        those tags so downstream scoring can break the result down per family.
        """
        rng = random.Random(seed)
        for _ in range(n):
            d = self.gen_document(rng)
            row = {"text": d.text, "spans": d.spans, "language": self.language, "domain": d.domain}
            if self.family:
                row["family"] = self.family
                row["genre"] = self.genre
            yield row

    def checksum_self_test(self, n: int = 200, seed: int = 0) -> None:
        """Assert every checksummed id type validates against its OWN validator over ``n`` draws.

        Fails loud (AssertionError) if any generator emits an id its validator rejects — the guard
        against teaching models the wrong checksum invariants.
        """
        rng = random.Random(seed)
        for cid in self.checksummed_ids:
            for _ in range(n):
                value = cid.generate(rng)
                assert cid.validate(value), f"{self.language}:{cid.name} produced invalid id: {value!r}"


def fill_document(
    rng: random.Random,
    templates: tuple[tuple[str, str], ...],
    fields_builder: FieldsBuilder,
) -> Doc:
    """Shared, locale-agnostic document builder enforcing the three quality-moat invariants.

    This is the generic form of the original ``ro_documents.gen_document`` /
    ``ro_skeletons.gen_document`` body: pick a template, splice via ``_fill`` (offset-correct by
    construction), drop non-PII "O" slots, byte-equality-assert every span, then run the strict
    ``char_spans_to_bioes`` + ``validate_bioes`` gate.
    """
    domain, template = rng.choice(templates)
    text, spans = _fill(template, fields_builder(rng))
    spans = [s for s in spans if s["label"] != "O"]  # drop filled-but-not-PII slots
    for sp in spans:
        assert text[sp["start"]:sp["end"]] == sp.pop("value"), "offset mismatch"
    validate_bioes(char_spans_to_bioes(text, [Span(s["start"], s["end"], s["label"]) for s in spans]))
    return Doc(text=text, spans=spans, domain=domain)
