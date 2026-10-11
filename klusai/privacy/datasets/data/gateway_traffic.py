"""RES-123: gateway contract, append-only split ledger and offline contamination gates.

No generation, network, model calls, or publication. All offsets are Python Unicode
character offsets within one text part. Identity keys are globally namespaced by the
producer; source-document identities intentionally do not include source revisions.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from europriv_bench.taxonomy import ENTITY_NAMES, TAXONOMY_VERSION

from .licensing import assert_clean_license

LANGUAGES = ("ro", "en", "de", "fr", "es", "it", "nl", "pl")
Split = Literal["train", "dev", "test"]
Language = Literal["ro", "en", "de", "fr", "es", "it", "nl", "pl"]
Nonempty = Annotated[str, Field(min_length=1, pattern=r"\S")]
SHA256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Revision = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
KPLabel = Literal[tuple(ENTITY_NAMES)]
FEATURES = (
    "aliases",
    "email",
    "phone",
    "address",
    "national_id",
    "bank_account",
    "card",
    "dob",
    "case_id",
    "company_id",
    "medical_id",
    "health_condition",
    "secret",
    "split_identifier",
    "obfuscated_identifier",
    "quoted_history",
    "unicode",
    "punctuation",
    "json_code",
    "tool_payload",
    "repeated_entity",
    "code_switch",
    "public_date",
    "public_org",
    "public_statute",
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TextPart(Strict):
    type: Literal["text"] = "text"
    text: Nonempty


class Message(Strict):
    role: Literal["system", "developer", "user", "assistant", "tool"]
    parts: Annotated[list[TextPart], Field(min_length=1)]


class Span(Strict):
    message: Annotated[int, Field(ge=0)]
    part: Annotated[int, Field(ge=0)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    text: Nonempty
    label: KPLabel
    entity_id: Nonempty
    subject_id: Nonempty
    identifier_class: Literal["DIRECT", "QUASI"]
    protection: Literal["mask", "pseudonymize", "retain"]


class Review(Strict):
    annotators: Annotated[list[Nonempty], Field(min_length=1)]
    native_reviewers: list[Nonempty]
    adjudicator: Nonempty | None
    guide_sha256: SHA256

    @model_validator(mode="after")
    def validate_reviewers(self):
        if len(set(self.annotators)) != len(self.annotators):
            raise ValueError("duplicate annotators")
        if len(set(self.native_reviewers)) != len(self.native_reviewers):
            raise ValueError("duplicate native reviewers")
        if set(self.native_reviewers) - set(self.annotators):
            raise ValueError("native reviewers must be recorded as annotators")
        return self


class Provenance(Strict):
    source_revision: Revision
    source_split: Nonempty
    source_record_id: Nonempty
    artifact_path: Nonempty
    file_sha256: SHA256
    author: Nonempty
    tool: Nonempty
    session: Nonempty
    generator_version: Nonempty
    prompt_sha256: SHA256
    content_sha256: SHA256
    seed: Annotated[int, Field(ge=0)]
    identity_provenance: Nonempty
    exclusions: list[Nonempty]
    review: Review


class Conversation(Strict):
    schema_version: Literal["gateway-traffic-v1"]
    config_status: Literal["dev"]
    taxonomy_version: Literal[TAXONOMY_VERSION]
    id: Nonempty
    language: Language
    secondary_languages: list[Language]
    source_id: Nonempty
    stratum: Literal["original-synthetic", "external-synthetic"]
    scenario_id: Nonempty
    family_id: Nonempty
    source_document_id: Nonempty
    translation_group_id: Nonempty
    subject_ids: list[Nonempty]
    split: Split
    messages: Annotated[list[Message], Field(min_length=1, max_length=8)]
    spans: list[Span]
    features: list[Nonempty]
    dense_document: bool
    token_count: Annotated[int, Field(ge=32, le=2048)]
    tokenizer_id: Nonempty
    tokenizer_revision: Revision
    truncated: Literal[False]
    provenance: Provenance

    @model_validator(mode="after")
    def validate_content(self):
        if len(self.subject_ids) != len(set(self.subject_ids)):
            raise ValueError("duplicate subjects")
        if set(self.features) - set(FEATURES):
            raise ValueError("unknown coverage feature")
        if self.language in self.secondary_languages or len(set(self.secondary_languages)) != len(
            self.secondary_languages
        ):
            raise ValueError("invalid secondary languages")
        if bool(self.secondary_languages) != ("code_switch" in self.features):
            raise ValueError("code_switch requires secondary languages and vice versa")
        subjects, occupied, entities = set(), {}, {}
        for span in self.spans:
            if span.label not in ENTITY_NAMES:
                raise ValueError(f"unknown KP label: {span.label}")
            try:
                text = self.messages[span.message].parts[span.part].text
            except IndexError as exc:
                raise ValueError("span references missing message/part") from exc
            if not 0 <= span.start < span.end <= len(text) or text[span.start : span.end] != span.text:
                raise ValueError("invalid character span")
            key = (span.message, span.part)
            for start, end in occupied.setdefault(key, []):
                if span.start < end and start < span.end:
                    raise ValueError("overlapping spans")
            occupied[key].append((span.start, span.end))
            subjects.add(span.subject_id)
            identity = (span.subject_id, span.label)
            if entities.setdefault(span.entity_id, identity) != identity:
                raise ValueError("entity coreference changed subject/label")
        if subjects != set(self.subject_ids):
            raise ValueError("subject IDs must exactly match annotated subjects")
        if not self.subject_ids and self.dense_document:
            raise ValueError("dense positive stratum requires subjects")
        if len(self.subject_ids) > 5 and not self.dense_document:
            raise ValueError("more than five subjects requires dense stratum")
        if digest(self.messages_payload()) != self.provenance.content_sha256:
            raise ValueError("content hash mismatch")
        return self

    def messages_payload(self):
        return [m.model_dump() for m in self.messages]


def digest(value) -> str:
    """Canonical UTF-8 JSON SHA-256; shared by ledger, manifest and content."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def text_digest(text: str) -> str:
    """Whitespace/case/NFKC-normalized exact-text detection; NOT semantic similarity."""
    return hashlib.sha256(" ".join(unicodedata.normalize("NFKC", text).casefold().split()).encode()).hexdigest()


