"""Create the local RES-124 tranche, then attach provenance after the input commit.

Never downloads, calls a model, trains, or publishes. Existing outputs are not overwritten.
"""

from __future__ import annotations

import argparse
import json
import subprocess

from klusai.privacy.datasets.data.gateway_authoring import (
    PROSE,
    ROOT,
    allocation,
    attach_provenance,
    get_tokenizer,
    make_draft,
)
from klusai.privacy.datasets.data.gateway_traffic import LANGUAGES, file_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("author", "finalize"))
    parser.add_argument("--source-revision")
    parser.add_argument("--resume", action="store_true", help="verify existing complete rows and append missing rows")
    args = parser.parse_args()
    output = ROOT / "artifacts/gateway-traffic-v1"
    output.mkdir(parents=True, exist_ok=True)
    if args.phase == "author":
        # Intentional first tranche: integer exact quotas at 280 test/60 dev per locale.
        if any(output.rglob("*.jsonl")) and not args.resume:
            raise SystemExit("Existing gateway data: refusing to regenerate or overwrite")
        tokenizer = get_tokenizer()
        prose = json.loads(PROSE.read_text())
        (output / "originals").mkdir(exist_ok=True)
        for split, n in (("test", 280), ("dev", 60)):
            plan = allocation(n, split)
            path = output / "originals" / f"{split}.jsonl"
            existing = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
            if len(existing) > n * len(LANGUAGES):
                raise SystemExit("Existing artifact exceeds tranche size")
            position = 0
            with path.open("a" if args.resume else "x") as stream:
                for language in LANGUAGES:
                    for i, (mix, length) in enumerate(plan):
                        draft = make_draft(language, split, i, mix, length, tokenizer, prose)
                        if position < len(existing):
                            if draft != existing[position]:
                                raise SystemExit(f"Resume mismatch at {draft['id']}; existing data retained")
                        else:
                            stream.write(json.dumps(draft, ensure_ascii=False) + "\n")
                        position += 1
                    stream.flush()
                    print(f"authored {split}/{language}: {n}", flush=True)
    else:
        if not args.source_revision:
            parser.error("--source-revision must identify the committed input artifact")
        for split in ("test", "dev"):
            artifact = output / "originals" / f"{split}.jsonl"
            committed = subprocess.check_output(
                ["git", "show", f"{args.source_revision}:{artifact.relative_to(ROOT)}"], cwd=ROOT
            )
            if committed != artifact.read_bytes():
                raise SystemExit("Input artifact differs from the pinned commit")
            sha = file_digest(artifact)
            with (output / f"{split}.jsonl").open("x") as stream:
                for line in artifact.read_text().splitlines():
                    row = attach_provenance(json.loads(line), artifact, args.source_revision, sha)
                    stream.write(row.model_dump_json() + "\n")
            print(f"finalized {split}: {sha}", flush=True)


if __name__ == "__main__":
    main()
