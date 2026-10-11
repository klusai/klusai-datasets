"""Offline, task-grounded second revision of gateway-traffic-v1 authoring.

Original v1 sources remain immutable. IDs and reserved split families are retained;
new source documents live under the manifest's originals/ artifact prefix.
"""

from __future__ import annotations

import csv
import io
import json
import random

from . import gateway_authoring as v1
from .gateway_traffic import LANGUAGES, Conversation, file_digest

ROOT = v1.ROOT
PROSE = ROOT / "docs/gateway-authoring/prose-v2.json"
GUIDE = ROOT / "docs/gateway-authoring/annotation-guide-v2.md"
ARTIFACTS = ROOT / "artifacts/gateway-traffic-v1/originals/v2"
VERSION = "res124-tranche2-v2"
KEY_FEATURE = dict(
    zip(
        v1.KEYS[1:],
        (
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
        ),
    )
)
# Per 20 documents: exact 20/40/30/10 subjects and 50/35/15 lengths.
CELLS = {
    ("negative", "short"): 2,
    ("negative", "medium"): 1,
    ("negative", "long"): 1,
    ("small", "short"): 5,
    ("small", "medium"): 2,
    ("small", "long"): 1,
    ("medium", "short"): 3,
    ("medium", "medium"): 3,
    ("dense", "medium"): 1,
    ("dense", "long"): 1,
}


