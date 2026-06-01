"""License CI gate: cleanly-licensed-only admission for the redistributable benchmark.

The KP program ships a *redistributable* benchmark, so every source folded into a released volume
must be redistributable AND derivative-permitting AND commercial-use-permitting. This module is the
single decision point: :func:`assert_clean_license` (and the pure predicate :func:`is_clean_license`)
classify a source's license string and **reject**:

- **NonCommercial / NoDerivatives** (e.g. Piiranha's ``CC-BY-NC-ND-4.0``) — NC forbids the
  commercial redistribution the benchmark needs; ND forbids the span-realignment / reformatting we
  perform, which is a derivative work.
- **Model-license-bound** corpora (e.g. ``Llama`` community-license-derived data) — the upstream
  model license rides along and is not a clean open-data license.
- **Copyleft** (``GPL`` / ``AGPL`` / ``CC-BY-SA`` "ShareAlike") — the viral share-alike obligation
  is incompatible with mixing into a single uniformly-licensed release.

A **clean** license is a permissive, derivative- and commercial-permitting open license: ``CC-BY``
(no NC/ND/SA suffix), ``CC0`` / public domain, MIT / Apache / BSD.

The gate is deliberately *fail-closed*: an unrecognized / empty license string is rejected, so a new
source cannot slip in unclassified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


class LicenseError(ValueError):
    """Raised when a source's license is not cleanly redistributable for the KP benchmark."""


@dataclass(frozen=True)
class LicenseVerdict:
    clean: bool
    normalized: str   # canonicalized license token we matched on
    reason: str       # human-readable rationale (why clean / why rejected)


# Substrings (matched case-insensitively against the normalized token) that disqualify a source.
# Ordered so the reported reason is the most specific applicable one.
_FORBIDDEN = (
    ("nc-nd", "NonCommercial-NoDerivatives (e.g. Piiranha CC-BY-NC-ND): forbids commercial "
              "redistribution and the derivative span-realignment we perform"),
    ("nc", "NonCommercial: forbids the commercial redistribution the benchmark requires"),
    ("nd", "NoDerivatives: forbids the span-realignment / reformatting we perform"),
    ("noncommercial", "NonCommercial: forbids commercial redistribution"),
    ("noderiv", "NoDerivatives: forbids derivative works"),
    ("sa", "ShareAlike/copyleft (CC-BY-SA): viral obligation incompatible with a uniform release"),
    ("sharealike", "ShareAlike/copyleft: viral obligation incompatible with a uniform release"),
    ("agpl", "AGPL copyleft: incompatible with a uniformly-licensed release"),
    ("gpl", "GPL copyleft: incompatible with a uniformly-licensed release"),
    ("lgpl", "LGPL copyleft: incompatible with a uniformly-licensed release"),
    ("copyleft", "copyleft: incompatible with a uniformly-licensed release"),
    ("llama", "Llama model-license-bound: upstream model license is not a clean open-data license"),
    ("openrail", "OpenRAIL: use-based restrictions are not cleanly redistributable"),
    ("proprietary", "proprietary / closed license"),
    ("research-only", "research-only: forbids the commercial redistribution the benchmark requires"),
    ("non-commercial", "NonCommercial: forbids commercial redistribution"),
)

# Permissive, derivative- and commercial-permitting open licenses (post-normalization tokens).
_CLEAN = (
    ("cc-by-4", "CC-BY-4.0: permissive, attribution-only — clean"),
    ("cc-by-3", "CC-BY-3.0: permissive, attribution-only — clean"),
    ("cc-by", "CC-BY: permissive, attribution-only — clean"),
    ("cc0", "CC0 / public domain — clean"),
    ("public-domain", "public domain — clean"),
    ("publicdomain", "public domain — clean"),
    ("pddl", "PDDL public-domain dedication — clean"),
    ("mit", "MIT — permissive, clean"),
    ("apache", "Apache-2.0 — permissive, clean"),
    ("bsd", "BSD — permissive, clean"),
    ("odc-by", "ODC-BY: attribution-only open-data license — clean"),
)


def _normalize(license_str: str) -> str:
    """Lowercase and collapse separators so 'CC BY 4.0', 'cc-by-4.0', 'CC_BY_4' compare equal."""
    s = license_str.strip().lower()
    s = re.sub(r"[\s_./]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def classify_license(license_str: str | None) -> LicenseVerdict:
    """Classify a license string as clean (redistributable) or not. Fail-closed on unknown/empty."""
    if not license_str or not license_str.strip():
        return LicenseVerdict(False, "", "empty/missing license (fail-closed: cannot classify)")
    norm = _normalize(license_str)

    # Forbidden takes priority: a 'cc-by-nc' must be rejected even though it contains 'cc-by'.
    for token, reason in _FORBIDDEN:
        if _has_token(norm, token):
            return LicenseVerdict(False, norm, reason)

    for token, reason in _CLEAN:
        if token in norm:
            return LicenseVerdict(True, norm, reason)

    return LicenseVerdict(False, norm, f"unrecognized license {license_str!r} (fail-closed)")


def _has_token(norm: str, token: str) -> bool:
    """Match ``token`` as a hyphen-delimited segment (so 'nd' hits 'cc-by-nc-nd', not 'iceland')."""
    if "-" not in token and len(token) <= 4:
        return any(seg == token for seg in norm.split("-"))
    return token in norm


def is_clean_license(license_str: str | None) -> bool:
    """True iff ``license_str`` is a cleanly-redistributable open license for the KP benchmark."""
    return classify_license(license_str).clean


def assert_clean_license(license_str: str | None, source: str = "source") -> LicenseVerdict:
    """Raise :class:`LicenseError` unless ``license_str`` is cleanly redistributable.

    The CI gate: a release script calls this for every source it folds in, so a NC/ND/Llama/copyleft
    corpus can never reach a published volume.
    """
    verdict = classify_license(license_str)
    if not verdict.clean:
        raise LicenseError(
            f"license gate rejected {source!r}: {verdict.reason} "
            f"(license={license_str!r}). Only cleanly-licensed (CC-BY/CC0/MIT/Apache/BSD) "
            f"sources may enter the redistributable KP benchmark."
        )
    return verdict
