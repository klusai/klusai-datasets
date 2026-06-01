"""Data utilities: loaders, normalizers, synthetic generation.

Span alignment lives in `europriv_bench.spans` (the single source of truth, beside the
taxonomy) — import it from there:

    from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes

Per-locale synthetic generation is bundled behind the :class:`LocalePack` abstraction
(:mod:`klusai.privacy.datasets.data.localepack`). The :data:`LOCALE_PACKS` registry maps language
code → pack so callers can iterate locales uniformly (e.g. checksum self-tests, dataset publishing).
"""

from __future__ import annotations


def _load_packs():
    """Lazily import the per-locale packs (avoids import cost / cycles at package import time)."""
    from .en_documents import en_pack
    from .pl_documents import pl_pack
    from .ro_documents import ro_pack
    from .ro_skeletons import ro_skeleton_pack

    return {
        "ro": ro_pack,
        "ro-realskeleton": ro_skeleton_pack,
        "pl": pl_pack,
        "en": en_pack,
    }


LOCALE_PACKS = _load_packs()

__all__ = ["LOCALE_PACKS"]
