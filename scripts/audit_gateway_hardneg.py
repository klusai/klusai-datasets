"""Census of hard-negative gold, disjoint subjects/families and raw/masked heldout overlap."""

from __future__ import annotations

import json
import re
from collections import Counter
from itertools import zip_longest

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from klusai.privacy.datasets.data.credential_scan import findings, scan_paths
from klusai.privacy.datasets.data.gateway_hardneg import (
    CATEGORIES,
    COUNTS,
    GUIDE,
    INPUT,
    KP,
    LABELS,
    MANIFEST,
    META,
    POOL_SIZE,
    PROSE,
    RECEIPT,
    ROOT,
    SEED,
    make_pools,
    parent_rows,
    rows,
)
from klusai.privacy.datasets.data.gateway_traffic import file_digest, load_manifest, text_digest
from klusai.privacy.datasets.data.gateway_train import base, heldout_rows, identity_values, training_row
from klusai.privacy.datasets.data.gateway_train_audit import SimilarityIndex, shingles, skeleton


def validate_gold(row, meta):
    assert set(row) == {"text", "spans", "language", "domain"}
    assert row["domain"] == "gateway" and row["language"] == meta["language"]
    text = row["text"]
    previous = 0
    for span in row["spans"]:
        assert set(span) == {"start", "end", "label"}
        assert previous <= span["start"] < span["end"] <= len(text)
        assert span["label"] in LABELS
        previous = span["end"]
    validate_bioes(char_spans_to_bioes(text, [Span(**s) for s in row["spans"]]))
    assert meta["hard_negatives"]
    for negative in meta["hard_negatives"]:
        start, end = negative["start"], negative["end"]
        assert 0 <= start < end <= len(text)
        assert text[start:end] == negative["text"]
        assert negative["category"] in CATEGORIES
        assert all(end <= s["start"] or start >= s["end"] for s in row["spans"]), "Protected hard negative"


def validate_contact_mentions(row, patterns):
    """Independent literal pool census catches missing/repeated contact annotations."""
    expected = {
        (match.start(), match.end(), label)
        for label, pattern in patterns.items()
        for match in pattern.finditer(row["text"])
    }
    actual = {(s["start"], s["end"], s["label"]) for s in row["spans"]}
    assert actual == expected, "Missing, extra or mislabeled contact mention"


