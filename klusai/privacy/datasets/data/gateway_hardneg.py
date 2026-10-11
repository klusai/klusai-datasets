"""Original offline hard-negative TRAIN augmentation; synthetic contacts, never live PII."""

from __future__ import annotations

import json
import random
import re
from collections import defaultdict

from .gateway_train import OUTPUT, ROOT, base, heldout_rows, identity_values, normalize

PROSE = ROOT / "docs/gateway-authoring/prose-hardneg.json"
GUIDE = ROOT / "docs/gateway-authoring/hardneg.md"
MANIFEST = ROOT / "conf/gateway_hardneg_manifest.json"
RECEIPT = ROOT / "docs/gateway-authoring/hardneg-audit.json"
INPUT = OUTPUT / "originals/hardneg-v1"
KP = OUTPUT / "train-hardneg-kp.jsonl"
META = OUTPUT / "train-hardneg-metadata.jsonl"
SEED = 12715
COUNTS = {language: 3000 if language in {"pl", "de"} else 1500 for language in base.LANGUAGES}
POOL_SIZE = 64
KEYS = ("name", "email", "phone", "address")
LABELS = ("PERSON", "EMAIL", "PHONE", "ADDRESS")
FAMILIES = (
    "catalogue-facets",
    "packaging-layout",
    "museum-shop-index",
    "receipt-column-recovery",
    "stock-status-interface",
    "supplier-field-mapping",
    "workshop-kit-picking",
    "bookshop-window-planning",
)
CATEGORIES = ("product", "article_code", "merchant", "header", "status", "packaging", "historical_figure")


def parent_rows():
    with (OUTPUT / "train-kp.jsonl").open() as stream:
        for line in stream:
            yield json.loads(line)


