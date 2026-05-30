#!/usr/bin/env python3
"""Publish a prepared KP dataset to the Hugging Face Hub with a dataset card.

Pattern mirrors tinyfabulist-tf3/upload_dataset.py. Usage:
    python scripts/upload_dataset.py --shards artifacts/legal-ro --repo klusai/ds-kp-legal-ro-50k
"""

import glob
import json

import click
from datasets import Dataset
from huggingface_hub import HfApi

CARD = """---
language:
{lang_block}
license: {license}
task_categories:
- token-classification
tags:
- pii
- privacy
- de-identification
- kp
- {domain}
size_categories:
- {size}
---

# {repo}

KlusAI Privacy dataset — {domain} domain. Gold PII/quasi-identifier spans in the harmonized
KP (BIOES) taxonomy. See https://huggingface.co/datasets/klusai/europriv-bench for the
benchmark these feed.

## License

{license}
"""


@click.command()
@click.option("--shards", required=True, help="Directory of *.jsonl shards (each: {text, spans}).")
@click.option("--repo", required=True, help="Target HF repo id, e.g. klusai/ds-kp-legal-ro-50k.")
@click.option("--language", required=True, help="ISO language code, e.g. ro.")
@click.option("--domain", default="general", help="general | legal | clinical.")
@click.option("--license", "license_", default="CC-BY-4.0", help="License tag (clean sources only).")
@click.option("--size", default="10K<n<100K", help="HF size_categories bucket.")
def main(shards: str, repo: str, language: str, domain: str, license_: str, size: str) -> None:
    rows = []
    for path in sorted(glob.glob(f"{shards}/*.jsonl")):
        with open(path, encoding="utf-8") as f:
            rows.extend(json.loads(line) for line in f if line.strip())
    ds = Dataset.from_list(rows)
    ds.push_to_hub(repo, private=False)

    card = CARD.format(
        lang_block=f"- {language}", license=license_, domain=domain, size=size, repo=repo,
    )
    HfApi().upload_file(
        path_or_fileobj=card.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=repo,
        repo_type="dataset",
    )
    click.echo(f"published {len(rows)} rows → https://huggingface.co/datasets/{repo}")


if __name__ == "__main__":
    main()
