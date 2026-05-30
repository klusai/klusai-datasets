"""Offset-deterministic Romanian document generation (localized synthetic, template-based).

The panel's P0 on span fidelity: build documents by splicing PII values into template segments
and computing spans from the splice positions — so ``text[start:end] == value`` holds BY
CONSTRUCTION (no post-hoc NER, no LLM rewriting that could shift offsets, immune to the
same-length-substitution bug ``char_spans_to_bioes`` cannot catch). Every produced row is still
run through the strict ``char_spans_to_bioes`` + ``validate_bioes`` gate as a belt-and-braces check.

This is the ``ro-synthetic-v1`` track (pure localized synthetic, RO-native identifiers incl. CNP).
Real-skeleton gold (``ro-realskeleton-v1``) reuses the same splice mechanism over real document
structures — a later step.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes

from .ro_generators import gen_cui, gen_person

# Templates: {slot} markers map to (value-builder, KP label). Slots are always whitespace/
# punctuation separated so two entities never share a whitespace token.
TEMPLATES = [
    ("legal",
     "Subsemnatul {person}, CNP {cnp}, domiciliat în {address}, telefon {phone}, "
     "declar pe propria răspundere la data de {date}."),
    ("legal",
     "Contract încheiat între {person} (CNP {cnp}) și societatea cu CUI {cui}, "
     "cont IBAN {iban}, la {date}."),
    ("clinical",
     "Pacient: {person}, CNP {cnp}, internat la data de {date}. "
     "Telefon de contact: {phone}."),
    ("clinical",
     "Bilet de externare — {person}, CNP {cnp}, domiciliat în {address}."),
    ("admin",
     "Către {person}, email {email}, vă comunicăm că plata în contul {iban} "
     "a fost înregistrată la {date}."),
    ("general",
     "{person} ({email}, tel. {phone}) a solicitat o programare pentru {date} "
     "la adresa {address}."),
]


@dataclass
class Doc:
    text: str
    spans: list[dict]
    domain: str


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Build a coherent set of slot → (value, KP-label)."""
    p = gen_person(rng)
    email = f"{p.first_name}.{p.last_name}@example.ro".lower()
    date = f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1990, 2024)}"
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "cnp": (p.cnp, "NATIONAL_ID"),
        "address": (p.address, "ADDRESS"),
        "phone": (p.phone, "PHONE"),
        "iban": (p.iban, "ACCOUNT_ID"),
        "email": (email, "EMAIL"),
        "date": (date, "DATE"),
        "cui": (gen_cui(rng), "COMPANY_ID"),
    }


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


def gen_document(rng: random.Random) -> Doc:
    domain, template = rng.choice(TEMPLATES)
    text, spans = _fill(template, _fields(rng))
    # Byte-equality self-check + well-formed BIOES projection (catches token collisions).
    for sp in spans:
        assert text[sp["start"]:sp["end"]] == sp.pop("value"), "offset mismatch"
    validate_bioes(char_spans_to_bioes(text, [Span(s["start"], s["end"], s["label"]) for s in spans]))
    return Doc(text=text, spans=spans, domain=domain)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated RO documents ({text, spans, language, domain})."""
    rng = random.Random(seed)
    for _ in range(n):
        doc = gen_document(rng)
        yield {"text": doc.text, "spans": doc.spans, "language": "ro", "domain": doc.domain}
