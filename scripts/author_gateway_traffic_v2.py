"""Create the local RES-124 tranche, then pin clean input Git blobs without self-referential commit hashes.

Never downloads, calls a model, trains, or publishes. Prior input revisions are preserved; finalize replaces the current published-shape local records.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from klusai.privacy.datasets.data.gateway_artifact_provenance import blob_revision, revision_bytes
from klusai.privacy.datasets.data.gateway_authoring import get_tokenizer
from klusai.privacy.datasets.data.gateway_authoring_v2 import (
    PROSE,
    ROOT,
    allocation,
    attach_provenance,
    make_draft,
)
from klusai.privacy.datasets.data.gateway_traffic import LANGUAGES, file_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("author", "finalize"))
    parser.add_argument("--source-revision", help="optional existing input commit/blob to verify")
    parser.add_argument("--records-dir", type=Path, help="output directory for finalized strict records")
    parser.add_argument("--resume", action="store_true", help="verify existing complete rows and append missing rows")
    args = parser.parse_args()
    output = ROOT / "artifacts/gateway-traffic-v1"
    output.mkdir(parents=True, exist_ok=True)
    if args.phase == "author":
        # Intentional first tranche: integer exact quotas at 1000 test/200 dev per locale.
        if any((output / "originals/v2").glob("*.jsonl")) and not args.resume:
            raise SystemExit("Existing gateway data: refusing to regenerate or overwrite")
        tokenizer = get_tokenizer()
        prose = json.loads(PROSE.read_text())
        (output / "originals/v2").mkdir(parents=True, exist_ok=True)
        for split, n in (("test", 1000), ("dev", 200)):
            plan = allocation(n, split)
            path = output / "originals/v2" / f"{split}.jsonl"
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
        records_dir = args.records_dir or output
        records_dir.mkdir(parents=True, exist_ok=True)
        for split in ("test", "dev"):
            artifact = output / "originals/v2" / f"{split}.jsonl"
            if args.source_revision and revision_bytes(args.source_revision, artifact, ROOT) != artifact.read_bytes():
                raise SystemExit("Input artifact differs from the supplied revision")
            revision = blob_revision(artifact, ROOT)
            sha = file_digest(artifact)
            with (records_dir / f"{split}.jsonl").open("w") as stream:
                for line in artifact.read_text().splitlines():
                    row = attach_provenance(json.loads(line), artifact, revision, sha)
                    stream.write(row.model_dump_json() + "\n")
            print(f"finalized {split}: {sha}", flush=True)


if __name__ == "__main__":
    main()
