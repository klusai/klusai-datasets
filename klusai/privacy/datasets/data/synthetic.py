"""Synthetic PII/PHI document generation — stage-A (general-domain bring-up).

Infrastructure, not the novelty (synthetic generation is the field's default). The research
value — implemented later — is (a) measuring & **closing the synthetic-to-real distribution
drift**, and (b) **multilingual legal synthesis** (thinner than clinical).

**Stage-A** wires :func:`generate` to the merged :class:`LocalePack` machinery
(:mod:`klusai.privacy.datasets.data.localepack`): a template-slot splice over the per-locale packs
(ro/en/pl) that emits gold PII spans **at generation time**, so there is no annotation cost and
the data is GDPR-safe (no real data subject). The three quality-moat invariants are inherited
unchanged from ``fill_document``:

1. offset-deterministic ``_fill`` (``text[start:end] == value`` by construction),
2. a byte-equality assert on every span, and
3. the strict ``char_spans_to_bioes`` + ``validate_bioes`` gate (via ``europriv_bench.spans``).

Legal/clinical real-structure synthesis (TinyFabulist entity-pool prompting) is H2; this module
deliberately reuses the LocalePack splice rather than reimplementing generation.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .localepack import LocalePack


@dataclass
class GenConfig:
    """Stage-A generation config: a registered locale pack + volume + seed.

    ``language`` selects a pack from :data:`LOCALE_PACKS`. ``domain`` is informational (the packs
    carry their own per-template domains); kept for forward-compat with the H2 legal/clinical
    real-structure synthesis and for card metadata.
    """

    language: str          # ISO code / pack key, e.g. "ro" | "en" | "pl"
    n: int                 # number of documents
    seed: int = 0
    domain: str = "general"


def generate(config: GenConfig) -> Iterator[dict]:
    """Generate ``config.n`` documents with gold PII spans for the configured locale.

    Yields dicts ``{text, spans:[{start,end,label}], language, domain}``. Each row is produced by
    the shared LocalePack splice, so gold spans are emitted at generation time and every span is
    byte-equality- and strict-BIOES-validated before it is yielded (the assertions live inside
    ``fill_document``).
    """
    pack = _resolve_pack(config.language)
    yield from pack.generate_dataset(config.n, seed=config.seed)


def _resolve_pack(language: str) -> LocalePack:
    """Look up the registered :class:`LocalePack` for ``language`` (fail loud on an unknown key)."""
    from . import LOCALE_PACKS

    try:
        return LOCALE_PACKS[language]
    except KeyError:
        raise KeyError(
            f"no LocalePack registered for {language!r}; "
            f"known packs: {sorted(LOCALE_PACKS)}"
        ) from None
