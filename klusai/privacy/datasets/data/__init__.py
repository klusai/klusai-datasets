"""Data utilities: loaders, normalizers, synthetic generation.

Span alignment lives in `europriv_bench.spans` (the single source of truth, beside the
taxonomy) — import it from there:

    from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
"""
