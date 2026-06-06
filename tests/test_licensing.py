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


# --- RES-93: Ai4Privacy tier gating (live-verified licenses, 2026-06-07) -----------------------
# The 500k flagship's card declares `license_name: cc-by-4.0` but its body binds the data to the
# Llama Community License (created with Llama 3.1/3.3, "Built with Llama" attribution). The gate
# must classify on the ACTUAL binding license string, not the cosmetic license_name — so we record
# the verified string ("Llama-Community-License") and assert it is blocked, while the openpii-1m
# tier (body says plainly "License: CC-BY-4.0", no Llama clause) passes.
def test_ai4privacy_500k_llama_tier_blocked():
    """open-pii-masking-500k is Llama-Community-License-bound → must be rejected."""
    verdict = classify_license("Llama-Community-License")
    assert not verdict.clean
    assert "llama" in verdict.reason.lower()
    with pytest.raises(LicenseError):
        assert_clean_license("Llama-Community-License",
                             source="ai4privacy/open-pii-masking-500k-ai4privacy")


def test_ai4privacy_300k_custom_commercial_tier_blocked():
    """pii-masking-300k/-200k carry a custom company-size-tiered license.md → fail-closed."""
    # `license.md` (the YAML license_name) is an unrecognized custom token → rejected fail-closed.
    assert not is_clean_license("license.md")
    assert not is_clean_license("research-only")


def test_ai4privacy_openpii_1m_clean_tier_passes():
    """The verified open core (pii-masking-openpii-1m) body states CC-BY-4.0 → passes the gate."""
    verdict = assert_clean_license("CC-BY-4.0", source="ai4privacy/pii-masking-openpii-1m")
    assert verdict.clean
