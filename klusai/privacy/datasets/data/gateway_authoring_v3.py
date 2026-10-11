"""Offline, task-grounded third revision of gateway-traffic-v1 authoring.

Original v1 sources remain immutable. IDs and reserved split families are retained;
new source documents live under the manifest's originals/ artifact prefix.
"""

from __future__ import annotations

import csv
import io
import random

from . import gateway_authoring as v1
from . import gateway_authoring_v2 as v2
from .gateway_traffic import LANGUAGES, Conversation, file_digest

ROOT = v1.ROOT
PROSE = ROOT / "docs/gateway-authoring/prose-v3.json"
GUIDE = ROOT / "docs/gateway-authoring/annotation-guide-v3.md"
ARTIFACTS = ROOT / "artifacts/gateway-traffic-v1/originals/v3"
VERSION = "res124-tranche3-v3"
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
# Reuse the frozen per-ID allocation, including subject counts and length strata.
allocation = v2.allocation


def code_repro(split, index):
    """A small executable retry failure with meaningful tests, not fixture repetition."""
    rng = random.Random(91000 + index)
    events = [dict(event_id=k, sku=str(73000000 + index + k), qty=rng.randint(1, 9)) for k in range(3)]
    if split == "test":
        code = """from copy import deepcopy

class Inventory:
    def __init__(self):
        self.stock = {}
        self.history = []

    def apply(self, events):
        for event in events:
            sku = event['sku']
            self.stock[sku] = self.stock.get(sku, 0) + event['qty']
            self.history.append(dict(event))
        return dict(self.stock)

    def snapshot(self):
        return deepcopy((self.stock, self.history))

    def restore(self, saved):
        self.stock, self.history = deepcopy(saved)


def deliver(inventory, events, lose_reply=False):
    result = inventory.apply(events)
    if lose_reply:
        raise TimeoutError('reply lost after update')
    return result


def check_replay(events):
    inventory = Inventory()
    expected = inventory.apply(events)
    received = inventory.apply(events)
    assert received == expected, (expected, received)


def check_lost_reply(events):
    inventory = Inventory()
    try:
        deliver(inventory, events, lose_reply=True)
    except TimeoutError:
        before_retry = inventory.snapshot()
    received = deliver(inventory, events)
    assert received == before_retry[0], (before_retry[0], received)


def check_new_event_same_sku(events):
    inventory = Inventory()
    first = events[0]
    inventory.apply([first])
    another = dict(first, event_id=99, qty=1)
    received = inventory.apply([another])
    assert received[first['sku']] == first['qty'] + 1


def check_restart(events):
    inventory = Inventory()
    expected = inventory.apply(events)
    saved = inventory.snapshot()
    replacement = Inventory()
    replacement.restore(saved)
    received = replacement.apply(events)
    assert received == expected, (expected, received)
"""
        tests = ["check_replay", "check_lost_reply", "check_new_event_same_sku", "check_restart"]
    else:
        code = """import sqlite3


def create_store():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE stock (sku TEXT PRIMARY KEY, qty INTEGER)')
    db.execute('CREATE TABLE deliveries (event_id INTEGER, sku TEXT, qty INTEGER)')
    return db


def consume(db, event, ack):
    with db:
        db.execute(
            'INSERT INTO stock VALUES (?, ?) ON CONFLICT(sku) '
            'DO UPDATE SET qty = qty + excluded.qty',
            (event['sku'], event['qty']),
        )
        db.execute('INSERT INTO deliveries VALUES (?, ?, ?)',
                   (event['event_id'], event['sku'], event['qty']))
    ack(event)


def snapshot(db):
    return db.execute('SELECT sku, qty FROM stock ORDER BY sku').fetchall()


def accepted(event):
    pass


def lost(event):
    raise ConnectionError('connection lost before ack')


def check_replay(events):
    db = create_store()
    for event in events:
        consume(db, event, accepted)
    expected = snapshot(db)
    for event in events:
        consume(db, event, accepted)
    assert snapshot(db) == expected, (expected, snapshot(db))


def check_lost_ack(events):
    db = create_store()
    event = events[0]
    try:
        consume(db, event, lost)
    except ConnectionError:
        expected = snapshot(db)
    consume(db, event, accepted)
    assert snapshot(db) == expected, (expected, snapshot(db))


def check_new_event_same_sku(events):
    db = create_store()
    event = events[0]
    consume(db, event, accepted)
    consume(db, dict(event, event_id=99, qty=1), accepted)
    assert snapshot(db) == [(event['sku'], event['qty'] + 1)]
"""
        tests = ["check_replay", "check_lost_ack", "check_new_event_same_sku"]
    return (
        "```python\n"
        + code
        + "\nevents = "
        + repr(events)
        + "\n\nfor check in ["
        + ", ".join(tests)
        + "]:\n"
        + "    try:\n        check(events)\n    except AssertionError as exc:\n"
        + "        print(check.__name__, 'FAIL', exc)\n"
        + "    else:\n        print(check.__name__, 'OK')\n```"
    )


