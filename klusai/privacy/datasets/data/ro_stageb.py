"""Stage-B narrative generation for Romanian (RES-95) — LLM-authored *bodies*, code-injected PII.

Why this exists
---------------
The stage-A RO generator (:mod:`ro_documents`) splices PII into a fixed set of ~6 hand-written
templates. RES-94 measured the consequence: the unique-document-*skeleton* ratio is ~0.004 (6
distinct skeletons over 1500 docs) versus Ai4Privacy's ~1.0. That structural monotony is why
detection F1 saturates and why a synthetic-trained model fails to transfer to real data (RES-97).

Stage-B raises document diversity toward Ai4Privacy by having a **local, offline LLM author the
surrounding narrative** while keeping the stage-A gold-integrity moat **byte-for-byte intact**:

  * The LLM writes ONLY the document body, emitting our ``{slot}`` placeholders verbatim — it never
    authors a PII *value*. So no hallucinated/invalid CNP can ever enter the gold.
  * The PII values are produced deterministically by the existing checksum-valid RO generators
    (:func:`ro_generators.gen_person` etc.) and spliced by the SAME offset-deterministic
    :func:`localepack._fill` used in stage-A. ``text[start:end] == value`` holds BY CONSTRUCTION.
  * Every row still passes the strict ``char_spans_to_bioes`` + ``validate_bioes`` gate inside
    :func:`localepack.fill_document`. A misaligned span fails loud; the row is discarded, never
    silently emitted.

The LLM-authored template is treated as untrusted text and **sanitized hard** before splicing
(:func:`_sanitize_template`): the body must contain each required slot exactly once, no stray
braces, and **no digit runs** (so the model cannot have smuggled a literal ID/date/phone into the
static prose — only our placeholders carry such values). A body that fails sanitization is retried;
after ``max_retries`` we fall back to a stage-A template so generation never stalls or thrashes.

LLM access (RES-95 bound)
-------------------------
The only LLM used is a **local, offline** model loaded via ``mlx-lm`` from the on-disk Hugging Face
cache (default: ``Qwen/Qwen3-1.7B`` — already in the KP model registry as the ``anon`` LoRA base).
No network, no API key, no external paid endpoint. ``mlx-lm`` is an optional extra (``.[stageb]``);
the module imports it lazily so the repo's core (splice, validation, tests) stays dependency-free.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from europriv_bench.national_id import validate_cnp

from .localepack import Doc, fill_document
from .ro_documents import TEMPLATES as STAGE_A_TEMPLATES
from .ro_generators import cui_valid, gen_cui, gen_iban_ro, gen_person, iban_ro_valid

# The slots stage-B may ask the LLM to weave in. Each maps to (value-builder, KP label) — the SAME
# coherent person used across slots so the document stays internally consistent (CNP county ==
# address county, etc.), exactly as stage-A's _fields does.
REQUIRED_SLOTS = ("person", "cnp", "address", "phone", "date")

# Genres the LLM is asked to write — the diversity driver. Plain RO administrative/everyday document
# types; the LLM's free prose around the slots is what makes each skeleton structurally unique.
GENRES: tuple[str, ...] = (
    "o adresă oficială de la primărie",
    "o cerere către o instituție publică",
    "un proces-verbal de constatare",
    "un e-mail intern către departamentul de resurse umane",
    "o notificare de plată restantă",
    "o sesizare către poliția locală",
    "o invitație la o ședință de consiliu",
    "o adeverință de salariat",
    "o reclamație a unui client",
    "o decizie administrativă",
    "o cerere de concediu",
    "o întâmpinare depusă la registratură",
    "o notă de informare internă",
    "un anunț de convocare",
    "o solicitare de acces la informații de interes public",
    "o confirmare de programare",
)

_SYSTEM_PROMPT = (
    "Ești un asistent care redactează documente administrative românești realiste și variate. "
    "Scrii DOAR corpul documentului, în limba română corectă, cu diacritice. "
    "Trebuie să folosești fiecare dintre acești substituenți EXACT o singură dată, literal cu "
    "acolade, fără să îi modifici: {person}, {cnp}, {address}, {phone}, {date}. "
    "REGULI STRICTE: nu scrie niciun nume propriu, niciun număr de telefon, CNP, dată calendaristică "
    "sau adresă reală — pune întotdeauna substituentul corespunzător în locul lor. "
    "Nu folosi NICIO cifră în text. Nu scrie cod, JSON, liste cu numere sau alt text în engleză. "
    "Variază puternic structura, tonul și vocabularul de la un document la altul. "
    "Scrie între 2 și 5 propoziții, ca un singur paragraf sau scurt document coerent."
)

# Validation regexes for the LLM body (applied AFTER the slots are removed for the digit check).
_SLOT_RE = re.compile(r"\{([a-z_]+)\}")
_ANY_BRACE_RE = re.compile(r"[{}]")
_DIGIT_RE = re.compile(r"\d")
# Cheap "looks like leaked code/markup" guard.
_BAD_FRAGMENTS = ('```', '"subject"', "<", "/>", "http")


@dataclass
class StageBConfig:
    """Config for the RO stage-B run. ``n`` rows, seeded; small batches only (RES-95 PoC bound)."""

    n: int
    seed: int = 0
    model_id: str = "Qwen/Qwen3-1.7B"   # local HF-cache id; offline mlx-lm load
    max_tokens: int = 260
    temperature: float = 0.9
    top_p: float = 0.95
    max_retries: int = 2                 # LLM body re-draws before deterministic fallback
    domain: str = "general"
    family: str = "stageb"
    genre: str = "ro-stageb-narrative-v1"


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
        """Author one RO document body for ``genre`` that weaves in each ``{slot}`` exactly once."""
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        slot_list = ", ".join("{" + s + "}" for s in slots)
        user = (
            f"Redactează {genre}. Folosește, fiecare exact o dată, substituenții: {slot_list}."
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
        a person/CNP recurring in a document is realistic, and every occurrence is spliced with the
        SAME checksum-valid value, so gold stays byte-exact);
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
# Per-document PII bundle (deterministic, checksum-valid) — identical contract to stage-A _fields
# --------------------------------------------------------------------------- #
def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Coherent slot -> (value, KP label) for one synthetic person. Values are checksum-valid."""
    p = gen_person(rng)
    date = f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1990, 2024)}"
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "cnp": (p.cnp, "NATIONAL_ID"),
        "address": (p.address, "ADDRESS"),
        "phone": (p.phone, "PHONE"),
        "date": (date, "DATE"),
    }


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def _stage_a_fallback(rng: random.Random) -> Doc:
    """Deterministic fallback: a stage-A template, so a run never stalls on a bad LLM body.

    Uses only the stage-A templates whose slots are a subset of REQUIRED_SLOTS so the same coherent
    person fills them; falls back further to the first such template. Fully offset-validated.
    """
    candidates = [
        (dom, tmpl)
        for dom, tmpl in STAGE_A_TEMPLATES
        if set(_SLOT_RE.findall(tmpl)) <= set(REQUIRED_SLOTS)
    ]
    pool = tuple(candidates) if candidates else STAGE_A_TEMPLATES
    return fill_document(rng, pool, _fields)


def generate_stageb(config: StageBConfig, narrator: MlxNarrator | None = None) -> Iterator[dict]:
    """Yield ``config.n`` offset-validated RO rows with LLM-authored, structurally-varied bodies.

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
            "language": "ro",
            "domain": doc.domain,
            "family": config.family,
            "genre": config.genre,
        }
        yield row


# Re-export the deterministic validators so a publish script / test can assert checksum validity
# without reaching into ro_generators.
__all__ = [
    "StageBConfig",
    "MlxNarrator",
    "generate_stageb",
    "REQUIRED_SLOTS",
    "GENRES",
    "validate_cnp",
    "iban_ro_valid",
    "cui_valid",
    "gen_iban_ro",
    "gen_cui",
]