def make_pools(prose):
    excluded = identity_values(heldout_rows())
    for label, values in identity_values(parent_rows()).items():
        excluded[label].update(values)
    used = defaultdict(set)
    pools = {}
    for language in base.LANGUAGES:
        rng = random.Random(SEED + 10000 * base.LANGUAGES.index(language))
        first, last = [s.split() for s in prose[language]["names"]]
        people = []
        for i in range(POOL_SIZE):
            surname = last[i // 8]
            if language == "pl" and first[i % 8].endswith("a"):
                surname = re.sub(r"(sk|ck)i$", r"\1a", surname)
            name = first[i % 8] + " " + surname
            if normalize(name) in excluded["PERSON"] | used["PERSON"]:
                raise ValueError("Author a new name pool; a proposed name overlaps existing subjects")
            for _ in range(10000):
                raw = base.person_values(language, rng, f"hn{language}{i:03d}")
                fields = dict(
                    name=name,
                    email=f"workshop.hn{language}{i:03d}@example.invalid",
                    phone=raw["phone"],
                    address=raw["address"],
                )
                if all(normalize(fields[k]) not in excluded[label] | used[label] for k, label in zip(KEYS, LABELS)):
                    break
            else:
                raise ValueError(f"Cannot construct disjoint subject {language}/{i}")
            for key, label in zip(KEYS, LABELS):
                used[label].add(normalize(fields[key]))
            fields["subject_id"] = f"gateway-hardneg-v1/train-pool/{language}/{i:03d}"
            people.append(fields)
        pools[language] = people
    return pools


def mix_plan(language):
    n = COUNTS[language]
    plan = [
        mix
        for mix, percent in (("negative", 20), ("small", 40), ("medium", 30), ("dense", 10))
        for _ in range(n * percent // 100)
    ]
    random.Random(SEED + base.LANGUAGES.index(language)).shuffle(plan)
    return plan


def make_row(language, index, mix, prose, pools):
    rng = random.Random(SEED + base.LANGUAGES.index(language) * 100000 + index)
    p = prose[language]
    family = index % len(FAMILIES)
    variant = index // len(FAMILIES) % 3
    n = {"negative": 0, "small": rng.randint(1, 2), "medium": rng.randint(3, 5), "dense": 6}[mix]
    people = rng.sample(pools[language], n)
    row_id = f"gateway-hardneg-v1/train/{language}/{index:05d}"
    negatives = []

    def negative(value, category):
        # Mark utility values independently of the protected placeholder renderer.
        slot = len(negatives)
        negatives.append((value, category))
        return f"{{{{negative:{slot}}}}}"

    def contact(j):
        keys = ["name", rng.choice(KEYS[1:])]
        if mix == "dense":
            keys = list(KEYS)
        return " / ".join(f"{p['private'][KEYS.index(k)]}: [[{j}.{k}]]" for k in keys)

    layout = rng.randrange(3)
    template = p["tasks"][family][variant] + "\n\n"
    if people:
        template += {
            "en": "Also draft clarification questions for the listed delivery contacts; retain their details in the internal working copy.",
            "ro": "Redactează și întrebări de clarificare pentru persoanele de contact de mai jos; păstrează datele lor în copia internă de lucru.",
            "de": "Formuliere außerdem Rückfragen an die genannten Lieferkontakte; behalte deren Angaben in der internen Arbeitsfassung bei.",
            "fr": "Prépare aussi les questions à poser aux contacts de livraison indiqués ; conserve leurs coordonnées dans la copie de travail interne.",
            "es": "Redacta también preguntas para los contactos de entrega indicados; conserva sus datos en la copia interna de trabajo.",
            "it": "Prepara anche le domande per i contatti di consegna indicati; conserva i loro dati nella copia di lavoro interna.",
            "nl": "Stel ook verduidelijkende vragen op voor de genoemde bezorgcontacten; behoud hun gegevens in de interne werkversie.",
            "pl": "Przygotuj też pytania do wskazanych osób kontaktowych w sprawie dostawy; zachowaj ich dane w wewnętrznej kopii roboczej.",
        }[language] + "\n\n"
    if people and layout == 0:
        template += p["contact"] + ":\n" + "\n".join(contact(j) for j in range(n)) + "\n\n"
    template += negative(rng.choice(p["merchants"]), "merchant") + "\n"
    extra_headers = {
        "en": ["Packaging", "Status", "Merchant"],
        "ro": ["Ambalaj", "Stare", "Comerciant"],
        "de": ["Verpackung", "Status", "Händler"],
        "fr": ["Emballage", "Statut", "Commerçant"],
        "es": ["Envase", "Estado", "Comercio"],
        "it": ["Confezione", "Stato", "Negozio"],
        "nl": ["Verpakking", "Status", "Winkel"],
        "pl": ["Opakowanie", "Status", "Sprzedawca"],
    }[language]
    headers = p["headers"] if family == 3 else [p["headers"][k] for k in (0, 1, 2, 6)] + extra_headers
    for k, header in enumerate(headers):
        template += (" | " if k else "") + negative(header, "header")
    template += "\n"
    # Useful quantity/price/packaging combinations, not an arbitrary example ID suffix.
    line_count = rng.randint(max(3, n), max(6, n + 2))
    for k in range(line_count):
        product = rng.randrange(len(p["products"]))
        code = (
            f"{'PAP NOTE ENV PEN SLV FOL CRD BRK'.split()[product]}-{rng.randrange(100, 999)}-{rng.choice('ABCDEFGH')}"
        )
        cents = rng.randint(90, 4590)
        quantity = rng.randint(1, 24)
        amount = f"{cents * quantity // 100},{cents * quantity % 100:02d}"
        cells = [
            negative(p["products"][product], "product"),
            str(quantity),
            f"{cents // 100},{cents % 100:02d}",
        ]
        if family == 3:
            cells += [
                amount,
                negative(rng.choice(p["statuses"]), "status"),
                amount,
                negative(code, "article_code"),
                "0 %",
            ]
        else:
            cells += [
                negative(code, "article_code"),
                negative(rng.choice(p["packaging"]), "packaging"),
                negative(rng.choice(p["statuses"]), "status"),
                negative(rng.choice(p["merchants"]), "merchant"),
            ]
        template += " | ".join(cells) + "\n"
        if family == 3:
            template += extra_headers[0] + ": " + negative(rng.choice(p["packaging"]), "packaging") + "\n"
        if family in {2, 7}:
            template += p["caption"] + ": " + negative(rng.choice(p["figures"]), "historical_figure") + "\n"
        if people and layout == 1 and k < n:
            template += p["contact"] + ": " + contact(k) + "\n"
    if people and layout == 2:
        template += "\n" + p["contact"] + ":\n" + "\n".join(contact(j) for j in range(n)) + "\n"
    template += "\n" + rng.choice(p["closing"])
    # Splice negatives before contacts, then recover their final offsets with one combined parser.
    text, spans, hard_negatives, cursor = "", [], [], 0
    pattern = r"\{\{negative:(\d+)\}\}|\[\[(\d+)\.(\w+)\]\]"
    for match in re.finditer(pattern, template):
        text += template[cursor : match.start()]
        if match[1] is not None:
            value, category = negatives[int(match[1])]
            hard_negatives.append(dict(start=len(text), end=len(text) + len(value), category=category, text=value))
        else:
            j, key = int(match[2]), match[3]
            value = people[j][key]
            spans.append(dict(start=len(text), end=len(text) + len(value), label=LABELS[KEYS.index(key)]))
        text += value
        cursor = match.end()
    text += template[cursor:]
    row = dict(text=text, spans=spans, language=language, domain="gateway")
    metadata = dict(
        id=row_id,
        split="train",
        language=language,
        family_id=f"gateway-hardneg-v1/{FAMILIES[family]}",
        template_variant=variant,
        scenario_id=f"gateway-hardneg-v1/{family}/{index:05d}",
        subject_ids=[p["subject_id"] for p in people],
        mix=mix,
        layout=layout,
        hard_negatives=hard_negatives,
        authoring_seed=SEED,
    )
    return row, metadata


def rows(prose, pools):
    for language in base.LANGUAGES:
        for i, mix in enumerate(mix_plan(language)):
            yield make_row(language, i, mix, prose, pools)
