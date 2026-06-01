"""License CI gate: cleanly-licensed-only admission for the redistributable KP benchmark.

The headline guard (issue KLU-18): the gate must BLOCK a deliberately bad source (Piiranha
CC-BY-NC-ND, Llama-bound, copyleft) and PASS a clean CC-BY source.
"""

import pytest

from klusai.privacy.datasets.data.licensing import (
    LicenseError,
    assert_clean_license,
    classify_license,
    is_clean_license,
)

CLEAN = [
    "CC-BY-4.0",
    "cc-by-4.0",
    "CC BY 4.0",
    "cc-by-3.0",
    "CC0-1.0",
    "cc0",
    "public domain",
    "MIT",
    "Apache-2.0",
    "BSD-3-Clause",
    "ODC-BY-1.0",
]

BAD = [
    "CC-BY-NC-ND-4.0",   # Piiranha
    "cc-by-nc-nd-4.0",
    "CC-BY-NC-4.0",
    "CC-BY-ND-4.0",
    "CC-BY-SA-4.0",      # copyleft / share-alike
    "GPL-3.0",
    "AGPL-3.0",
    "LGPL-2.1",
    "Llama-2-community-license",
    "llama3",
    "openrail",
    "proprietary",
    "research-only",
    "",                  # empty → fail-closed
    None,                # missing → fail-closed
    "some-unheard-of-license",  # unrecognized → fail-closed
]


@pytest.mark.parametrize("lic", CLEAN)
def test_clean_licenses_pass(lic):
    assert is_clean_license(lic)
    verdict = assert_clean_license(lic, source="clean-source")
    assert verdict.clean


@pytest.mark.parametrize("lic", BAD)
def test_bad_licenses_blocked(lic):
    assert not is_clean_license(lic)
    with pytest.raises(LicenseError):
        assert_clean_license(lic, source="bad-source")


def test_gate_blocks_piiranha_specifically():
    """The named adversarial case: Piiranha's CC-BY-NC-ND must be rejected with an NC/ND reason."""
    verdict = classify_license("CC-BY-NC-ND-4.0")
    assert not verdict.clean
    assert "noncommercial" in verdict.reason.lower() or "nc" in verdict.reason.lower()


def test_gate_passes_clean_cc_by():
    """A clean CC-BY source passes (the benchmark's intended source class)."""
    verdict = assert_clean_license("CC-BY-4.0", source="ai4privacy-openpii")
    assert verdict.clean


def test_nc_takes_priority_over_cc_by_substring():
    """'cc-by-nc' contains 'cc-by' but must still be rejected (forbidden checked first)."""
    assert not is_clean_license("CC-BY-NC-4.0")


def test_error_message_names_source_and_reason():
    with pytest.raises(LicenseError) as exc:
        assert_clean_license("CC-BY-NC-ND-4.0", source="piiranha")
    msg = str(exc.value)
    assert "piiranha" in msg and "CC-BY-NC-ND-4.0" in msg
