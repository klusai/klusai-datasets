"""Author local train conversations and KP model input; deterministic, offline, resumable."""

from __future__ import annotations

import argparse
import json

from klusai.privacy.datasets.data.gateway_artifact_provenance import blob_revision
from klusai.privacy.datasets.data.gateway_authoring_v2 import allocation
from klusai.privacy.datasets.data.gateway_traffic import file_digest
from klusai.privacy.datasets.data.gateway_train import (
    GUIDE,
    INPUT,
    LANGUAGES,
    OUTPUT,
    PROSE,
    ROOT,
    attach_provenance,
    base,
    make_draft,
    make_pools,
    training_row,
)


def write_verified(path, rows, resume):
    """Append only after verifying each existing row; reject excess/partial/corrupt lines."""
    if path.exists() and not resume:
        raise ValueError(f"Existing artifact: {path}; use --resume for verification")
    previous = path.open() if path.exists() else None
    exhausted = previous is None
    try:
        with path.open("a" if resume else "x") as output:
            for number, row in enumerate(rows, 1):
                old = next(previous, "") if not exhausted else ""
                exhausted = exhausted or not old
                if old:
                    if not old.endswith("\n") or json.loads(old) != row:
                        raise ValueError(f"Resume mismatch at {path}:{number}")
                else:
                    output.write(json.dumps(row, ensure_ascii=False) + "\n")
                if number % 5000 == 0:
                    output.flush()
                    print(f"{path.name}: {number}", flush=True)
            if not exhausted and next(previous, ""):
                raise ValueError(f"Excess rows in {path}")
    finally:
        if previous:
            previous.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    INPUT.mkdir(parents=True, exist_ok=True)
    prose = json.loads(PROSE.read_text())
    pools = make_pools(prose)
    pool_path = INPUT / "pools.json"
    if pool_path.exists():
        if json.loads(pool_path.read_text()) != pools:
            raise ValueError("Existing subject pool differs; refusing reassignment")
    else:
        pool_path.write_text(json.dumps(pools, ensure_ascii=False, indent=2) + "\n")
    tokenizer = base.get_tokenizer()
    plan = allocation(5000, "train")
    draft_path = INPUT / "train.jsonl"
    drafts = (
        make_draft(lang, i, mix, length, tokenizer, prose, pools)
        for lang in LANGUAGES
        for i, (mix, length) in enumerate(plan)
    )
    write_verified(draft_path, drafts, args.resume)
    revision, sha = blob_revision(draft_path, ROOT), file_digest(draft_path)
    with draft_path.open() as stream:
        rows = (attach_provenance(json.loads(line), draft_path, revision, sha).model_dump() for line in stream)
        write_verified(OUTPUT / "train.jsonl", rows, args.resume)
    with (OUTPUT / "train.jsonl").open() as stream:
        write_verified(OUTPUT / "train-kp.jsonl", (training_row(json.loads(line)) for line in stream), args.resume)
    paths = [draft_path, pool_path, OUTPUT / "train.jsonl", OUTPUT / "train-kp.jsonl", PROSE, GUIDE]
    receipt = dict(rows=40000, source_blob=revision, files={str(p.relative_to(ROOT)): file_digest(p) for p in paths})
    receipt_path = OUTPUT / "train-build.json"
    if receipt_path.exists() and json.loads(receipt_path.read_text()) != receipt:
        raise ValueError("Build receipt differs")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
