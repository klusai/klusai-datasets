"""Catch provider-shaped synthetic secrets before they enter Git history."""

from __future__ import annotations

import hashlib
import json
import subprocess

import pytest

from klusai.privacy.datasets.data.credential_scan import AWS_DOCUMENTED_EXAMPLE, findings, scan_paths
from klusai.privacy.datasets.data.gateway_artifact_provenance import blob_revision, revision_bytes
from klusai.privacy.datasets.data.gateway_authoring import ROOT
from scripts.scan_artifact_credentials import artifact_paths


@pytest.mark.parametrize(
    "family,value",
    [
        ("stripe", "sk_" + "test_" + "a1" * 12),
        ("stripe", "rk_" + "live_" + "a1" * 12),
        ("aws_access_id", "AKIA" + "Z" * 16),
        ("aws_access_id", "ASIA" + "9" * 16),
        ("github", "ghp_" + "x" * 36),
        ("github", "gho_" + "x" * 36),
        ("github", "github_pat_" + "x" * 82),
        ("slack", "xoxb-" + "1" * 12 + "-" + "a" * 32),
        ("slack", "xoxp-" + "2" * 12 + "-" + "b" * 32),
        ("google_api", "AIza" + "a" * 35),
        ("openai", "sk-" + "a" * 48),
        ("openai", "sk-proj-" + "a" * 100),
        ("signed_jwt", "eyJ" + "a" * 20 + ".eyJ" + "b" * 20 + "." + "c" * 43),
        ("private_key", "-----BEGIN " + "PRIVATE KEY-----\n" + "a" * 64),
        ("private_key", "-----BEGIN RSA " + "PRIVATE KEY-----\n" + "a" * 64),
    ],
)
def test_pattern_families_detect_runtime_examples_without_committing_them(family, value):
    assert family in {name for name, _, _ in findings(value)}
    assert list(findings(json.dumps({"token": value})))


def test_only_documented_aws_example_is_exempt():
    assert not list(findings(AWS_DOCUMENTED_EXAMPLE))
    assert list(findings(AWS_DOCUMENTED_EXAMPLE[:-1] + "Z"))
    assert not list(findings("opaque__" + hashlib.sha256(b"synthetic fixture").hexdigest()[:24]))


def test_all_artifacts_and_tracked_files_have_no_provider_credentials():
    paths = artifact_paths()
    assert {ROOT / f"artifacts/gateway-traffic-v1/{s}.jsonl" for s in ("test", "dev")} <= set(paths)
    assert not list(scan_paths(paths)), "Provider-shaped credentials found; report locations, never bypass the scanner"


def test_blob_pin_survives_without_its_authoring_commit(tmp_path):
    artifact = tmp_path / "fixture.txt"
    artifact.write_text("provider-neutral synthetic input\n")
    revision = blob_revision(artifact, ROOT)
    assert subprocess.check_output(["git", "cat-file", "-t", revision], cwd=ROOT).strip() == b"blob"
    assert revision_bytes(revision, artifact, ROOT) == artifact.read_bytes()


def test_current_credential_gold_is_preserved_and_provider_neutral():
    count = 0
    for split in ("test", "dev"):
        path = ROOT / f"artifacts/gateway-traffic-v1/{split}.jsonl"
        for line in path.read_text().splitlines():
            row = json.loads(line)
            for span in row["spans"]:
                if span["label"] not in {"SECRET", "CREDENTIAL"}:
                    continue
                count += 1
                assert span["protection"] == "mask"
                text = row["messages"][span["message"]]["parts"][span["part"]]["text"]
                assert text[span["start"] : span["end"]] == span["text"]
                assert not list(findings(span["text"]))
    assert count == 264
