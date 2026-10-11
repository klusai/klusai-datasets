"""RES-127 original TRAIN families; never reuse a dev/test prose renderer."""

from __future__ import annotations

import json
import random
import unicodedata
from collections import defaultdict
from functools import lru_cache

from . import gateway_authoring as base
from .gateway_authoring_v2 import allocation
from .gateway_authoring_v3 import KEY_FEATURE
from .gateway_traffic import LANGUAGES, Conversation, file_digest
from .it_generators import _consonant_code

ROOT = base.ROOT
PROSE = ROOT / "docs/gateway-authoring/prose-train.json"
GUIDE = ROOT / "docs/gateway-authoring/train.md"
OUTPUT = ROOT / "artifacts/gateway-traffic-v1"
INPUT = OUTPUT / "originals/train-v1"
SEED = 127
POOL_SIZE = 512
IDENTITY_LABELS = frozenset(
    {"PERSON", "EMAIL", "PHONE", "ADDRESS", "NATIONAL_ID", "ACCOUNT_ID", "CASE_NUMBER", "COMPANY_ID", "MRN", "SECRET"}
)
WORKFLOWS = (
    "support",
    "billing",
    "hr",
    "clinical_appointment",
    "legal_intake",
    "internal_it",
    "code_log_debugging",
    "travel",
)


def normalize(value):
    return "".join(c for c in unicodedata.normalize("NFKC", value).casefold() if c.isalnum())


def heldout_rows():
    for split in ("test", "dev"):
        with (OUTPUT / f"{split}.jsonl").open() as stream:
            for line in stream:
                yield json.loads(line)


def identity_values(rows):
    values = defaultdict(set)
    for row in rows:
        for span in row["spans"]:
            if span["label"] in IDENTITY_LABELS:
                value = span.get("text")
                if value is None:
                    value = row["text"][span["start"] : span["end"]]
                values[span["label"]].add(normalize(value))
    return values


