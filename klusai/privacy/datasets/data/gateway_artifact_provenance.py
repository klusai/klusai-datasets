"""Content-addressed artifact provenance without a self-referential commit hash."""

from __future__ import annotations

import subprocess
from pathlib import Path


def blob_revision(artifact: Path, root: Path) -> str:
    """Store the clean input blob; its object ID survives squash/clone unchanged."""
    return subprocess.check_output(["git", "hash-object", "-w", str(artifact)], cwd=root, text=True).strip()


def revision_bytes(revision: str, artifact: Path, root: Path) -> bytes:
    """Read a blob pin or a historical commit/path pin, rejecting other Git object types."""
    kind = subprocess.check_output(["git", "cat-file", "-t", revision], cwd=root, text=True).strip()
    if kind == "blob":
        return subprocess.check_output(["git", "cat-file", "blob", revision], cwd=root)
    if kind == "commit":
        return subprocess.check_output(["git", "show", f"{revision}:{artifact.relative_to(root)}"], cwd=root)
    raise ValueError(f"Unsupported artifact revision type: {kind}")
