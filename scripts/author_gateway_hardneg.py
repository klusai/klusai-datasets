"""Build reproducible local hard-negative KP rows and audit metadata, without network access."""

from __future__ import annotations

import argparse
import json

from klusai.privacy.datasets.data.gateway_hardneg import INPUT, KP, META, PROSE, make_pools, rows
from scripts.author_gateway_train import write_verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    prose = json.loads(PROSE.read_text())
    pools = make_pools(prose)
    INPUT.mkdir(parents=True, exist_ok=True)
    pool_path = INPUT / "pools.json"
    if pool_path.exists() and json.loads(pool_path.read_text()) != pools:
        raise ValueError("Subject pool changed")
    if not pool_path.exists():
        pool_path.write_text(json.dumps(pools, ensure_ascii=False, indent=2) + "\n")
    write_verified(KP, (row for row, _ in rows(prose, pools)), args.resume)
    write_verified(META, (meta for _, meta in rows(prose, pools)), args.resume)


if __name__ == "__main__":
    main()