def make_pools(prose):
    """New names and rejection-sampled identifier pools, explicitly excluding heldout surfaces.

    Dates and conditions can naturally recur and are not global subject identity keys.
    Names have three components, from independently authored TRAIN-only lexical pools.
    """
    excluded = identity_values(heldout_rows())
    used = defaultdict(set)
    pools = {}
    for language in LANGUAGES:
        rng = random.Random(SEED + 100000 * LANGUAGES.index(language))
        first, middle, last = [x.split() for x in prose[language]["names"]]
        people = []
        for index in range(POOL_SIZE):
            key = f"r127{language}{index:04d}"
            name = f"{first[index % 8]} {middle[index // 8 % 8]} {last[index // 64]}"
            for attempt in range(10000):
                fields = base.person_values(language, rng, key)
                fields.update(
                    name=name,
                    alias=f"{name.split()[0]} {name.split()[1]}",
                    email=f"contact.{key}@example.invalid",
                    secret=f"opaque__{rng.getrandbits(96):024x}",
                )
                if language == "it":
                    from europriv_bench.national_id import _cf_control_letter

                    # Rebind the name-coded portion while retaining the decoded birth date.
                    prefix = _consonant_code(last[index // 64], is_surname=True)
                    prefix += _consonant_code(" ".join(name.split()[:2]), is_surname=False)
                    first15 = prefix + fields["national"][6:15]
                    fields["national"] = first15 + _cf_control_letter(first15)
                values = [
                    (label, normalize(fields[k]))
                    for k, label in zip(base.KEYS, base.LABELS)
                    if label in IDENTITY_LABELS
                ]
                if all(value not in excluded[label] and value not in used[label] for label, value in values):
                    break
            else:
                raise ValueError(f"Cannot construct disjoint pool: {language}/{index}")
            for label, value in values:
                used[label].add(value)
            fields["obfuscated"] = fields["email"].replace("@", " [at] ")
            compact = fields["iban"].replace(" ", "")
            fields["split_iban"] = compact[:12] + "\n" + compact[12:]
            fields["subject_id"] = f"gateway-v1/train-pool/{language}/{index:04d}"
            people.append(fields)
        pools[language] = people
    return pools


def negative_material(workflow, index, length):
    """Task-bearing utility data: numeric references are public product/config values."""
    rng = random.Random(SEED * 10000 + index)
    if workflow == 6:
        # A boundary classification bug, independent of both heldout retry/idempotency families.
        code = """def histogram(samples, edges):
    counts = [0] * (len(edges) - 1)
    for value in samples:
        for i, (left, right) in enumerate(zip(edges, edges[1:])):
            if left <= value <= right:
                counts[i] += 1
    return counts
"""
        edges = sorted(rng.sample(range(-40, 61), 6))
        samples = [rng.choice(edges) for _ in range(6)]
        if length == "short":
            return f"edges={edges}; samples={samples}; rule=[left,right)"
        code += f"\nedges = {edges}\nsamples = {samples}\nprint(histogram(samples, edges))\n"
        if length == "long":
            code += """
def reference(samples, edges):
    return [sum(left <= value < right for value in samples)
            for left, right in zip(edges, edges[1:])]

def test_total():
    inside = [x for x in samples if edges[0] <= x < edges[-1]]
    assert sum(histogram(samples, edges)) == len(inside)

def test_upper_edge():
    assert histogram([edges[-1]], edges) == [0] * (len(edges) - 1)

def test_internal_edge():
    point = edges[2]
    expected = [0] * (len(edges) - 1)
    expected[2] = 1
    assert histogram([point], edges) == expected

def test_empty():
    assert histogram([], edges) == [0] * (len(edges) - 1)

for test in [test_total, test_upper_edge, test_internal_edge, test_empty]:
    try:
        test()
    except AssertionError:
        print(test.__name__, 'FAIL')
    else:
        print(test.__name__, 'OK')

# Additional boundary cases for comparing both algorithms:
"""
            for _ in range(8):
                values = rng.sample(range(-50, 71), 5)
                code += f"print(histogram({values}, edges), reference({values}, edges))\n"
        return "```python\n" + code + "```"
    records = [
        {"product": f"W-{index:05d}", "months": 12 + index % 25, "labour": 6 + index % 13},
        {"principal_eur": 400 + index, "months": 3 + index % 18, "interest_percent": index % 7},
        {
            "grade": f"G{index % 9}",
            "weekly_hours": 20 + index % 21,
            "cycle_weeks": 1 + index % 6,
            "shift_start_minute": 300 + index // 8,
        },
        {"service": f"D{index % 19}", "review_hours": 12 + index % 72, "forms_required": 1 + index % 5},
        {"public_reference": "Directive 2011/83/EU", "adopted": "2011-10-25", "exercise_words": 40 + index},
        {"module": f"archive/segment-{index}", "retention_days": 30 + index % 336, "purge_mode": "scheduled"},
        {},
        {"deck": 1 + index % 12, "ramp_width_cm": 90 + index % 111, "turning_area_cm": 150 + index % 51},
    ]
    return json.dumps(records[workflow], ensure_ascii=False)


def attachment(fields, index, length):
    """Distinct invoice-allocation task, not heldout receipt/merchant comparisons."""
    rng = random.Random(12700000 + index)
    size = rng.randint(18, 24) if length == "long" else 3
    lines = ["line;contact;due_eur;paid_eur;instalment_eur;priority"]
    for k in range(size):
        due = rng.randint(12000, 150000)
        paid = rng.randint(0, due // 2)
        instalment = rng.randint(1000, min(20000, due - paid))
        money = lambda cents: f"{cents // 100}.{cents % 100:02}"  # noqa: E731
        lines.append(
            f"{k + 1};[[{k % len(fields)}.name]];{money(due)};{money(paid)};{money(instalment)};{rng.randint(1, 5)}"
        )
    return "```csv\n" + "\n".join(lines) + "\n```"


@lru_cache(maxsize=1)
def single_subject_slots():
    """No replacement within a family for single-subject prompts (avoids exact repeats)."""
    counters = defaultdict(int)
    slots = {}
    for index, (mix, length) in enumerate(allocation(5000, "train")):
        if mix == "small" and (length == "short" or index // 8 % 2 == 0):
            workflow = index % 8
            slots[index] = counters[workflow]
            counters[workflow] += 1
    assert max(counters.values()) <= POOL_SIZE
    return slots


def make_draft(language, index, mix, length, tokenizer, prose, pools):
    workflow, slot = index % 8, index // 8
    family = f"gateway-v1/family-{workflow * 3:03d}"
    row_id = f"gateway-v1/train/{language}/{workflow:02d}-{slot:03d}"
    seed = SEED + LANGUAGES.index(language) * 100000 + index
    rng = random.Random(seed)
    n = {
        "negative": 0,
        "small": 1 if length == "short" else 1 + slot % 2,
        "medium": 3 if length == "short" else 3 + slot % 3,
        "dense": 6,
    }[mix]
    fields = rng.sample(pools[language], n)
    if n == 1:
        fields = [pools[language][single_subject_slots()[index]]]
    p = prose[language]
    labels = dict(zip(base.KEYS, p["labels"]))
    features = {"punctuation"}
    secondary = []
    template = p["asks" if n else "negative"][workflow]
    if length != "short":
        template += "\n\n" + p["context"]
    if not n:
        template += "\n\n" + negative_material(workflow, index, length)
        features.add("json_code")
        if workflow == 4:
            features.update(("public_date", "public_statute"))
            template += "\nEuropean Union"
            features.add("public_org")
    else:
        keys = {
            0: ["email", "address", "phone"],
            1: ["case", "iban", "company"],
            2: ["national", "dob", "email"],
            3: ["mrn", "dob", "health"],
            4: ["case", "address"],
            5: ["email"],
            6: ["email"],
            7: ["case", "phone"],
        }[workflow]
        if length == "short":
            keys = [] if n > 2 else ["mrn" if workflow == 3 else "case" if workflow in (1, 4, 7) else "email"]
        elif n > 2:
            keys = [keys[0]]
        for j in range(n):
            template += f"\n\n[[{j}.name]]"
            for key in keys:
                actual = "obfuscated" if key == "email" and workflow == 0 and slot % 2 else key
                template += f"\n{labels[key]}: [[{j}.{actual}]]"
                features.add(KEY_FEATURE[key])
                if actual == "obfuscated":
                    features.add("obfuscated_identifier")
        if workflow == 1 and length != "short":
            template += "\n\n" + attachment(fields, index, length)
            features.update(("repeated_entity",))
            if n > 2:
                template += f"\n{labels['iban']}: [[0.iban]]"
                features.add("bank_account")
            if slot % 2:
                template += f"\n{labels['card']}: [[0.card]]"
                features.add("card")
            else:
                template += f"\n{labels['iban']} (OCR): [[0.split_iban]]"
                features.add("split_identifier")
        if workflow == 4 and length != "short":
            template += "\n\n> [[0.name]]\n> [[0.alias]]"
            features.update(("quoted_history", "aliases", "repeated_entity"))
        if workflow == 5 and length != "short":
            template += '\n```json\n{"operation":"revoke","principal":"[[0.email]]",'
            template += '"retain_shared_files":true}\n```'
            features.update(("json_code", "repeated_entity"))
            if n == 1:
                template += (
                    "\nEchipa de arhivare cere o explicație în română a câmpului retain_shared_files."
                    if language == "en"
                    else "\nThe archive team needs an English explanation of retain_shared_files for its handover."
                )
                secondary = ["ro" if language == "en" else "en"]
                features.add("code_switch")
        if workflow == 6 and length != "short":
            template += '\n```json\n{"logger":"diagnostic","credential":"[[0.secret]]",'
            template += '"contact":"[[0.email]]","sink":"disk"}\n```'
            features.update(("secret", "json_code", "repeated_entity"))
    # Task parameters make each negative instance meaningful and distinct, rather than ID padding.
    if n and length == "short":
        template += f"\n{p['closing']}"
    message, spans = base.splice(template, fields, 0, row_id + "/subject")
    messages = [message]
    tokens = base.count_tokens(messages, tokenizer)
    lo, hi = {"short": (32, 128), "medium": (129, 512), "long": (513, 2048)}[length]
    if tokens < lo:
        template += "\n\n" + p["closing"]
        message, spans = base.splice(template, fields, 0, row_id + "/subject")
        messages = [message]
        tokens = base.count_tokens(messages, tokenizer)
    if tokens < lo and length == "medium":
        # A structured output contract adds usable instructions, once, never repeated padding.
        template += '\n```json\n{"output":{"facts":[],"unresolved_questions":[],"next_action":null},'
        template += '"rules":{"infer_missing_values":false,"preserve_order":true,"automatic_send":false}}\n```'
        features.add("json_code")
        message, spans = base.splice(template, fields, 0, row_id + "/subject")
        messages = [message]
        tokens = base.count_tokens(messages, tokenizer)
    if workflow == 6 and n and length != "short":
        tool, tool_spans = base.splice(
            '{"scanner":"log_preview","credential":"[[0.secret]]","exposed":true}',
            fields,
            1,
            row_id + "/subject",
        )
        tool["role"] = "tool"
        messages.append(tool)
        spans.extend(tool_spans)
        features.add("tool_payload")
        tokens = base.count_tokens(messages, tokenizer)
    if not lo <= tokens <= hi:
        raise ValueError(f"{row_id}: {mix}/{length}: {tokens} outside {lo}..{hi}")
    if any(ord(c) > 127 for message in messages for part in message["parts"] for c in part["text"]):
        features.add("unicode")
    # One pool identity denotes one fictional subject across all its document appearances.
    for span in spans:
        j = int(span["subject_id"].rsplit("/", 1)[1])
        span["subject_id"] = fields[j]["subject_id"]
        span["entity_id"] = fields[j]["subject_id"] + "/" + span["entity_id"].rsplit("/", 1)[1]
    return dict(
        schema_version="gateway-traffic-v1",
        config_status="dev",
        taxonomy_version=base.TAXONOMY_VERSION,
        id=row_id,
        language=language,
        secondary_languages=secondary,
        source_id="originals",
        stratum="original-synthetic",
        scenario_id=f"{family}/train-scenario-{slot:03d}",
        family_id=family,
        source_document_id=row_id,
        translation_group_id=f"{family}/train-adaptation-{slot:03d}",
        subject_ids=[f["subject_id"] for f in fields],
        split="train",
        messages=messages,
        spans=spans,
        features=sorted(features),
        dense_document=mix == "dense",
        token_count=tokens,
        tokenizer_id=base.TOKENIZER_ID,
        tokenizer_revision=base.TOKENIZER_REVISION,
        truncated=False,
        authoring_seed=seed,
        intended_mix=mix,
        intended_length=length,
    )


def attach_provenance(draft, artifact, revision, sha):
    row = base.attach_provenance(draft, artifact, revision, sha).model_dump()
    row["provenance"].update(
        source_split="original-authored-train-v1",
        generator_version="res127-train-v1",
        session="RES-127/2026-10-11",
        prompt_sha256=file_digest(PROSE),
        identity_provenance="Independent train prose and 512 new subjects per language; "
        "all identifying pool values exclude normalized dev/test surfaces. "
        "Pool IDs persist across appearances. Language adaptations share train families. "
        "Dates/conditions may recur. Independent human semantic review pending.",
    )
    row["provenance"]["review"]["guide_sha256"] = file_digest(GUIDE)
    return Conversation.model_validate(row)


def training_row(row):
    """RES-100 load_rows / encoder train.py contract. Offsets include part separators."""
    if isinstance(row, Conversation):
        row = row.model_dump()
    text, spans = "", []
    for m, message in enumerate(row["messages"]):
        for p, part in enumerate(message["parts"]):
            if text:
                text += "\n\n"
            offset = len(text)
            text += part["text"]
            spans.extend(
                {"start": s["start"] + offset, "end": s["end"] + offset, "label": s["label"]}
                for s in row["spans"]
                if s["message"] == m and s["part"] == p
            )
    return dict(text=text, spans=sorted(spans, key=lambda s: s["start"]), language=row["language"], domain="gateway")