def identity_keys(row: Conversation) -> list[str]:
    return [
        f"conversation:{row.id}",
        f"family:{row.family_id}",
        f"scenario:{row.scenario_id}",
        f"document:{row.source_id}:{row.source_document_id}",
        f"translation:{row.translation_group_id}",
        *(f"subject:{s}" for s in row.subject_ids),
        *(f"text:{text_digest(p.text)}" for m in row.messages for p in m.parts),
    ]


def extend_ledger(previous: dict[str, str], rows: list[Conversation]) -> dict[str, str]:
    """Return a new ledger; never reassign an existing identity, even transitively.

    Import the committed ledger plus ALL previous release identities before extending.
    Colliding components fail rather than moving any previously assigned conversation.
    """
    ledger = dict(previous)
    if set(ledger.values()) - {"train", "dev", "test"}:
        raise ValueError("invalid ledger split")
    for row in rows:
        for key in identity_keys(row):
            if key in ledger and ledger[key] != row.split:
                raise ValueError(f"cross-split identity: {key}")
            ledger[key] = row.split
    return dict(sorted(ledger.items()))


def load_manifest(path: Path) -> dict:
    manifest = yaml.safe_load(path.read_text())
    root = path.resolve().parent.parent
    if manifest["dataset"] != "gateway-traffic-v1" or manifest["languages"] != list(LANGUAGES):
        raise ValueError("gateway name/languages changed")
    if manifest["targets"] != {"test": 1000, "dev": 200}:
        raise ValueError("v1 targets changed")
    if set(manifest["required_labels"]) - set(ENTITY_NAMES):
        raise ValueError("coverage labels are not in the KP taxonomy")
    for source in manifest["sources"].values():
        assert_clean_license(source["license"], source["url"])
        if not source["permitted_train"] or not source["permitted_redistribute"]:
            raise ValueError("source rights do not permit training and redistribution")
        if len(source["revision"]) != 40 or any(c not in "0123456789abcdef" for c in source["revision"]):
            raise ValueError("source revision must be a full Git hash")
        if file_digest(root / source["license_evidence"]) != source["license_sha256"]:
            raise ValueError("license evidence hash mismatch")
        if not source["attribution"] or not source["url"].startswith("https://"):
            raise ValueError("missing source attribution/URL")
    for key in ("split_plan", "training_inventory"):
        entry = manifest[key]
        if file_digest(root / entry["path"]) != entry["sha256"]:
            raise ValueError(f"{key} hash mismatch")
    plan = json.loads((root / manifest["split_plan"]["path"]).read_text())
    for split, target in manifest["targets"].items():
        for language in LANGUAGES:
            if sum(f["slots_per_language"] for f in plan["families"] if f["split"] == split) != target:
                raise ValueError(f"split plan target mismatch: {split}/{language}")
    families = [f["id"] for f in plan["families"]]
    if len(families) != len(set(families)):
        raise ValueError("duplicate reserved family")
    if set(f["split"] for f in plan["families"]) != {"train", "dev", "test"}:
        raise ValueError("all three split reservations are required")
    return manifest


