#!/usr/bin/env python3
"""Local-only RES-77 v2 build; resumable identical writes, refuses changed artifacts.

Run from the repository root with PYTHONPATH=. No HF client or publishing path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from europriv_bench.metrics import wilson_interval
from europriv_bench.national_id import parse_national_id
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from klusai.privacy.datasets.data.pl_generators import iban_pl_valid, nip_valid, regon9_valid
from klusai.privacy.datasets.data.pl_skeletons_v2 import generate_dataset as generate_pl
from klusai.privacy.datasets.data.ro_generators import cui_valid, iban_ro_valid
from klusai.privacy.datasets.data.ro_skeletons_v2 import generate_dataset as generate_ro

ROOT = Path(__file__).resolve().parents[1]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(rows) -> bytes:
    return ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n").encode()


def write_once(path: Path, data: bytes):
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Refusing to overwrite changed artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # An interrupted temporary write is regenerable. The final artifact is renamed atomically.
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def stratum(row):
    if row["domain"] != "legal":
        return row["domain"]
    return "contract" if row["text"].startswith(("CONTRACT", "UMOWA")) else "declaration"


def samples(rows, per_type=25, heldout_per_type=75):
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[stratum(row)].append(i)
    review_rng, heldout_rng = random.Random(7711), random.Random(7712)
    review, heldout = [], []
    for kind, indices in sorted(groups.items()):
        selected = review_rng.sample(indices, per_type)
        selected_set = set(selected)
        reserved = heldout_rng.sample([i for i in indices if i not in selected_set], heldout_per_type)
        for destination, picked in ((review, selected), (heldout, reserved)):
            for i in sorted(picked):
                destination.append({**rows[i], "source_index": i, "stratum": kind,
                                    "text_sha256": digest(rows[i]["text"].encode())})
    return review, heldout, {key: len(value) for key, value in sorted(groups.items())}


def validate_rows(rows):
    counts = Counter()
    seen_subjects = set()
    for row in rows:
        text, country = row["text"], row["country"]
        spans = [Span(s["start"], s["end"], s["label"]) for s in row["spans"]]
        validate_bioes(char_spans_to_bioes(text, spans))
        assert not re.search(r"[^\S\n]+[,.;]", text)
        assert not set("şţŞŢ") & set(text)
        counts["strict_bioes_docs"] += 1
        values = defaultdict(list)
        for s in row["spans"]:
            value = text[s["start"]:s["end"]]
            assert value
            values[s["label"]].append(value)
            if s["label"] == "ACCOUNT_ID":
                assert (iban_ro_valid if country == "RO" else iban_pl_valid)(value)
                counts["valid_iban"] += 1
            if s["label"] == "COMPANY_ID":
                validator = cui_valid if country == "RO" else nip_valid if len(value) == 10 else regon9_valid
                assert validator(value)
                counts["valid_company_id"] += 1
        pattern = r"(?<!\d)\d{13}(?!\d)" if country == "RO" else r"(?<!\d)\d{11}(?!\d)"
        for match in re.finditer(pattern, text):
            assert any(s["start"] == match.start() and s["end"] == match.end()
                       and s["label"] == "NATIONAL_ID" for s in row["spans"])
            counts["raw_id_mentions_covered"] += 1
        ids = {v for v in values["NATIONAL_ID"] if re.fullmatch(pattern, v)}
        for value in ids:
            info = parse_national_id(value, country)
            assert info.valid and info.extra["birth_date"] and info.extra["sex"] in ("M", "F")
            assert (country, value) not in seen_subjects, "duplicate synthetic subject across documents"
            seen_subjects.add((country, value))
            counts["valid_decoded_subjects"] += 1
            if row["domain"] == "clinical":
                date = ".".join(reversed(info.extra["birth_date"].split("-")))
                assert date in values["DATE"]
                sex = {"RO": {"M": "masculin", "F": "feminin"},
                       "PL": {"M": "męska", "F": "żeńska"}}[country][info.extra["sex"]]
                assert f"{'sex' if country == 'RO' else 'płeć'}: {sex}\n" in text
                counts["clinical_dob_sex_agreement"] += 1
        if row["domain"] == "clinical":
            assert len(ids) == 1
    return {name: {"n": n, "passed": n, "wilson_95": wilson_interval(n, n)}
            for name, n in sorted(counts.items())}


def build(output: Path, n=1500, seed=2026101277):
    # Include generator dependencies, shared gate, patch targets, build script and protocol.
    sources = [*sorted((ROOT / "klusai/privacy/datasets/data").glob("*.py")),
               ROOT / "scripts/generate_realskeleton_v2.py", ROOT / "docs/res77-v2-review-protocol.md"]
    hashes = {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in sources}
    for offset, (language, generate) in enumerate((("ro", generate_ro), ("pl", generate_pl))):
        config = f"{language}-realskeleton-v2"
        rows = list(generate(n, seed + offset))
        validation = validate_rows(rows)
        review, heldout, strata = samples(rows)
        payloads = {"test.jsonl": encode(rows), "self-review.jsonl": encode(review),
                    "heldout-review.jsonl": encode(heldout)}
        manifest = {
            "config": config, "config_status": "dev", "n": n, "seed": seed + offset,
            "generation_seed_count": 1, "review_seed": 7711, "heldout_seed": 7712,
            "review_n": len(review), "heldout_n": len(heldout), "strata": strata,
            "license": "CC-BY-4.0", "source_url": "https://github.com/klusai/klusai-datasets",
            "parent_data_url": "https://huggingface.co/datasets/klusai/europriv-bench",
            "source_kind": "original authored prose and existing synthetic generators; no new corpus",
            "scope": "four correspondence types, one family; RO education family B not included",
            "protocol_sha256": hashes["docs/res77-v2-review-protocol.md"],
            "source_sha256": hashes, "files_sha256": {name: digest(data) for name, data in payloads.items()},
            "validation": validation,
        }
        # Verify the manifest before touching files when resuming an existing build.
        directory = output / config
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
        if (directory / "manifest.json").exists() and (directory / "manifest.json").read_bytes() != manifest_bytes:
            raise ValueError(f"Immutable config differs: {config}; use a separate build directory")
        for name, data in payloads.items():
            write_once(directory / name, data)
        write_once(directory / "manifest.json", manifest_bytes)
        print(json.dumps({"config": config, "n": n, "strata": strata, "validation": validation}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=2026101277)
    args = parser.parse_args()
    build(args.output, args.n, args.seed)