def allocation(n, split):
    if n % 40:
        raise ValueError("full balanced workflow allocation requires a multiple of 40")
    rng = random.Random(12402 + (10000 if split == "dev" else 0))
    result = [None] * n
    # Rich attachments belong to expense reconciliation and executable repro cases.
    for workflow, cells in ((1, [("small", "long"), ("dense", "long")]), (6, [("negative", "long")])):
        positions = list(range(workflow, n, 8))
        rng.shuffle(positions)
        for cell in cells:
            for _ in range(n // 20):
                result[positions.pop()] = cell
    rest = [cell for cell, count in CELLS.items() if cell[1] != "long" for _ in range(count * n // 20)]
    rng.shuffle(rest)
    for i, value in enumerate(result):
        if value is None:
            result[i] = rest.pop()
    return result


def public_material(p, workflow, split, index, length):
    """Actual input to the negative task, with public identifiers in their normal roles."""
    tag = 73000000 + index if split == "test" else 84000000 + index
    if workflow == 2:
        # Public biographies: presentation requirements vary, not fictional private people.
        x = p["extra"]["lesson"]
        return x.format(age=10 + index % 9, minutes=20 + index % 37, questions=3 + index % 7) + (
            "\n" + p["extra"]["lesson_outline"] if length == "medium" else ""
        )
    if workflow == 4:
        appendix = "\n" + "\n".join(p["extra"]["legal_toc"]) if length == "medium" else ""
        return (
            f"{p['extra']['law']}\n2018-05-25 · EUR-Lex · CELEX: 32016R0679\n{p['extra']['edition']}: {tag}" + appendix
        )
    if workflow == 5:
        settings = (
            "inherit: false\nmobile: read\ndesktop: read\nauth: required"
            if split == "test"
            else "enrolment: required\nassignment: manual\nallow_reuse: false\ncleanup_old_device: false"
        )
        if length == "medium":
            settings += "\nclients:\n  desktop:\n    auth: sso\n    cache_minutes: 60\n    refresh_on_expiry: true\n  mobile:\n    auth: sso\n    cache_minutes: 0\n    refresh_on_expiry: false\nlogging:\n  level: debug\n  include_headers: false\n  redact_secrets: true"
        return f"```yaml\npolicy_version: {tag}\n{settings}\nretry_seconds: {10 + index % 41}\n```"
    if workflow == 3:
        return p["extra"]["booking_" + split].format(minutes=10 + index % 37, version=tag) + (
            "\n```json\n"
            + json.dumps(
                {
                    "booking": {"hold_minutes": 10 + index % 37, "confirmation": "email", "extend_on_refresh": False},
                    "reminders": {"email": True, "portal": True, "cancel_booking_on_disable": False},
                },
                indent=2,
            )
            + "\n```"
            if length == "medium"
            else ""
        )
    if workflow == 6:
        size = 28 if length == "long" else (7 if length == "medium" else 2)
        items = [{"sku": str(tag + k), "qty": 1 + k % 4, "version": 1 + k // 4} for k in range(size)]
        if split == "test":
            code = "def apply(stock, rows):\n    for row in rows:\n        key = row['sku']\n        stock[key] = stock.get(key, 0) + row['qty']\n    return stock\n"
            tail = "\nstock = {}\napply(stock, rows)\nfirst = dict(stock)\napply(stock, rows)\nassert stock == first  # fails"
        else:
            code = "def consume(catalogue, event):\n    sku = event['sku']\n    catalogue[sku] = catalogue.get(sku, 0) + event['qty']\n"
            tail = "\ncatalogue = {}\nfor event in rows:\n    consume(catalogue, event)\nexpected = dict(catalogue)\nfor event in rows:\n    consume(catalogue, event)\nassert catalogue == expected  # fails"
        # Short requests include the failing line and two inputs, medium/long the full executable repro.
        if length == "short":
            return f"```python\nstock[sku] = stock.get(sku, 0) + qty\n```\n{items[0]}"
        return "```python\n" + code + "\nrows = " + json.dumps(items, indent=2) + tail + "\n```"
    if workflow == 0 and split == "dev":
        body = p["extra"]["return_steps"] + f"\nv{tag}"
        if length == "medium":
            config = {
                "return_flow": ["choose_item", "select_resolution", "download_label", "book_collection"],
                "label": {"format": "pdf", "creates_pickup": False},
                "collection": {"requires_booking": True, "confirmation": "email", "window_hours": 4},
                "exchange": {"check_stock_first": True, "fallback": "refund"},
            }
            body += "\n```json\n" + json.dumps(config, indent=2) + "\n```"
        return body
    count = 2 if length == "short" else 12
    names = p["extra"]["products"]
    if workflow == 0:
        return "SKU; model; compatible_with\n" + "\n".join(
            f"{tag + k}; {names[k % 4]}; M-{100 + (index + k) % 99}" for k in range(count)
        )
    if workflow == 7:
        names = p["extra"]["baggage" if split == "test" else "fares"]
        if split == "test":
            header = "model; type; cm; kg"
            rows = [f"{tag + k}; {names[k % 4]}; {45 + k % 4 * 5}x35x20; {7 + k % 4 * 2}" for k in range(count)]
        else:
            header = "code; type; change_train; change_passenger; fee_EUR"
            rows = [f"{tag + k}; {names[k % 4]}; {k % 4 != 2}; {k % 4 == 0}; {k % 4 * 5}" for k in range(count)]
        return header + "\n" + "\n".join(rows)
    header = p["extra"]["catalog_header"]
    return (
        header
        + "\n"
        + "\n".join(
            f"{tag + k}; {names[(index + k) % len(names)]}; {1 + k % 4}; {9 + (index + k) % 70},90"
            for k in range(count)
        )
    )


def expense_export(p, fields, split, index):
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=";", lineterminator="\n")
    writer.writerow([s.strip() for s in p["extra"]["expense_header"].split(";")])
    products = p["extra"]["expenses"]
    for k in range(36):
        owner = min(k // (36 // len(fields)), len(fields) - 1)
        line = k % (36 // len(fields)) + 1
        if line == 3 and owner == 0:
            line = 2
        product = products[(line + index + owner * 3) % len(products)]
        amount = 10 + (line * 13 + index + owner * 17) % 120
        status = p["notes_t" if split == "test" else "notes_d"][1].split("|")[(line + owner) % 4]
        writer.writerow(
            [
                f"[[{owner}.name]]",
                f"[[{owner}.case]]",
                line,
                product,
                1 + (line + owner) % 3,
                f"{amount},90",
                "EUR",
                status,
            ]
        )
    return "```csv\n" + stream.getvalue() + "```"


def make_draft(language, split, index, mix, length, tokenizer, prose):
    workflow, slot = index % 8, index // 8
    family = f"gateway-v1/family-{workflow * 3 + (2 if split == 'test' else 1):03d}"
    row_id = f"gateway-v1/{split}/{language}/{workflow:02d}-{slot:03d}"
    seed = 124 + LANGUAGES.index(language) * 100000 + (10000 if split == "dev" else 0) + index
    rng = random.Random(seed)
    n = {
        "negative": 0,
        "small": 1 if length == "short" else 1 + slot % 2,
        "medium": 3 if length == "short" else 3 + slot % 3,
        "dense": 6,
    }[mix]
    fields = []
    for person in range(n):
        key = f"{'t' if split == 'test' else 'd'}{LANGUAGES.index(language)}{index:04d}{person}"
        while True:
            values = v1.person_values(language, rng, key)
            if values["name"] not in {v["name"] for v in fields}:
                break
        values["health"] = prose[language]["extra"]["conditions"][(slot + person) % 5]
        values["secret"] = values["secret"].replace("synthetic_only_", "opaque__")
        values["obfuscated"] = values["email"].replace("@", " [at] ")
        compact = values["iban"].replace(" ", "")
        groups = [compact[j : j + 4] for j in range(0, len(compact), 4)]
        values["split_iban"] = " ".join(groups[:4]) + "\n" + " ".join(groups[4:])
        fields.append(values)
    p = prose[language]
    side = "t" if split == "test" else "d"
    labels = dict(zip(v1.KEYS, p["extra"]["labels"]))
    if language == "fr":
        labels["dob"] = "Naissance (MM/AA)"
    elif language == "it":
        labels["dob"] = "Nascita (GG/MM/AA)"
    features = {"punctuation"}
    secondary = []
    if not n:
        template = p["neg_" + side][workflow] + "\n\n" + public_material(p, workflow, split, index, length)
        if workflow == 4:
            features.update(("public_date", "public_org", "public_statute"))
        if workflow in (5, 6) or (length == "medium" and (workflow == 3 or (workflow == 0 and split == "dev"))):
            features.add("json_code")
    else:
        ask = p[("batch_" if n > 1 else "asks_") + side][workflow]
        variants = ask.split("||")
        template = variants[slot % len(variants)]
        if length != "short":
            template += "\n\n" + p["context_" + side][workflow]
        notes = p["notes_" + side][workflow].split("|")
        for j in range(n):
            template += f"\n\n[[{j}.name]] — {notes[(slot + j) % len(notes)]}"
            keys = []
            if length == "short":
                if n == 1:
                    keys = ["email"] if workflow in (0, 2, 5, 7) else (["mrn"] if workflow == 3 else ["case"])
                if workflow in (3, 7):
                    keys = ["mrn"] if workflow == 3 else ["case"]
            else:
                keys = {
                    0: ["email", "phone", "address"],
                    1: ["case", "iban"],
                    2: ["email", "national", "dob"],
                    3: ["mrn", "national", "dob", "health"],
                    4: ["case", "address"],
                    5: ["email"],
                    6: ["email"],
                    7: ["email", "phone"],
                }[workflow]
                if n > 2:
                    keys = {
                        0: ["email"],
                        1: ["case"],
                        2: ["email"],
                        3: ["mrn", "health"],
                        4: ["case"],
                        5: ["email"],
                        6: ["email"],
                        7: ["phone"],
                    }[workflow]
            for key in keys:
                field = "obfuscated" if key == "email" and workflow == 0 and slot % 2 else key
                template += f"\n{labels[key]}: [[{j}.{field}]]"
                features.add(KEY_FEATURE[key])
                if field == "obfuscated":
                    features.add("obfuscated_identifier")
            if workflow == 1 and length != "short" and j == 0:
                # Only the reimbursement contact's bank/company details accompany the expense export.
                if n > 2:
                    template += f"\n{labels['iban']}: [[0.iban]]"
                    features.add("bank_account")
                template += f"\n{labels['company']}: [[0.company]]"
                features.add("company_id")
                if slot % 2:
                    template += f"\n{labels['card']}: [[0.card]]"
                    features.add("card")
                else:
                    template += "\n" + p["extra"]["ocr"] + "\n[[0.split_iban]]"
                    features.update(("split_identifier", "repeated_entity"))
        if workflow == 1 and length == "long":
            template += "\n\n" + expense_export(p, fields, split, index)
            features.add("repeated_entity")
        if workflow in (0, 4) and length != "short" and n == 1:
            template += "\n\n> " + p["extra"]["greeting"] + "\n> " + notes[slot % 4]
            template += "\n\n" + p["extra"]["signature"]
            features.update(("quoted_history", "aliases", "repeated_entity"))
        if workflow == 5 and length != "short":
            template += "\n\n" + p["extra"]["mixed_" + split]
            features.update(("code_switch", "quoted_history"))
            secondary = ["ro" if language == "en" else "en"]
            template += (
                '\n```json\n{"tool":"device_check","account":"[[0.email]]","status":"'
                + ("access_denied" if split == "test" else "already_assigned")
                + '"}\n```'
            )
            features.update(("tool_payload", "json_code", "repeated_entity"))
        if workflow == 6:
            if length == "short":
                template += (
                    "\n`headers = {'Authorization': token}`"
                    if split == "test"
                    else "\n`db.execute('INSERT INTO events VALUES (?)', [event_id])`"
                )
            else:
                template += (
                    "\n```python\ntoken = '[[0.secret]]'\nheaders = {'Authorization': token}\n"
                    "response = client.post('/hook', headers=headers, json=event)\n```"
                    if split == "test"
                    else "\n```python\nTOKEN = '[[0.secret]]'\ndef handle(event):\n"
                    "    db.execute('INSERT INTO events(id) VALUES (?)', [event['id']])\n"
                    "    db.commit()\n    queue.ack(event)\n```"
                )
                features.add("secret")
            features.add("json_code")
    message, spans = v1.splice(template, fields, 0, row_id + "/subject")
    messages = [message]
    tokens = v1.count_tokens(messages, tokenizer)
    lo, hi = {"short": (32, 128), "medium": (129, 512), "long": (513, 2048)}[length]
    # A task-relevant follow-up is allowed once, never a repeated padding paragraph.
    if tokens < lo and length in {"short", "medium"}:
        template += "\n\n" + p["extra"]["reply_" + split]
        message, spans = v1.splice(template, fields, 0, row_id + "/subject")
        messages = [message]
        tokens = v1.count_tokens(messages, tokenizer)
    if not lo <= tokens <= hi:
        raise ValueError(f"{row_id}: {mix}/{length} {tokens} not in {lo}..{hi}")
    if any(ord(c) > 127 for c in template):
        features.add("unicode")
    return dict(
        schema_version="gateway-traffic-v1",
        config_status="dev",
        taxonomy_version=v1.TAXONOMY_VERSION,
        id=row_id,
        language=language,
        secondary_languages=secondary,
        source_id="originals",
        stratum="original-synthetic",
        scenario_id=f"{family}/scenario-{slot:03d}",
        family_id=family,
        source_document_id=row_id,
        translation_group_id=f"{family}/adaptation-{slot:03d}",
        subject_ids=[f"{row_id}/subject/{j}" for j in range(n)],
        split=split,
        messages=messages,
        spans=spans,
        features=sorted(features),
        dense_document=mix == "dense",
        token_count=tokens,
        tokenizer_id=v1.TOKENIZER_ID,
        tokenizer_revision=v1.TOKENIZER_REVISION,
        truncated=False,
        authoring_seed=seed,
        intended_mix=mix,
        intended_length=length,
    )


def attach_provenance(draft, artifact, revision, artifact_hash):
    data = v1.attach_provenance(draft, artifact, revision, artifact_hash).model_dump()
    data["provenance"].update(
        source_split="original-authored-tranche2-git-blob", generator_version=VERSION, prompt_sha256=file_digest(PROSE)
    )
    data["provenance"]["review"]["guide_sha256"] = file_digest(GUIDE)
    return Conversation.model_validate(data)