def validate_collection(rows: list[Conversation], manifest: dict, plan: dict, ledger: dict) -> dict:
    ids = [r.id for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate conversation ID")
    reservations = {f["id"]: f for f in plan["families"]}
    counts = Counter()
    for row in rows:
        source = manifest["sources"].get(row.source_id)
        if source is None or row.split not in source["allowed_gateway_splits"]:
            raise ValueError("source not admitted for this gateway split (TAB is anchor-only)")
        if row.stratum != source["stratum"]:
            raise ValueError("source stratum mismatch")
        if row.source_id != "originals" and row.provenance.source_revision != source["revision"]:
            raise ValueError("source revision mismatch")
        if row.source_id == "originals":
            family = reservations.get(row.family_id)
            if family is None or family["split"] != row.split:
                raise ValueError("unreserved/wrong-split original family")
            counts[(row.family_id, row.language)] += 1
            if row.split != "train" and counts[(row.family_id, row.language)] > family["slots_per_language"]:
                raise ValueError("reserved family capacity exceeded")
        # External rows need independently established family/subject/sibling metadata;
        # source validation split alone does not establish any of those identities.
    reserved = {f"family:{f['id']}": f["split"] for f in plan["families"]}
    for key, value in reserved.items():
        if key in ledger and ledger[key] != value:
            raise ValueError("ledger contradicts frozen family reservation")
    return extend_ledger(reserved | ledger, rows)


def coverage_report(rows: list[Conversation], manifest: dict) -> dict:
    """Exact v1 quotas for the original stratum; external rows cannot fill them.

    Coverage tags are author assertions, checked alongside labels/counts and later by
    native review. Token counts must come from the recorded tokenizer, without truncation.
    """
    errors, cells = [], {}
    for split, target in manifest["targets"].items():
        for language in LANGUAGES:
            subset = [
                r for r in rows if r.split == split and r.language == language and r.stratum == "original-synthetic"
            ]
            mix, lengths, features, labels = Counter(), Counter(), set(), set()
            reviewed = 0
            for row in subset:
                n = len(row.subject_ids)
                mix["negative" if n == 0 else "dense" if row.dense_document else "small" if n <= 2 else "medium"] += 1
                lengths["short" if row.token_count <= 128 else "medium" if row.token_count <= 512 else "long"] += 1
                features.update(row.features)
                labels.update(s.label for s in row.spans if s.protection != "retain")
                review = row.provenance.review
                reviewed += len(set(review.native_reviewers)) >= 2 and review.adjudicator is not None
            key = f"{split}/{language}"
            cells[key] = {
                "n": len(subset),
                "mix": dict(mix),
                "lengths": dict(lengths),
                "native_double_reviewed": reviewed,
                "labels": sorted(labels),
                "features": sorted(features),
            }
            if len(subset) != target:
                errors.append(f"{key}: expected {target} originals, got {len(subset)}")
            for name, percent in manifest["subject_mix_percent"].items():
                if mix[name] * 100 != target * percent:
                    errors.append(f"{key}: subject quota {name}")
            for name, percent in manifest["length_mix_percent"].items():
                if lengths[name] * 100 != target * percent:
                    errors.append(f"{key}: length quota {name}")
            for feature in FEATURES:
                if feature not in features:
                    errors.append(f"{key}: missing feature {feature}")
            for label in manifest["required_labels"]:
                if label not in labels:
                    errors.append(f"{key}: missing label {label}")
    for language in LANGUAGES:
        reviewed = sum(cells[f"{split}/{language}"]["native_double_reviewed"] for split in manifest["targets"])
        if reviewed < 100:
            errors.append(f"{language}: fewer than 100 native double-reviewed/adjudicated conversations")
    return {"status": "pass" if not errors else "incomplete", "cells": cells, "errors": errors}


def iter_training_rows(path: Path):
    """Local only: HF single-file parquet must first be hf_hub_download'ed."""
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq

        for batch in pq.ParquetFile(path).iter_batches(batch_size=4096):
            yield from batch.to_pylist()
    else:
        with path.open() as stream:
            for line in stream:
                if line.strip():
                    yield json.loads(line)


def audit_training(rows: list[Conversation], inventory: dict, paths: dict[str, Path]) -> dict:
    """Hash-check EVERY inventoried corpus, then compare normalized part/full text.

    Legacy corpora lack subject/source-document/translation IDs. Missing identities
    are reported, never interpreted as evidence of semantic disjointness. A complete
    release additionally requires human family/identity audit against this inventory.
    """
    expected = {c["id"] for c in inventory["corpora"]}
    if set(paths) != expected:
        raise ValueError(f"training inventory paths mismatch: missing={sorted(expected - set(paths))}")
    fingerprints = {}
    for row in rows:
        if row.split == "train":
            continue
        texts = [p.text for m in row.messages for p in m.parts]
        for text in texts + ["\n".join(texts)]:
            fingerprints.setdefault(text_digest(text), set()).add(row.id)
    hits, scanned = [], []
    for corpus in inventory["corpora"]:
        path = paths[corpus["id"]]
        if file_digest(path) != corpus["file_sha256"]:
            raise ValueError(f"training file hash mismatch: {corpus['id']}")
        n = 0
        for item in iter_training_rows(path):
            n += 1
            if "text" not in item or not isinstance(item["text"], str):
                raise ValueError(f"training row has no text: {corpus['id']}")
            for row_id in sorted(fingerprints.get(text_digest(item["text"]), ())):
                hits.append({"corpus": corpus["id"], "row": n, "conversation": row_id})
        if n != corpus["rows"]:
            raise ValueError(f"training row count mismatch: {corpus['id']}")
        scanned.append({"id": corpus["id"], "rows": n, "sha256": corpus["file_sha256"]})
    return {
        "status": "overlap" if hits else "pending_generation" if not rows else "exact_text_clear_only",
        "candidate_conversations": len(rows),
        "scanned": scanned,
        "hits": hits,
        "semantic_disjointness": "unverified: legacy subject/document/translation IDs unavailable",
        "inventory_scope": inventory["scope"],
        "metric_n": 0,
        "seeds": 0,
        "ci": None,
    }
