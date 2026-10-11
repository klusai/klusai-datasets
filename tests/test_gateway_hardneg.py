"""Hard-negative augmentation contamination and annotation regression gates."""

import json
import re

import pytest

from klusai.privacy.datasets.data.gateway_hardneg import RECEIPT, ROOT
from klusai.privacy.datasets.data.gateway_traffic import file_digest
from scripts.audit_gateway_hardneg import audit, validate_contact_mentions, validate_gold

FROZEN_RECEIPT = json.loads(RECEIPT.read_text())
PARENT_KP = "artifacts/gateway-traffic-v1/train-kp.jsonl"
LOCAL_ARTIFACTS = {name for name in FROZEN_RECEIPT["files"] if name.startswith("artifacts/")} | {PARENT_KP}
PINNED_FILES = (
    FROZEN_RECEIPT["files"]
    | {PARENT_KP: FROZEN_RECEIPT["parent_kp_sha256"]}
    | {entry["path"]: entry["sha256"] for entry in FROZEN_RECEIPT["heldout_files"].values()}
)


@pytest.mark.parametrize("name,sha", [pytest.param(name, sha, id=name) for name, sha in PINNED_FILES.items()])
def test_hardneg_file_digest_when_present(name, sha):
    path = ROOT / name
    if name in LOCAL_ARTIFACTS and not path.exists():
        pytest.skip(f"local hard-negative artifact not materialized: {name}")
    assert file_digest(path) == sha, f"Pinned hard-negative input changed: {name}"


def test_full_hardneg_census_matches_hash_bound_receipt(request):
    missing = sorted(name for name in LOCAL_ARTIFACTS if not (ROOT / name).exists())
    if missing:
        pytest.skip(f"full hard-negative census requires local artifacts: {', '.join(missing)}")
    request.getfixturevalue("gateway_tokenizer")
    receipt = audit()
    assert receipt == json.loads(RECEIPT.read_text())
    assert receipt["rows"] == 15000 and receipt["status"] == "pass"
    assert not any(receipt["overlap"].values())


def test_protecting_public_figure_is_rejected_even_with_valid_person_offsets():
    text = "Historical display: Ada Lovelace; contact: Alice Willow."
    start = text.index("Ada Lovelace")
    row = dict(text=text, spans=[dict(start=start, end=start + 12, label="PERSON")], language="en", domain="gateway")
    meta = dict(
        language="en",
        hard_negatives=[dict(start=start, end=start + 12, text="Ada Lovelace", category="historical_figure")],
    )
    with pytest.raises(AssertionError, match="Protected hard negative"):
        validate_gold(row, meta)
    contact = text.index("Alice Willow")
    row["spans"] = [dict(start=contact, end=contact + 12, label="PERSON")]
    validate_gold(row, meta)


def test_repeated_contact_cannot_lose_its_annotation():
    row = dict(text="Alice Willow / Alice Willow", spans=[dict(start=0, end=12, label="PERSON")])
    with pytest.raises(AssertionError, match="contact mention"):
        validate_contact_mentions(row, {"PERSON": re.compile("Alice Willow")})
    row["spans"].append(dict(start=15, end=27, label="PERSON"))
    validate_contact_mentions(row, {"PERSON": re.compile("Alice Willow")})
