"""release_dataset.py: PACK vs SLUG, audit metrics, uniform card, license gate wiring (no network)."""

import importlib.util
import sys
from pathlib import Path

import pytest

from klusai.privacy.datasets.data.licensing import LicenseError
from klusai.privacy.datasets.data.synthetic import GenConfig, generate

_SPEC = importlib.util.spec_from_file_location(
    "release_dataset", Path(__file__).resolve().parent.parent / "scripts" / "release_dataset.py"
)
release_dataset = importlib.util.module_from_spec(_SPEC)
sys.modules["release_dataset"] = release_dataset  # so @dataclass can resolve annotations
_SPEC.loader.exec_module(release_dataset)


def _rows(lang="ro", n=30, seed=5):
    return list(generate(GenConfig(language=lang, n=n, seed=seed)))


def test_validate_rows_reports_full_validity():
    metrics = release_dataset._validate_rows(_rows())
    assert metrics.byte_equality_pct == 100.0
    assert metrics.bioes_validity_pct == 100.0
    assert metrics.train_gold_overlap == 0
    assert metrics.validation_status == "PASS"
    assert metrics.n_docs == 30


def test_card_carries_all_required_fields():
    metrics = release_dataset._validate_rows(_rows())
    card = release_dataset.build_card(
        slug="klusai/ds-kp-general-ro-50k", pack="ro", language="ro", domain="general",
        seed=20260601, commit="abc1234", metrics=metrics,
    )
    # source + license, generator commit + seed, taxonomy version, n_docs, byte-equality %,
    # BIOES-validity %, train/gold-overlap=0, drift placeholder, validation status.
    for needle in [
        "KlusAI synthetic", "CC-BY-4.0", "abc1234", "20260601",
        release_dataset.TAXONOMY_VERSION, "byte-equality", "BIOES-validity",
        "train/gold-overlap", "drift", "PASS",
    ]:
        assert needle in card, f"card missing {needle!r}"
    # PACK vs SLUG distinction is explicit.
    assert "PACK" in card and "SLUG" in card
    # Valid YAML frontmatter header.
    assert card.startswith("---\n")


def test_release_runs_license_gate_and_rejects_bad_source():
    """The release entrypoint must abort on a non-clean source license (gate wired in)."""
    runner = pytest.importorskip("click.testing").CliRunner()
    result = runner.invoke(release_dataset.main, [
        "--pack", "ro", "--slug", "klusai/ds-kp-general-ro-50k",
        "--n", "5", "--source-license", "CC-BY-NC-ND-4.0", "--dry-run",
    ])
    assert result.exit_code != 0
    assert isinstance(result.exception, LicenseError)


def test_release_dry_run_clean_source_succeeds():
    runner = pytest.importorskip("click.testing").CliRunner()
    result = runner.invoke(release_dataset.main, [
        "--pack", "en", "--slug", "klusai/ds-kp-general-en-50k",
        "--n", "10", "--source-license", "CC-BY-4.0", "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    assert "byte-equality" in result.output  # card echoed


def test_size_bucket():
    assert release_dataset._size_bucket(50_000) == "10K<n<100K"
    assert release_dataset._size_bucket(500) == "n<1K"
