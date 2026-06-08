"""en-legal-realskeleton-v1 (RES-72): real-STRUCTURE EN court-judgment scaffolds + synthetic PII.

The English legal real-skeleton track — the RES-72 *real-skeleton* method applied to the EN court
-judgment genre, built to feed the RES-104 win-track (a general legal de-id model that GENERALIZES to
the TAB real-legal board zero-shot). Where the existing ``*-realskeleton`` packs (e.g.
``ro_skeletons_legal``) use a small handful of *authored* templates — which collapses the unique
-document-skeleton ratio toward zero (RES-94: ours EN ratio ≈ 0.004) — this track uses **real document
STRUCTURE as the scaffold**: it mines per-document *layout signatures* from real Court of Justice of
the EU (CJEU) judgments and renders each signature into authored neutral connective prose with
checksum-valid synthetic PII spliced in deterministically. Because each generated document follows a
*distinct real layout signature* (section sequence + paragraph counts), the corpus is structurally
diverse by construction — the property the generic synthetic corpus lacks.

Source + license (verified live, 2026-06-08)
--------------------------------------------
Layout signatures are mined from ``davidwickerhf/cjeu-opendata`` (config ``fulltexts``, EN rows) —
**Apache-2.0**, CJEU judgments/opinions sourced from EUR-Lex/CURIA open data. CJEU material on
EUR-Lex is additionally reusable for commercial purposes under **Commission Decision 2011/833/EU**
(editorial content CC-BY-4.0). The mined artifact ``artifacts/res72/cjeu_en_signatures.json`` stores
**only structural features** — the document type, the ordered sequence of section-heading *types*
(classified into a tiny controlled vocabulary), and paragraph counts — and **no source sentence,
heading text, party name, or identifier**. No CJEU prose is included or redistributed.

Contamination with the TAB test set (the load-bearing zero-shot guard)
----------------------------------------------------------------------
TAB is **ECHR / HUDOC** court judgments (Council of Europe). CJEU is the **Court of Justice of the
EU** — a *different court, different corpus, different document collection*. There is no document
overlap, so a model trained on CJEU-structured data and scored on TAB ECHR is a genuine zero-shot
transfer. The ECHR-derived corpora (``AUEB-NLP/ecthr_cases``, LexGLUE ``ecthr_a``/``ecthr_b``) are
the *same family* as TAB and are **excluded on contamination grounds** (and ``ecthr_cases`` is also
NC-SA, license-excluded). This is the reason the EN real-skeleton scaffold is CJEU, not ECHR.

Gold integrity (inherited, unchanged)
-------------------------------------
Every document is rendered by the shared :func:`localepack.fill_document`: PII values come from the
checksum-/format-valid EN generators (:mod:`en_generators`); the offset-deterministic ``_fill``
guarantees ``text[start:end] == value`` by construction; every span is byte-equality-asserted; the
strict ``char_spans_to_bioes`` + ``validate_bioes`` gate fails loud on any token collision. KP label
set matches the TAB crosswalk target: PERSON, CASE_NUMBER, ADDRESS, ORG_PARTY, DATE (plus NINO/IBAN
direct identifiers, which the EN generators check).

This is ``config_status=dev`` and a **scoping proof of concept** (RES-72): EN-first, ~50-doc proof
for the structural-diversity claim — NOT a full corpus and NOT published here.
"""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from pathlib import Path

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes

from .en_generators import gen_iban_gb, gen_person
from .localepack import Doc, _fill

LANGUAGE = "en"
COUNTRY = "GB"
FAMILY = "L"
GENRE = "legal (CJEU-structured EN court judgment / opinion, real-skeleton)"

# Mined real-structure signatures (layout features only — no source prose). Built by
# ``scripts/mine_cjeu_structure.py`` from davidwickerhf/cjeu-opendata (Apache-2.0), EN rows.
# Committed as package data (structure-only: no prose/PII), so the proof + tests are reproducible
# without a network fetch or the gitignored artifacts/ dir.
_SIG_PATH = Path(__file__).resolve().parent / "res72" / "cjeu_en_signatures.json"


