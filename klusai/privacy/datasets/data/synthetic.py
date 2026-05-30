"""Synthetic PII/PHI document generation (legal + clinical, 20 languages).

Infrastructure, not the novelty (synthetic generation is the field's default). The research
value — implemented in Phase 2 — is (a) measuring & **closing the synthetic-to-real
distribution drift**, and (b) **multilingual legal synthesis** (thinner than clinical).

Reuses the TinyFabulist generation approach (entity-pool prompting → sharded JSONL with gold
spans emitted at generation time, so no annotation cost and GDPR-safe). Gold spans are
validated against the shared taxonomy via `europriv_bench.spans` so labels never drift.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GenConfig:
    domain: str            # legal | clinical
    language: str          # ISO code
    n: int                 # number of documents
    entity_pool: str       # path to entity-pool YAML (names/orgs/addresses per locale)
    seed: int = 0


def generate(config: GenConfig):  # pragma: no cover - Phase 2
    """Generate `config.n` documents with gold PII spans. Yields dicts: {text, spans}."""
    raise NotImplementedError(
        "synthetic.generate: Phase 2 — port tinyfabulist-tf3/tf3/ds_generation, emit gold spans, "
        "then validate every example via europriv_bench.spans.char_spans_to_bioes + validate_bioes"
    )
