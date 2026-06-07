"""Stage-B narrative generation for English (RES-95) — LLM-authored *bodies*, code-injected PII.

This is the English sibling of :mod:`ro_stageb`. It exists to prove the stage-B upgrade is
**language-agnostic**: the exact same gold-safety design that closed the RO templating gap
(unique-skeleton ratio 0.004 → 0.909) is applied to a second language with only the *locale content*
swapped — English narrative prompts and the English LocalePack's checksum-valid PII generators.

Why this exists
---------------
The stage-A EN generator (:mod:`en_documents`) splices PII into a fixed handful of templates, so the
unique-document-*skeleton* ratio collapses just as it did for RO (RES-94). Stage-B raises document
diversity toward Ai4Privacy by having a **local, offline LLM author the surrounding narrative** while
keeping the stage-A gold-integrity moat **byte-for-byte intact**:

  * The LLM writes ONLY the document body, emitting our ``{slot}`` placeholders verbatim — it never
    authors a PII *value*. So no hallucinated/invalid NINO/IBAN can ever enter the gold.
  * The PII values are produced deterministically by the existing format-/checksum-valid EN
    generators (:func:`en_generators.gen_person` etc.) and spliced by the SAME offset-deterministic
    :func:`localepack._fill` used in stage-A. ``text[start:end] == value`` holds BY CONSTRUCTION.
  * Every row still passes the strict ``char_spans_to_bioes`` + ``validate_bioes`` gate inside
    :func:`localepack.fill_document`. A misaligned span fails loud; the row is discarded, never
    silently emitted.

The LLM-authored template is treated as untrusted text and **sanitized hard** before splicing
(:func:`_sanitize_template`): the body must contain each required slot at least once, no unknown
slot, no stray braces, and **no digit runs** (so the model cannot have smuggled a literal
id/date/phone into the static prose — only our placeholders carry such values). A body that fails
sanitization is retried; after ``max_retries`` we fall back to a stage-A template so generation never
stalls or thrashes.

The sanitizer/splice/validation path is byte-for-byte the same logic as :mod:`ro_stageb`; only the
locale content (slots, value builder, prompts, genres) differs. NINO is format-valid only (the
scheme defines no arithmetic checksum); IBAN-GB (mod-97) and the payment card (Luhn) are genuinely
checksum-valid — see :mod:`en_generators`.

LLM access (RES-95 bound)
-------------------------
The only LLM used is a **local, offline** model loaded via ``mlx-lm`` from the on-disk Hugging Face
cache (default: ``Qwen/Qwen3-1.7B``). No network, no API key, no external paid endpoint. ``mlx-lm``
is an optional extra (``.[stageb]``); the module imports it lazily so the repo's core stays
dependency-free.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from .en_documents import TEMPLATES as STAGE_A_TEMPLATES
from .en_generators import (
    card_valid,
    gen_card,
    gen_iban_gb,
    gen_person,
    iban_gb_valid,
    nino_format_valid,
)
from .localepack import Doc, fill_document

# The slots stage-B may ask the LLM to weave in. Each maps to (value-builder, KP label) — the SAME
# coherent person used across slots so the document stays internally consistent, exactly as
# en_documents._fields does. NINO is the English NATIONAL_ID; IBAN is an ACCOUNT_ID; email/date are
# digit-bearing-but-placeholder-carried values.
REQUIRED_SLOTS = ("person", "nino", "address", "phone", "iban", "email", "date")

# Genres the LLM is asked to write — the diversity driver. Plain EN/UK administrative/everyday
# document types; the LLM's free prose around the slots is what makes each skeleton structurally
# unique.
GENRES: tuple[str, ...] = (
    "an official letter from a local council",
    "a request to a public authority",
    "an internal email to the human resources department",
    "an overdue-payment reminder notice",
    "a complaint to the local police",
    "an invitation to a board meeting",
    "an employment verification letter",
    "a customer complaint",
    "an administrative decision",
    "a leave-of-absence request",
    "a submission lodged with a registry office",
    "an internal information memo",
    "a notice of meeting",
    "a freedom-of-information request",
    "an appointment confirmation",
    "a tenancy reference letter",
)

_SYSTEM_PROMPT = (
    "You are an assistant who drafts realistic and varied British administrative documents. "
    "You write ONLY the body of the document, in correct British English. "
    "You MUST use each of these placeholders EXACTLY once, literally with the curly braces, without "
    "altering them: {person}, {nino}, {address}, {phone}, {iban}, {email}, {date}. "
    "STRICT RULES: never write any real personal name, telephone number, National Insurance number, "
    "IBAN, email address, calendar date, or address — always put the corresponding placeholder "
    "instead. Do NOT use ANY digit anywhere in the prose. Do not write code, JSON, numbered lists, "
    "or markup. Vary the structure, tone and vocabulary strongly from one document to the next. "
    "Write between 2 and 5 sentences, as a single coherent paragraph or short document."
)

# Validation regexes for the LLM body (applied AFTER the slots are removed for the digit check).
_SLOT_RE = re.compile(r"\{([a-z_]+)\}")
_ANY_BRACE_RE = re.compile(r"[{}]")
_DIGIT_RE = re.compile(r"\d")
# Cheap "looks like leaked code/markup" guard.
_BAD_FRAGMENTS = ("```", '"subject"', "<", "/>", "http")


@dataclass
class StageBConfig:
    """Config for the EN stage-B run. ``n`` rows, seeded; small batches only (RES-95 PoC bound)."""

    n: int
    seed: int = 0
    model_id: str = "Qwen/Qwen3-1.7B"   # local HF-cache id; offline mlx-lm load
    max_tokens: int = 260
    temperature: float = 0.9
    top_p: float = 0.95
    max_retries: int = 2                 # LLM body re-draws before deterministic fallback
    domain: str = "general"
    family: str = "stageb"
    genre: str = "en-stageb-narrative-v1"


# --------------------------------------------------------------------------- #
# Local, offline LLM client (lazy mlx-lm import; no network, no API key)
# --------------------------------------------------------------------------- #
@dataclass
class MlxNarrator:
    """Thin wrapper over a local mlx-lm model used ONLY to author document bodies.

    Holds the loaded model/tokenizer and a seeded sampler. ``write_body`` returns the raw model
    text for one (genre, slots) request — it never sees or emits PII values, only ``{slot}`` markers.
    """

    model_id: str
    temperature: float = 0.9
    top_p: float = 0.95
    max_tokens: int = 260
    _model: object = field(default=None, repr=False)
    _tok: object = field(default=None, repr=False)

    def load(self) -> MlxNarrator:
        """Lazily import mlx-lm and load the model from the offline HF cache (fail loud if absent).

        Forces HF offline mode so the load is guaranteed network-free: the model must already be in
        the on-disk cache (RES-95 bound — no new credentials/endpoints, no download).
        """
        import os

        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        try:
            from mlx_lm import load
        except ImportError as exc:  # pragma: no cover - exercised only without the optional extra
            raise RuntimeError(
                "stage-B needs the local LLM extra: `pip install 'kp-datasets[stageb]'` "
                "(installs mlx-lm). No network/API is used; the model loads from the HF cache."
            ) from exc
        self._model, self._tok = load(self.model_id)
        return self

    def write_body(self, genre: str, slots: tuple[str, ...], seed: int) -> str:
        """Author one EN document body for ``genre`` that weaves in each ``{slot}`` exactly once."""
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        slot_list = ", ".join("{" + s + "}" for s in slots)
        user = (
            f"Draft {genre}. Use each of these placeholders exactly once: {slot_list}."
        )
        prompt = self._tok.apply_chat_template(
            [{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": user}],
            add_generation_prompt=True,
            tokenize=False,
            enable_thinking=False,
        )
        sampler = make_sampler(temp=self.temperature, top_p=self.top_p)
        # mlx-lm uses a global RNG; seed per-call so a (seed, i) pair is reproducible.
        import mlx.core as mx

        mx.random.seed(seed)
        return generate(
            self._model, self._tok, prompt=prompt, max_tokens=self.max_tokens, sampler=sampler,
            verbose=False,
        )


# --------------------------------------------------------------------------- #
# Template sanitization — the gate that keeps LLM output safe to splice
# --------------------------------------------------------------------------- #
def _sanitize_template(body: str, required: tuple[str, ...]) -> str | None:
    """Return a clean splice-ready template, or ``None`` if the LLM body is unusable.

    A body is accepted only if, after trimming, it:
      * contains no leaked code/markup fragments;
      * contains every required slot AT LEAST once and NO unknown slot (a repeated slot is allowed —
        a person/id recurring in a document is realistic, and every occurrence is spliced with the
        SAME valid value, so gold stays byte-exact);
      * has no stray ``{``/``}`` beyond well-formed ``{slot}`` markers;
      * contains NO digit anywhere outside the slots (so the model cannot have smuggled a literal
        id/date/phone into the static prose — only our placeholders carry digit-bearing values).

    These guarantees mean the subsequent :func:`localepack._fill` splice produces exactly the
    intended PII spans and nothing the model wrote can masquerade as (or corrupt) a gold value.
    """
    body = body.strip()
    if not body or len(body) > 2000:
        return None
    low = body.lower()
    if any(frag in low for frag in _BAD_FRAGMENTS):
        return None

    found = _SLOT_RE.findall(body)
    # Every required slot present at least once, and no unknown slot type.
    if set(found) != set(required):
        return None
    # No brace characters other than the well-formed {slot} markers we just matched.
    if len(_ANY_BRACE_RE.findall(body)) != 2 * len(found):
        return None
    # No digits outside the slots: strip the placeholders, then assert digit-free.
    stripped = _SLOT_RE.sub(" ", body)
    if _DIGIT_RE.search(stripped):
        return None
    # Collapse runs of whitespace the model may have left; keep it a single tidy block.
    return re.sub(r"[ \t]+", " ", body).strip()


# --------------------------------------------------------------------------- #
# Per-document PII bundle (deterministic, valid) — identical contract to stage-A _fields
# --------------------------------------------------------------------------- #
def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Coherent slot -> (value, KP label) for one synthetic person. Ids are format-/checksum-valid."""
    p = gen_person(rng)
    email = f"{p.first_name}.{p.last_name}@example.co.uk".lower()
    date = f"{rng.randint(1990, 2024)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "nino": (p.nino, "NATIONAL_ID"),
        "address": (p.address, "ADDRESS"),
        "phone": (p.phone, "PHONE"),
        "iban": (p.iban, "ACCOUNT_ID"),
        "email": (email, "EMAIL"),
        "date": (date, "DATE"),
    }


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def _stage_a_fallback(rng: random.Random) -> Doc:
    """Deterministic fallback: a stage-A template, so a run never stalls on a bad LLM body.

    Uses only the stage-A templates whose slots are a subset of REQUIRED_SLOTS so the same coherent
    person fills them; falls back further to the full template list. Fully offset-validated.
    """
    candidates = [
        (dom, tmpl)
        for dom, tmpl in STAGE_A_TEMPLATES
        if set(_SLOT_RE.findall(tmpl)) <= set(REQUIRED_SLOTS)
    ]
    pool = tuple(candidates) if candidates else tuple(STAGE_A_TEMPLATES)
    return fill_document(rng, pool, _fields)