def load_signatures(path: Path = _SIG_PATH) -> list[dict]:
    """Load the mined CJEU layout signatures (structure only). Fail loud if the cache is missing."""
    if not path.exists():
        raise FileNotFoundError(
            f"CJEU structure cache not found at {path}. Run scripts/mine_cjeu_structure.py first "
            "(mines layout-only signatures from davidwickerhf/cjeu-opendata, Apache-2.0)."
        )
    sigs = json.loads(path.read_text())
    if not sigs:
        raise ValueError(f"CJEU structure cache at {path} is empty.")
    return sigs


# --------------------------------------------------------------------------- #
# Authored connective prose — original boilerplate keyed to the layout heading TYPES. None of this
# text is copied from CJEU/EUR-Lex; it reproduces only the public, uncopyrightable section LAYOUT.
# Slots ({person} etc.) are whitespace/punctuation-separated so no two entities share a token.
# --------------------------------------------------------------------------- #
_DOCTYPE_HEADING = {
    "JUDGMENT": "JUDGMENT OF THE COURT",
    "OPINION": "OPINION OF THE ADVOCATE GENERAL",
}

# Per-heading-type authored section bodies. Each entry is a list of authored variants; the renderer
# picks one per occurrence so repeated section types do not produce identical prose.
_SECTION_BODIES: dict[str, list[str]] = {
    "PARTIES": [
        "In the proceedings between {person} , the applicant, and {org} , the defendant, "
        "the Court delivered the following ruling.",
        "The action was brought by {person} against {org} concerning the matters set out below.",
    ],
    "SUMMARY": [
        "The present case concerns an application lodged on {date} and registered under "
        "reference {case_number} .",
        "By an application registered as {case_number} and dated {date} , the matter was "
        "referred for determination.",
    ],
    "GROUNDS": [
        "The applicant, residing at {address} , submitted that the contested measure was unlawful.",
        "It was argued on behalf of {person} , of {address} , that the obligations had not been met.",
    ],
    "SECTION": [
        "The parties were notified at the address on file and invited to submit observations.",
        "The contested decision was communicated to the applicant on {date} .",
        "Correspondence in the matter was directed to {org} for the attention of the parties.",
        "The bank account designated for any reimbursement was {iban} .",
    ],
    "OPINION_HEADING": [
        "The Advocate General set out the following considerations for the Court.",
    ],
    "JUDGMENT_HEADING": [
        "The Court, having regard to the written and oral procedure, gives the following judgment.",
    ],
    "OPERATIVE": [
        "On those grounds, the Court declares the application registered as {case_number} "
        "admissible and orders that the present ruling be served on {person} on {date} .",
        "For these reasons, the Court rules that the matter referred under {case_number} be "
        "decided in favour of the party identified above, with notice to {org} .",
    ],
}

# A numbered-paragraph body (authored). Numbered paragraphs are where CJEU judgments carry the bulk
# of the recital prose; here they carry authored connective sentences with optional PII slots.
_NUMBERED_BODIES = [
    "The applicant {person} stated that the relevant events occurred on {date} .",
    "The defendant {org} contested the account given by the applicant.",
    "It is not in dispute that notice was served at {address} .",
    "Reference is made to the application registered under {case_number} .",
    "The Court observes that the procedural steps were completed in due time.",
    "The payment in issue was made to account {iban} .",
]


