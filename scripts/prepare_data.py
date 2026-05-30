#!/usr/bin/env python3
"""Normalize a raw/source corpus into KP JSONL ({text, spans}) and validate alignment.

Phase 1/2 entry point. Validates every produced example with the span-alignment integrity
checks so off-by-one annotations fail loudly instead of corrupting F1 downstream.
"""

import click

from klusai.privacy.datasets.logger import get_logger

logger = get_logger("prepare_data")


@click.command()
@click.option("--source", required=True, help="Path to a raw/source corpus.")
@click.option("--out", required=True, help="Output JSONL path.")
@click.option("--domain", default="general")
def main(source: str, out: str, domain: str) -> None:
    raise NotImplementedError(
        "prepare_data: Phase 1/2 — load `source`, map source labels → KP taxonomy, emit "
        "{text, spans}, validate via kp.data.span_align, write `out`."
    )


if __name__ == "__main__":
    main()
