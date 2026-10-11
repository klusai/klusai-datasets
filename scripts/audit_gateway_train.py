"""Census of local TRAIN against frozen gateway test/dev; no model quality claim."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from itertools import zip_longest

from europriv_bench.national_id import REGISTRY
from klusai.privacy.datasets.data.credential_scan import findings
from klusai.privacy.datasets.data.en_generators import nino_format_valid
from klusai.privacy.datasets.data.gateway_traffic import (
    FEATURES,
    Conversation,
    digest,
    file_digest,
    load_manifest,
    text_digest,
    validate_collection,
)
from klusai.privacy.datasets.data.gateway_train import (
    GUIDE,
    INPUT,
    LANGUAGES,
    OUTPUT,
    PROSE,
    ROOT,
    base,
    heldout_rows,
    identity_values,
    training_row,
)
from klusai.privacy.datasets.data.gateway_train_audit import (
    PERMUTATIONS,
    SEED,
    SHINGLE_WORDS,
    THRESHOLD,
    SimilarityIndex,
    shingles,
    skeleton,
)


def audit():
    manifest = load_manifest(ROOT / "conf/gateway_traffic_manifest.yaml")
    extension = manifest["train_extension"]
    for entry in extension["frozen_heldout"].values():
        assert file_digest(ROOT / entry["path"]) == entry["sha256"], "Frozen heldout changed"
    for name, sha in extension["artifacts"].items():
        assert file_digest(ROOT / name) == sha, f"Train artifact changed: {name}"
    plan = json.loads((ROOT / manifest["split_plan"]["path"]).read_text())
    previous_path = ROOT / "docs/gateway-authoring/audit-v3.json"
    previous = json.loads(previous_path.read_text())["ledger"]
    held = list(heldout_rows())
    if Counter(r["split"] for r in held) != {"test": 8000, "dev": 1600}:
        raise ValueError("Incomplete heldout input")
    holdout_values = identity_values(held)
    held_families = {r["family_id"] for r in held}
    held_subjects = {s for r in held for s in r["subject_ids"]}
    held_texts = {text_digest(training_row(r)["text"]) for r in held}
    held_kp = [training_row(r) for r in held]
    indexes = {
        mode: SimilarityIndex(
            shingles(skeleton(r) if mode == "masked" else r["text"], mode == "masked") for r in held_kp
        )
        for mode in ("raw", "masked")
    }
    hits = Counter()
    cells = defaultdict(
        lambda: dict(
            n=0, spans=0, mix=Counter(), lengths=Counter(), labels=set(), features=set(), min_tokens=2048, max_tokens=0
        )
    )
    tokenizer = base.get_tokenizer()
    seen_ids, seen_texts = set(), set()
    used_subjects = set()
    ledger = previous
    train_path = OUTPUT / "train.jsonl"
    kp_path = OUTPUT / "train-kp.jsonl"
    draft_path = INPUT / "train.jsonl"
    draft_sha = file_digest(draft_path)
    pools = json.loads((INPUT / "pools.json").read_text())
    national_checks = {}
    for language, people in pools.items():
        assert len(people) == 512
        for person in people:
            country = base.COUNTRIES[language]
            if country == "GB":
                assert nino_format_valid(person["national"])
                continue
            parsed = REGISTRY[country].parse(person["national"])
            assert parsed.valid
            extra = parsed.extra
            if extra.get("birth_date"):
                assert person["dob"] == extra["birth_date"]
            elif country == "FR":
                assert person["dob"] == f"{extra['birth_month']:02d}/{extra['birth_year_2digit']}"
            elif country == "IT":
                assert (
                    person["dob"] == f"{extra['birth_day']:02d}/{extra['birth_month']:02d}/{extra['birth_year_2digit']}"
                )
        n = len(people)
        z = 1.959963984540054
        center = (1 + z * z / (2 * n)) / (1 + z * z / n)
        half = z * math.sqrt(z * z / (4 * n * n)) / (1 + z * z / n)
        national_checks[language] = dict(
            n=n,
            passed=n,
            wilson95=[center - half, min(1.0, center + half)],
            scope="Unique synthetic pool values; GB format only; census, not accuracy",
        )
    pool_ids = {p["subject_id"] for people in pools.values() for p in people}
    pool_values = identity_values(
        [
            {"spans": [{"label": label, "text": p[key]} for key, label in zip(base.KEYS, base.LABELS)]}
            for people in pools.values()
            for p in people
        ]
    )
    assert all(not pool_values[k] & holdout_values[k] for k in pool_values), "Pool/heldout value overlap"
    with train_path.open() as strict, kp_path.open() as kp, draft_path.open() as drafts:
        batch = []
        for number, lines in enumerate(zip_longest(strict, kp, drafts), 1):
            if None in lines:
                raise ValueError("Train, KP and draft row counts differ")
            row, exported, draft = [json.loads(line) for line in lines]
            validated = Conversation.model_validate(row)
            batch.append(validated)
            assert row["split"] == "train"
            assert row["id"] not in seen_ids
            seen_ids.add(row["id"])
            assert row["provenance"]["file_sha256"] == draft_sha
            assert row["provenance"]["prompt_sha256"] == file_digest(PROSE)
            assert row["provenance"]["review"]["guide_sha256"] == file_digest(GUIDE)
            assert exported == training_row(row)
            assert row["id"] == draft["id"]
            assert exported["language"] in LANGUAGES and exported["domain"] == "gateway"
            assert set(exported) == {"text", "spans", "language", "domain"}
            hits["family"] += row["family_id"] in held_families
            hits["subject"] += bool(set(row["subject_ids"]) & held_subjects)
            assert set(row["subject_ids"]) <= pool_ids
            used_subjects.update(row["subject_ids"])
            values = identity_values([row])
            hits["subject_value"] += any(values[k] & holdout_values[k] for k in values)
            hashed = text_digest(exported["text"])
            hits["exact"] += hashed in held_texts
            hits["within_train_exact"] += hashed in seen_texts
            seen_texts.add(hashed)
            hits["provider_secret"] += bool(list(findings(exported["text"])))
            for mode, index in indexes.items():
                doc = shingles(skeleton(exported) if mode == "masked" else exported["text"], mode == "masked")
                result = index.query(doc)
                hits[f"{mode}_near_duplicate"] += bool(result["matches"])
            tokens = base.count_tokens(row["messages"], tokenizer)
            assert tokens == row["token_count"]
            has_unicode = any(ord(c) > 127 for c in exported["text"])
            assert ("unicode" in row["features"]) == has_unicode
            cell = cells[row["language"]]
            cell["n"] += 1
            cell["spans"] += len(row["spans"])
            cell["min_tokens"] = min(cell["min_tokens"], tokens)
            cell["max_tokens"] = max(cell["max_tokens"], tokens)
            mix = (
                "negative"
                if not row["subject_ids"]
                else ("dense" if row["dense_document"] else "small" if len(row["subject_ids"]) <= 2 else "medium")
            )
            length = "short" if tokens <= 128 else "medium" if tokens <= 512 else "long"
            assert mix == draft["intended_mix"] and length == draft["intended_length"]
            cell["mix"][mix] += 1
            cell["lengths"][length] += 1
            cell["labels"].update(s["label"] for s in row["spans"])
            cell["features"].update(row["features"])
            if number % 5000 == 0:
                ledger = validate_collection(batch, manifest, plan, ledger)
                batch = []
                print(f"audited {number}: {dict(hits)}", flush=True)
        if batch:
            ledger = validate_collection(batch, manifest, plan, ledger)
    for language, cell in cells.items():
        assert cell["n"] == 5000, (language, cell)
        assert cell["mix"] == {"negative": 1000, "small": 2000, "medium": 1500, "dense": 500}
        assert cell["lengths"] == {"short": 2500, "medium": 1750, "long": 750}
        assert set(manifest["required_labels"]) <= cell["labels"], (language, cell["labels"])
        assert set(FEATURES) <= cell["features"], (language, set(FEATURES) - cell["features"])
        cell["labels"] = sorted(cell["labels"])
        cell["features"] = sorted(cell["features"])
    assert set(cells) == set(LANGUAGES)
    assert all(ledger[k] == v for k, v in previous.items())
    paths = [
        train_path,
        kp_path,
        draft_path,
        INPUT / "pools.json",
        OUTPUT / "test.jsonl",
        OUTPUT / "dev.jsonl",
        PROSE,
        GUIDE,
        ROOT / "conf/gateway_traffic_splits.json",
    ]
    receipt = dict(
        status="pass" if not any(hits.values()) else "fail",
        train_rows=len(seen_ids),
        heldout_rows=len(held),
        used_subjects=len(used_subjects),
        national_id_checks=national_checks,
        overlap=dict(hits),
        cells=dict(cells),
        minhash=dict(
            seed=SEED,
            permutations=PERMUTATIONS,
            bands=32,
            rows_per_band=4,
            word_shingles=SHINGLE_WORDS,
            threshold=THRESHOLD,
            certification="Complete exact Jaccard prefix join at the same threshold; "
            "raw and PII-masked/numeric-normalized full text",
            unique_heldout={m: len(i.documents) for m, i in indexes.items()},
            unique_train={m: len(i.cache) for m, i in indexes.items()},
        ),
        parent_ledger_sha256=file_digest(previous_path),
        ledger_sha256=digest(ledger),
        ledger_entries=len(ledger),
        generation_seeds=1,
        scoring_seeds=0,
        files={str(p.relative_to(ROOT)): file_digest(p) for p in paths},
        limitations=[
            "No model training or harness scoring; no performance claim or performance CI.",
            "No independent semantic/native review; lexical overlap gates are not semantic proof.",
            "Census counts have no sampling CI; one deterministic generation seed.",
            "Legacy training-inventory semantic disjointness is outside this train-vs-heldout audit.",
        ],
    )
    # Local ledger is resumable evidence; its digest and parent are committed in the compact receipt.
    (OUTPUT / "train-ledger.json").write_text(json.dumps(ledger, sort_keys=True) + "\n")
    return receipt


def main():
    result = audit()
    path = ROOT / "docs/gateway-authoring/train-audit.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"cells", "files"}}, indent=2))
    if result["status"] != "pass":
        raise SystemExit("Train overlap audit failed")


if __name__ == "__main__":
    main()
