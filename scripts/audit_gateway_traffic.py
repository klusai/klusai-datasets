"""Offline RES-123 manifest/coverage/overlap audit. Never generates or publishes data."""

from __future__ import annotations

import json
from pathlib import Path

import click

from klusai.privacy.datasets.data.gateway_traffic import (
    Conversation,
    audit_training,
    coverage_report,
    digest,
    file_digest,
    load_manifest,
    validate_collection,
)


@click.command()
@click.option("--manifest", type=click.Path(path_type=Path, exists=True), default="conf/gateway_traffic_manifest.yaml")
@click.option(
    "--records", type=click.Path(path_type=Path, exists=True), help="Future RES-124 JSONL; omitted means n=0."
)
@click.option(
    "--training-paths",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="JSON mapping EVERY inventory corpus ID to a local JSONL/parquet path.",
)
@click.option(
    "--prior-ledger",
    type=click.Path(path_type=Path, exists=True),
    help="Previous complete ledger receipt; required when extending an earlier release.",
)
@click.option(
    "--output", type=click.Path(path_type=Path), required=True, help="New audit/ledger receipt; no overwrite."
)
@click.option("--require-complete", is_flag=True, help="Fail for missing coverage or unverified semantic disjointness.")
def main(manifest, records, training_paths, prior_ledger, output, require_complete):
    root = manifest.resolve().parent.parent
    try:
        spec = load_manifest(manifest)
        plan = json.loads((root / spec["split_plan"]["path"]).read_text())
        inventory = json.loads((root / spec["training_inventory"]["path"]).read_text())
        paths = {k: Path(v) for k, v in json.loads(training_paths.read_text()).items()}
        rows = (
            []
            if records is None
            else [Conversation.model_validate_json(line) for line in records.read_text().splitlines() if line.strip()]
        )
        previous = {} if prior_ledger is None else json.loads(prior_ledger.read_text())
        if previous and (
            digest(previous["ledger"]) != previous["ledger_sha256"]
            or previous["split_plan_sha256"] != spec["split_plan"]["sha256"]
        ):
            raise ValueError("prior ledger hash or split plan mismatch")
        ledger = validate_collection(rows, spec, plan, previous.get("ledger", {}))
        audit = audit_training(rows, inventory, paths)
        coverage = coverage_report(rows, spec)
        report = {
            "dataset": spec["dataset"],
            "manifest_sha256": file_digest(manifest),
            "split_plan_sha256": spec["split_plan"]["sha256"],
            "training_inventory_sha256": spec["training_inventory"]["sha256"],
            "records_sha256": None if records is None else file_digest(records),
            "parent_receipt_sha256": None if prior_ledger is None else file_digest(prior_ledger),
            "ledger": ledger,
            "ledger_sha256": digest(ledger),
            "audit": audit,
            "coverage": coverage,
            "release_ready": False,
            "blocking_review": "Family/subject/source-document/translation provenance review remains required; "
            "legacy corpus IDs are incomplete. Exact-text clearance alone is insufficient.",
        }
        with output.open("x") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
    except (ValueError, KeyError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{audit['status']}; candidates={len(rows)}; coverage={coverage['status']}; receipt={output}")
    if audit["hits"] or require_complete:
        raise click.ClickException("Gateway release gate failed; inspect the receipt's blockers.")


if __name__ == "__main__":
    main()
