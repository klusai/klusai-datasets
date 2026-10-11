"""Scan all artifact files and tracked text, reporting locations without secret values."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from klusai.privacy.datasets.data.credential_scan import findings, scan_paths

ROOT = Path(__file__).resolve().parents[1]


def artifact_paths():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    paths = {ROOT / name for name in tracked if name}
    paths.update(p for p in (ROOT / "artifacts").rglob("*") if p.is_file())
    return sorted(p for p in paths if p.is_file())


def scan_git_patch(args):
    process = subprocess.Popen(["git", *args], cwd=ROOT, stdout=subprocess.PIPE, text=True, errors="replace")
    hits = []
    for number, line in enumerate(process.stdout, 1):
        hits.extend((number, family) for family, _, _ in findings(line))
    if process.wait():
        raise RuntimeError("Git patch enumeration failed")
    return hits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="also scan every reachable commit patch")
    parser.add_argument("--staged", action="store_true", help="also scan the index patch, including deletions")
    args = parser.parse_args()
    paths = artifact_paths()
    hits = list(scan_paths(paths))
    history = scan_git_patch(["log", "-p", "--no-ext-diff"]) if args.history else []
    staged = scan_git_patch(["diff", "--cached", "--no-ext-diff"]) if args.staged else []
    print(json.dumps(dict(files=len(paths), hits=hits, history_hits=history, staged_hits=staged), indent=2))
    raise SystemExit(bool(hits or history or staged))


if __name__ == "__main__":
    main()
