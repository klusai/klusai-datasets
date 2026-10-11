"""Conservative local mirrors of documented provider secret families.

GitHub publishes supported families, not its complete production regex rules:
https://docs.github.com/en/code-security/reference/secret-security/supported-secret-scanning-patterns
This guard is not a claim of parity with GitHub's server-side scanner.
"""

from __future__ import annotations

import re
from pathlib import Path

# Intentionally broader than specific token lengths/versions, including test credentials.
PATTERNS = {
    "stripe": re.compile(r"\b(?:sk|rk)_(?:test|live)_[A-Za-z0-9]{12,}"),
    "aws_access_id": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "github": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "slack": re.compile(r"\bxox[a-z](?:-[a-z])?-[A-Za-z0-9-]{10,}"),
    "google_api": re.compile(r"\bAIza[A-Za-z0-9_-]{20,}"),
    "openai": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}"),
    "signed_jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{20,}"),
    "private_key": re.compile(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----"),
}
# The sole exception is the published AWS example explicitly allowed by this task.
AWS_DOCUMENTED_EXAMPLE = "AKIAIOSFODNN7EXAMPLE"


def findings(text: str):
    """Yield family and offsets only; never echo a potentially sensitive value."""
    for provider, regex in PATTERNS.items():
        for match in regex.finditer(text):
            if provider == "aws_access_id" and match.group() == AWS_DOCUMENTED_EXAMPLE:
                continue
            yield provider, match.start(), match.end()


def scan_paths(paths: list[Path]):
    for path in paths:
        # Text artifacts are UTF-8; invalid bytes are preserved as nonmatching separators.
        for line_number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            for provider, _, _ in findings(line):
                yield str(path), line_number, provider