def public_material(p, workflow, split, index, length):
    # User constraints vary for a reason; editions no longer carry meaningless IDs.
    limit = p["revision3"]["word_limit"].format(words=45 + index // 8)
    if workflow == 4:
        body = p["extra"]["law"] + "\n2018-05-25 · EUR-Lex · CELEX: 32016R0679\n" + limit
        if length == "medium":
            body += "\n\n" + p["revision3"]["legal_context"]
        return body
    if workflow == 6 and length == "long":
        return code_repro(split, index)
    body = v2.public_material(p, workflow, split, index, length)
    tag = 73000000 + index if split == "test" else 84000000 + index
    if workflow == 5:
        body = body.replace(f"policy_version: {tag}\n", "") + "\n" + limit
    if workflow == 0 and split == "dev":
        body = body.replace(f"\nv{tag}", "") + "\n" + limit
    if workflow == 3:
        body += "\n" + limit
    # Four fare types are sufficient; additional rows repeated exactly the same rules.
    if workflow == 7 and split == "dev" and length == "medium":
        body = "\n".join(body.splitlines()[:5]) + "\n\n" + p["revision3"]["fare_context"]
    return body


def expense_export(p, fields, split, index, length):
    """Variable receipt lengths, heterogeneous cents, real comparison columns and one replay."""
    rng = random.Random(812403 + index + (10000 if split == "dev" else 0))
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=";", lineterminator="\n")
    header = [s.strip() for s in p["extra"]["expense_header"].split(";")]
    header.extend(p["revision3"]["merchant_header"].split(" / "))
    writer.writerow(header)
    rows = []
    # Long receipts carry 18--25 substantive entries, not 36 cyclic fixture rows.
    total = rng.randint(18, 25) if length == "long" else max(len(fields), rng.randint(3, 5))
    for k in range(total):
        owner = k % len(fields)
        product = rng.choice(p["extra"]["expenses"])
        cents = rng.randint(350, 12999)
        merchant, bank = rng.choice(
            [
                ("PAPER SHOP", "PAPER-SHOP EU"),
                ("DESK STORE", "DESK STORE"),
                ("OFFICE DIRECT", "OFFICE DIRECT WEB"),
                ("TECH CORNER", "TECH CORNER"),
            ]
        )
        row = [
            f"[[{owner}.name]]",
            f"[[{owner}.case]]",
            k + 1,
            product,
            rng.choice([1, 1, 1, 2, 3]),
            f"{cents // 100},{cents % 100:02}",
            "EUR",
            p["notes_t" if split == "test" else "notes_d"][1].split("|")[k % 4],
            merchant,
            bank,
        ]
        rows.append(row)
    if split == "test":
        rows.insert(rng.randint(1, len(rows)), rows[0].copy())
    writer.writerows(rows)
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
        if workflow == 5 and length == "short":
            template = p["revision3"]["it_short"]
        if workflow == 1 and length == "short":
            template = p["revision3"]["expense_ask"]
        if workflow == 2 and length != "short" and n <= 2:
            template = p["revision3"]["payroll_ask"]
        if length != "short" and not (workflow == 1 and length == "medium" and n > 2):
            context = p["context_" + side][workflow]
            if workflow == 2:
                context = p["revision3"]["payroll_context"] if n <= 2 else p["revision3"]["case_context"]
            elif workflow == 5:
                context = p["revision3"]["case_context"]
            template += "\n\n" + context
        notes = p["notes_" + side][workflow].split("|")
        if workflow == 2 and length != "short" and n <= 2:
            notes = p["revision3"]["payroll_notes"].split("|")
        for j in range(n):
            note = notes[(slot + j) % len(notes)]
            if workflow == 1:
                note = ""  # Receipt rows supply the evidence; no unsupported preclassified status.
            template += f"\n\n[[{j}.name]]" + (f" — {note}" if note else "")
            keys = []
            if length == "short":
                if n == 1:
                    keys = ["email"] if workflow in (0, 2, 5, 7) else (["mrn"] if workflow == 3 else ["case"])
                if workflow == 5:
                    keys = ["email"]
                if workflow in (3, 7):
                    keys = ["mrn"] if workflow == 3 else ["case"]
            else:
                keys = {
                    0: ["email", "address"],
                    1: ["case", "iban"],
                    2: ["email", "national", "dob"],
                    3: ["mrn", "dob", "health"],
                    4: ["case", "address"],
                    5: ["email"],
                    6: ["email"],
                    7: ["case", "phone"],
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
                        7: ["case"],
                    }[workflow]
            for key in keys:
                field = "obfuscated" if key == "email" and workflow == 0 and slot % 2 else key
                template += f"\n{labels[key]}: [[{j}.{field}]]"
                features.add(KEY_FEATURE[key])
                if field == "obfuscated":
                    features.add("obfuscated_identifier")
            if workflow == 0 and length != "short" and n <= 2 and j == 0:
                template += f"\n{labels['phone']}: [[0.phone]]"
                features.add("phone")
            if workflow == 1 and length == "short":
                cents = random.Random(seed + j + 8124).randint(350, 12999)
                template += f"\n{p['extra']['expenses'][(slot + j) % 6]} · {cents // 100},{cents % 100:02} EUR"
                if split == "dev":
                    template += " · PAPER SHOP / PAPER-SHOP"
            if workflow == 1 and length != "short" and j == 0:
                if n > 2:
                    template += f"\n{labels['iban']}: [[0.iban]]"
                    features.add("bank_account")
                if n <= 2:
                    template += f"\n{labels['company']}: [[0.company]]"
                    features.add("company_id")
                    if slot % 2:
                        template += "\n" + p["revision3"]["card_context"]
                        template += f"\n{labels['card']}: [[0.card]]"
                        features.add("card")
                    else:
                        template += "\n" + p["extra"]["ocr"] + "\n[[0.split_iban]]"
                        features.update(("split_identifier", "repeated_entity"))
        if workflow == 1 and length != "short":
            template += "\n\n" + expense_export(p, fields, split, index, length)
            features.add("repeated_entity")
        if workflow == 4 and length != "short" and n == 1:
            # The alias is a signature in an actual message, not a self-addressed greeting.
            template += "\n\n" + p["revision3"]["quote"]
            features.update(("quoted_history", "aliases", "repeated_entity"))
        if workflow == 5 and length != "short":
            if n == 1:
                template += "\n\n" + p["revision3"]["mixed_" + split]
                features.update(("code_switch", "quoted_history"))
                secondary = ["ro" if language == "en" else "en"]
            for j in range(1):
                template += (
                    '\n```json\n{"tool":"device_check","account":"[['
                    + str(j)
                    + '.email]]","status":"'
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
                    else "\n```python\nTOKEN = '[[0.secret]]'\nqueue = QueueClient(token=TOKEN)\ndef handle(event):\n"
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
        if not n:
            detail = p["revision3"]["code_context"] if workflow in (5, 6) else p["revision3"]["public_context"]
        else:
            detail = p["revision3"]["case_context"] if length == "medium" else p["extra"]["reply_" + split]
        template += "\n\n" + detail
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
        source_split="original-authored-tranche3-git-blob", generator_version=VERSION, prompt_sha256=file_digest(PROSE)
    )
    data["provenance"]["review"]["guide_sha256"] = file_digest(GUIDE)
    return Conversation.model_validate(data)