def _slot_fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Build the shared slot pool for one document → {slot: (value, KP-label)}.

    PII values come from the checksum-/format-valid EN generators. Labels are the TAB-crosswalk KP
    types (PERSON / CASE_NUMBER / ADDRESS / ORG_PARTY / DATE) plus the direct-identifier IBAN.
    """
    p = gen_person(rng)
    year = rng.randint(1990, 2024)
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "org": (rng.choice(_ORGS), "ORG_PARTY"),
        "address": (p.address, "ADDRESS"),
        "case_number": (f"{rng.randint(1, 999)}/{year % 100:02d}", "CASE_NUMBER"),
        "date": (f"{rng.randint(1, 28)} {rng.choice(_MONTHS)} {year}", "DATE"),
        "iban": (gen_iban_gb(rng), "IBAN"),
    }


_ORGS = [
    "the Commission of the European Communities", "the Exemplar Trading Authority",
    "the Office for Example Affairs", "the Example National Agency", "Example Holdings Ltd",
]
_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _render_signature(sig: dict, rng: random.Random) -> str:
    """Render one mined layout signature into an authored EN judgment template with {slot} markers.

    The signature dictates the *structure*: document-type heading, the ordered sequence of section
    heading types, and the number of numbered paragraphs. The prose is authored (not from CJEU).
    Each (value-bearing) slot name is made unique per occurrence (``person#3``) so a slot pool with
    one value per name still produces a valid byte-equal splice and BIOES sequence.
    """
    parts: list[str] = []
    counter: dict[str, int] = {}

    def uniq(template_str: str) -> str:
        # Make every slot occurrence unique so the same logical value can appear once; the field
        # builder expands these back. {person} -> {person#0}, next -> {person#1}, ...
        out = []
        i = 0
        while i < len(template_str):
            if template_str[i] == "{":
                j = template_str.index("}", i)
                name = template_str[i + 1 : j]
                counter[name] = counter.get(name, -1) + 1
                out.append("{" + f"{name}#{counter[name]}" + "}")
                i = j + 1
            else:
                out.append(template_str[i])
                i += 1
        return "".join(out)

    parts.append("IN THE MATTER OF APPLICATION " + uniq("{case_number}"))
    parts.append(_DOCTYPE_HEADING.get(sig["doctype"], "JUDGMENT OF THE COURT"))
    for htype in sig.get("heading_seq", []):
        bodies = _SECTION_BODIES.get(htype, _SECTION_BODIES["SECTION"])
        parts.append(uniq(rng.choice(bodies)))
    n_num = min(int(sig.get("n_numbered_paras", 0)), 20)
    for k in range(n_num):
        parts.append(f"{k + 1}. " + uniq(rng.choice(_NUMBERED_BODIES)))
    return "\n\n".join(parts)


def _expand_fields(template: str, rng: random.Random) -> dict[str, tuple[str, str]]:
    """Expand the per-occurrence unique slot names (``person#3``) into concrete (value, label) pairs.

    Distinct PII subjects: each unique occurrence gets a freshly generated value so the document
    contains many distinct entities (like a real judgment), and every span is independently valid.
    """
    names = {m for m in _iter_slot_names(template)}
    fields: dict[str, tuple[str, str]] = {}
    for name in names:
        base = name.split("#", 1)[0]
        pool = _slot_fields(rng)  # fresh values per occurrence
        fields[name] = pool[base]
    return fields


def _iter_slot_names(template: str) -> Iterator[str]:
    i = 0
    while i < len(template):
        if template[i] == "{":
            j = template.index("}", i)
            yield template[i + 1 : j]
            i = j + 1
        else:
            i += 1


def gen_document(rng: random.Random, signatures: list[dict] | None = None) -> Doc:
    """Generate one offset-validated EN CJEU-real-skeleton document (byte-equality + strict BIOES)."""
    sigs = signatures if signatures is not None else load_signatures()
    sig = rng.choice(sigs)
    template = _render_signature(sig, rng)
    fields = _expand_fields(template, rng)
    text, spans = _fill(template, fields)
    spans = [s for s in spans if s["label"] != "O"]
    for sp in spans:
        assert text[sp["start"] : sp["end"]] == sp.pop("value"), "offset mismatch"
    validate_bioes(char_spans_to_bioes(text, [Span(s["start"], s["end"], s["label"]) for s in spans]))
    return Doc(text=text, spans=spans, domain="legal")


def generate_dataset(n: int, seed: int = 0, signatures: list[dict] | None = None) -> Iterator[dict]:
    """Yield ``n`` offset-validated EN CJEU-real-skeleton rows (RES-72 proof).

    Each row carries ``country='GB'`` (EN/UK PII), ``family='L'``, ``genre`` and ``domain='legal'``.
    """
    rng = random.Random(seed)
    sigs = signatures if signatures is not None else load_signatures()
    for _ in range(n):
        d = gen_document(rng, sigs)
        yield {
            "text": d.text,
            "spans": d.spans,
            "language": LANGUAGE,
            "country": COUNTRY,
            "domain": d.domain,
            "family": FAMILY,
            "genre": GENRE,
        }


__all__ = ["gen_document", "generate_dataset", "load_signatures", "LANGUAGE", "COUNTRY"]