def audit():
    manifest = json.loads(MANIFEST.read_text())
    parent_manifest = load_manifest(ROOT / "conf/gateway_traffic_manifest.yaml")
    pinned = parent_manifest["train_extension"]
    for entry in pinned["frozen_heldout"].values():
        assert file_digest(ROOT / entry["path"]) == entry["sha256"], "Frozen heldout changed"
    parent_kp = ROOT / "artifacts/gateway-traffic-v1/train-kp.jsonl"
    assert file_digest(parent_kp) == pinned["artifacts"][str(parent_kp.relative_to(ROOT))]
    assert manifest["source"]["license"] == "CC-BY-4.0"
    assert manifest["source"]["trainable"] and manifest["source"]["redistributable"]
    held = list(heldout_rows())
    assert Counter(r["split"] for r in held) == {"test": 8000, "dev": 1600}
    held_kp = [training_row(r) for r in held]
    held_values = identity_values(held)
    parent = list(parent_rows())
    assert len(parent) == 40000
    parent_values = identity_values(parent)
    pools = json.loads((INPUT / "pools.json").read_text())
    prose = json.loads(PROSE.read_text())
    assert pools == make_pools(prose), "Pool reproduction mismatch"
    contact_patterns = {
        language: {
            label: re.compile("|".join(re.escape(p[key]) for p in people))
            for key, label in zip(("name", "email", "phone", "address"), LABELS)
        }
        for language, people in pools.items()
    }
    pool_values = identity_values(
        [
            dict(text=p[k], spans=[dict(start=0, end=len(p[k]), label=label)])
            for people in pools.values()
            for p in people
            for k, label in zip(("name", "email", "phone", "address"), LABELS)
        ]
    )
    for label, values in pool_values.items():
        assert not values & held_values[label], "Heldout pool identity overlap"
        assert not values & parent_values[label], "Parent train pool identity overlap"
    held_families = {r["family_id"] for r in held}
    held_subjects = {s for r in held for s in r["subject_ids"]}
    held_texts = {text_digest(r["text"]) for r in held_kp}
    parent_texts = {text_digest(r["text"]) for r in parent}
    indexes = {
        mode: SimilarityIndex(
            shingles(skeleton(r) if mode == "masked" else r["text"], mode == "masked") for r in held_kp
        )
        for mode in ("raw", "masked")
    }
    hits = Counter(
        {
            key: 0
            for key in (
                "family",
                "subject_id",
                "subject_value",
                "heldout_exact",
                "parent_exact",
                "within_exact",
                "raw_near_duplicate",
                "masked_near_duplicate",
                "provider_secret",
            )
        }
    )
    cells = {
        lang: dict(
            n=0,
            spans=0,
            mix=Counter(),
            families=Counter(),
            layouts=Counter(),
            categories=Counter(),
            min_tokens=100000,
            max_tokens=0,
            min_hard_negatives=100000,
        )
        for lang in COUNTS
    }
    seen_texts, seen_ids, used_subjects = set(), set(), set()
    tokenizer = base.get_tokenizer()
    with KP.open() as kp, META.open() as metadata:
        for number, triple in enumerate(zip_longest(kp, metadata, rows(prose, pools)), 1):
            assert all(item is not None for item in triple), "Export, metadata or reproduction count differs"
            line, meta_line, expected = triple
            row, meta = json.loads(line), json.loads(meta_line)
            assert (row, meta) == expected, "Artifact differs from deterministic reproduction"
            validate_gold(row, meta)
            validate_contact_mentions(row, contact_patterns[row["language"]])
            assert meta["split"] == "train" and meta["id"] not in seen_ids
            seen_ids.add(meta["id"])
            hits["family"] += meta["family_id"] in held_families
            hits["subject_id"] += bool(set(meta["subject_ids"]) & held_subjects)
            values = identity_values([row])
            hits["subject_value"] += any(values[k] & held_values[k] for k in values)
            hashed = text_digest(row["text"])
            hits["heldout_exact"] += hashed in held_texts
            hits["parent_exact"] += hashed in parent_texts
            hits["within_exact"] += hashed in seen_texts
            seen_texts.add(hashed)
            used_subjects.update(meta["subject_ids"])
            hits["provider_secret"] += bool(list(findings(row["text"])))
            for mode, index in indexes.items():
                doc = shingles(skeleton(row) if mode == "masked" else row["text"], mode == "masked")
                hits[f"{mode}_near_duplicate"] += bool(index.query(doc)["matches"])
            cell = cells[row["language"]]
            cell["n"] += 1
            cell["spans"] += len(row["spans"])
            cell["mix"][meta["mix"]] += 1
            cell["families"][meta["family_id"]] += 1
            cell["layouts"][meta["layout"]] += 1
            cell["categories"].update(n["category"] for n in meta["hard_negatives"])
            cell["min_hard_negatives"] = min(cell["min_hard_negatives"], len(meta["hard_negatives"]))
            tokens = len(tokenizer.encode(row["text"]).ids)
            assert 32 <= tokens <= 2048, "Unexpected truncation risk"
            cell["min_tokens"] = min(cell["min_tokens"], tokens)
            cell["max_tokens"] = max(cell["max_tokens"], tokens)
            n = len(meta["subject_ids"])
            assert {"negative": n == 0, "small": 1 <= n <= 2, "medium": 3 <= n <= 5, "dense": n == 6}[meta["mix"]]
            assert bool(n) == bool(row["spans"])
            if number % 1500 == 0:
                print(f"audited {number}: {dict(hits)}", flush=True)
    for language, cell in cells.items():
        n = COUNTS[language]
        assert cell["n"] == n and len(cell["families"]) == 8
        assert cell["mix"] == {"negative": n // 5, "small": n * 2 // 5, "medium": n * 3 // 10, "dense": n // 10}
        assert set(cell["categories"]) == set(CATEGORIES)
        assert len(pools[language]) == POOL_SIZE
        cell["layouts"] = {str(k): v for k, v in sorted(cell["layouts"].items())}
    paths = [
        KP,
        META,
        INPUT / "pools.json",
        PROSE,
        GUIDE,
        MANIFEST,
        ROOT / "klusai/privacy/datasets/data/gateway_hardneg.py",
        ROOT / "scripts/author_gateway_hardneg.py",
        ROOT / "scripts/audit_gateway_hardneg.py",
    ]
    assert not list(scan_paths(paths)), "Provider-shaped credential in hard-negative inputs or outputs"
    result = dict(
        status="pass" if not any(hits.values()) else "fail",
        rows=len(seen_ids),
        heldout_rows=len(held),
        parent_train_rows=len(parent),
        subjects=len(used_subjects),
        overlap=dict(hits),
        cells=cells,
        files={str(p.relative_to(ROOT)): file_digest(p) for p in paths},
        heldout_files=pinned["frozen_heldout"],
        parent_kp_sha256=file_digest(parent_kp),
        generation_seeds=1,
        generation_seed=SEED,
        scoring_seeds=0,
        overlap_method=dict(
            threshold=0.8,
            word_shingles=5,
            permutations=128,
            seed=12703,
            views=["raw", "PII-masked and numeric-normalized"],
            certification="Complete exact Jaccard prefix join supplements MinHash candidates",
        ),
        limitations=[
            "Census counts, not sampled estimates: sampling confidence intervals are not applicable.",
            "No model training or harness scoring; no performance CI or win claim.",
            "No independent native-language or semantic review; construction gold remains provisional.",
            "Repeated templates and translated families limit independence; one deterministic generation seed.",
            "No real PII is collected. Synthetic phone/address assignments are not verified against registries.",
            "Only PERSON/EMAIL/PHONE/ADDRESS positives; parent TRAIN retains other labels and long-document coverage.",
            "Parent TRAIN comparison covers identities and exact text, not near-duplicate semantics.",
        ],
    )
    return result


def main():
    result = audit()
    RECEIPT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"cells", "files"}}, indent=2))
    if result["status"] != "pass":
        raise SystemExit("Hard-negative overlap audit failed")


if __name__ == "__main__":
    main()
