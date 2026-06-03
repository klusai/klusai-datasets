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
    from .de_documents import de_pack
    from .en_documents import en_pack
    from .es_documents import es_pack
    from .fr_documents import fr_pack
    from .it_documents import it_pack
    from .nl_documents import nl_pack
    from .pl_documents import pl_pack
    from .pl_skeletons import pl_skeleton_pack
    from .ro_documents import ro_pack
    from .ro_skeletons import ro_skeleton_pack
    from .ro_skeletons_edu import ro_skeleton_edu_pack

    return {
        "ro": ro_pack,
        "ro-realskeleton": ro_skeleton_pack,
        "ro-realskeleton-b": ro_skeleton_edu_pack,
        "pl": pl_pack,
        "pl-realskeleton": pl_skeleton_pack,
        "en": en_pack,
        # T1 packs (KLU-102) — IT is the critical-path decode-bearing identifier (codice fiscale).
        "it": it_pack,
        "de": de_pack,
        "fr": fr_pack,
        "es": es_pack,
        "nl": nl_pack,
    }


LOCALE_PACKS = _load_packs()

__all__ = ["LOCALE_PACKS"]