def generate_stageb(config: StageBConfig, narrator: MlxNarrator | None = None) -> Iterator[dict]:
    """Yield ``config.n`` offset-validated EN rows with LLM-authored, structurally-varied bodies.

    For each document: draw a coherent PII bundle, ask the local LLM for a body of a randomly chosen
    genre, sanitize it, then splice via the shared offset-deterministic gate (byte-equality + strict
    BIOES). On an unusable body we retry up to ``max_retries`` then fall back to a stage-A template.

    ``narrator`` is injected for tests (a fake narrator avoids loading a model); in production it is
    created and loaded here from the offline HF cache.
    """
    if narrator is None:
        narrator = MlxNarrator(
            model_id=config.model_id,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
        ).load()

    rng = random.Random(config.seed)
    for i in range(config.n):
        genre = rng.choice(GENRES)
        fields = _fields(rng)  # advance rng identically regardless of LLM path → reproducible PII
        doc: Doc | None = None
        for attempt in range(config.max_retries + 1):
            body = narrator.write_body(genre, REQUIRED_SLOTS, seed=config.seed * 1_000_003 + i * 17 + attempt)
            template = _sanitize_template(body, REQUIRED_SLOTS)
            if template is None:
                continue
            # Splice with the SAME offset-deterministic gate stage-A uses. The pre-drawn PII bundle is
            # captured so it is fixed for this doc; the builder ignores its rng arg and returns it.
            doc = fill_document(rng, ((config.domain, template),), lambda _r, _f=fields: _f)
            break
        if doc is None:
            doc = _stage_a_fallback(rng)

        row = {
            "text": doc.text,
            "spans": doc.spans,
            "language": "en",
            "domain": doc.domain,
            "family": config.family,
            "genre": config.genre,
        }
        yield row


# Re-export the deterministic validators so a publish script / test can assert id validity without
# reaching into en_generators.
__all__ = [
    "StageBConfig",
    "MlxNarrator",
    "generate_stageb",
    "REQUIRED_SLOTS",
    "GENRES",
    "nino_format_valid",
    "iban_gb_valid",
    "card_valid",
    "gen_iban_gb",
    "gen_card",
]
