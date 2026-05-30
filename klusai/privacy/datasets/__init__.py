"""klusai.privacy.datasets — data layer for the KlusAI Privacy program.

Sourcing, synthetic generation, normalization, and HF publishing. Publishes
`klusai/ds-kp-{domain}-{lang}-{size}` and the benchmark data `klusai/europriv-bench`.

Shared semantics (taxonomy + span alignment) are imported from `europriv_bench`, the single
source of truth — never copied here.
"""

__version__ = "0.1.0"
