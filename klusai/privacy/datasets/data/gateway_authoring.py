"""RES-124 offline authoring: original prose, locale-pack values, construction-time gold.

Template siblings share reserved families and scenario/translation identities. No API,
model inference, training text, or borrowed locale-pack document template is used.
"""

from __future__ import annotations

import importlib
import random
import re
import unicodedata
from pathlib import Path

from europriv_bench.national_id import REGISTRY
from europriv_bench.taxonomy import BY_NAME, TAXONOMY_VERSION

from .en_generators import gen_card, nino_format_valid
from .gateway_traffic import LANGUAGES, Conversation, digest, file_digest
from .ro_generators import gen_person as ro_person

ROOT = Path(__file__).resolve().parents[4]
PROSE = ROOT / "docs/gateway-authoring/prose.json"
GUIDE = ROOT / "docs/gateway-authoring/annotation-guide.md"
TOKENIZER_ID = "FacebookAI/xlm-roberta-large"
TOKENIZER_REVISION = "c23d21b0620b635a76227c604d44e43a9f0ee389"
SEED = 124
VERSION = "res124-tranche1-v1"
COUNTRIES = dict(zip(LANGUAGES, ("RO", "GB", "DE", "FR", "ES", "IT", "NL", "PL")))
ID_ATTRS = dict(zip(LANGUAGES, ("cnp", "nino", "steuer_id", "nir", "dni", "codice_fiscale", "bsn", "pesel")))
KEYS = (
    "name",
    "email",
    "phone",
    "address",
    "national",
    "iban",
    "card",
    "dob",
    "case",
    "company",
    "mrn",
    "health",
    "secret",
)
LABELS = (
    "PERSON",
    "EMAIL",
    "PHONE",
    "ADDRESS",
    "NATIONAL_ID",
    "ACCOUNT_ID",
    "ACCOUNT_ID",
    "DATE",
    "CASE_NUMBER",
    "COMPANY_ID",
    "MRN",
    "HEALTH_CONDITION",
    "SECRET",
)
CONDITIONS = dict(
    zip(
        LANGUAGES,
        (
            "astm bronșic",
            "asthma",
            "Asthma bronchiale",
            "asthme",
            "asma",
            "asma bronchiale",
            "astma",
            "astma oskrzelowa",
        ),
    )
)
EXTRA = {
    "ro": (
        "Date copiate",
        "Istoric citat",
        "Notițe suplimentare",
        "Verificări",
        "variantă",
        "în așteptare",
        "confirmat",
    ),
    "en": ("Copied details", "Quoted history", "Additional notes", "Checks", "variant", "pending", "confirmed"),
    "de": ("Kopierte Angaben", "Zitierter Verlauf", "Weitere Notizen", "Prüfungen", "Variante", "offen", "bestätigt"),
    "fr": (
        "Informations copiées",
        "Historique cité",
        "Notes complémentaires",
        "Vérifications",
        "variante",
        "en attente",
        "confirmé",
    ),
    "es": (
        "Datos copiados",
        "Historial citado",
        "Notas adicionales",
        "Comprobaciones",
        "variante",
        "pendiente",
        "confirmado",
    ),
    "it": ("Dati copiati", "Cronologia citata", "Note aggiuntive", "Verifiche", "variante", "in attesa", "confermato"),
    "nl": (
        "Gekopieerde gegevens",
        "Geciteerde geschiedenis",
        "Aanvullende notities",
        "Controles",
        "variant",
        "in behandeling",
        "bevestigd",
    ),
    "pl": (
        "Skopiowane dane",
        "Cytowana historia",
        "Dodatkowe notatki",
        "Kontrole",
        "wariant",
        "oczekuje",
        "potwierdzono",
    ),
}


def get_tokenizer(path: Path | None = None):
    from tokenizers import Tokenizer

    if path is None:
        from huggingface_hub import hf_hub_download

        path = Path(hf_hub_download(TOKENIZER_ID, "tokenizer.json", revision=TOKENIZER_REVISION, local_files_only=True))
    tokenizer = Tokenizer.from_file(str(path))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    return tokenizer


def count_tokens(messages: list[dict], tokenizer) -> int:
    # Message/role framing is not included. Each explicit text part is encoded separately.
    return sum(len(tokenizer.encode(p["text"], add_special_tokens=False).ids) for m in messages for p in m["parts"])


def person_values(language: str, rng: random.Random, key: str) -> dict:
    module = importlib.import_module(f"klusai.privacy.datasets.data.{language}_generators")
    p = module.gen_person(rng)
    national = getattr(p, ID_ATTRS[language])
    info = None if language == "en" else REGISTRY[COUNTRIES[language]].parse(national)
    if language == "en":
        assert nino_format_valid(national)
    else:
        assert info.valid, (language, national)
    # Reserved .invalid domain; never reuse a locale pack's possibly routable email.
    handle = unicodedata.normalize("NFKD", f"{p.first_name}.{p.last_name}").encode("ascii", "ignore").decode().lower()
    handle = re.sub(r"[^a-z0-9.]+", ".", handle).strip(".")
    address = p.address
    for attr in ("postcode", "plz", "cap", "cp", "code_postal"):
        postal = getattr(p, attr, None)
        if postal:
            address = address.replace(postal, "")
    address = " ".join(address.split())
    values = dict(
        name=f"{p.first_name} {p.last_name}",
        alias=p.first_name,
        email=f"{handle}.{key}@example.invalid",
        phone=p.phone,
        address=address,
        national=national,
        iban=p.iban,
        card=gen_card(rng),
        case=f"C-{key.upper()}",
        mrn=f"MRN-{key.upper()}",
        health=CONDITIONS[language],
        secret=f"synthetic_only_{rng.getrandbits(96):024x}",
    )
    # Preserve the exact precision supplied by the decoder; never invent century/day.
    if info and info.extra.get("birth_date"):
        values["dob"] = info.extra["birth_date"]
    elif language == "it":
        values["dob"] = p.dob
    elif language == "fr":
        values["dob"] = f"{info.extra['birth_month']:02d}/{info.extra['birth_year_2digit']}"
    else:
        values["dob"] = f"{rng.randint(1960, 2000)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
    company_functions = {
        "ro": "gen_cui",
        "de": "gen_ust_idnr",
        "fr": "gen_siren",
        "it": "gen_partita_iva",
        "pl": "gen_nip",
        "nl": "gen_kvk",
    }
    values["company"] = (
        getattr(module, company_functions[language])(rng) if language in company_functions else f"REG-{key.upper()}"
    )
    # A cross-border ID in EN provides genuine checksum-bearing national-ID coverage;
    # its independently generated DOB is never attached to the UK subject.
    if language == "en":
        values["foreign"] = ro_person(rng).cnp
    return values


def splice(template: str, fields: dict, message: int, subject_prefix: str) -> tuple[dict, list[dict]]:
    text, spans, cursor = "", [], 0
    for match in re.finditer(r"\[\[([0-9]+)\.([a-z_]+)\]\]", template):
        text += template[cursor : match.start()]
        person, field = match.groups()
        value = fields[int(person)][field]
        start = len(text)
        text += value
        canonical = {"alias": "name", "obfuscated": "email", "split_iban": "iban", "foreign": "national"}.get(
            field, field
        )
        label = LABELS[KEYS.index(canonical)]
        entity = f"{subject_prefix}/{person}/{canonical}"
        if field == "foreign":
            entity += "/cross-border"
        spans.append(
            dict(
                message=message,
                part=0,
                start=start,
                end=len(text),
                text=value,
                label=label,
                entity_id=entity,
                subject_id=f"{subject_prefix}/{person}",
                identifier_class=BY_NAME[label].identifier_class.value.upper(),
                protection="pseudonymize" if label == "PERSON" else "mask",
            )
        )
        cursor = match.end()
    text += template[cursor:]
    assert "[[" not in text
    assert all(text[s["start"] : s["end"]] == s["text"] for s in spans)
    return {"role": "user", "parts": [{"type": "text", "text": text}]}, spans


def allocation(n: int, split: str) -> list[tuple[str, str]]:
    if n % 20:
        raise ValueError("exact tranche percentages require multiples of 20 per language")
    subjects = [
        s for s, pct in (("negative", 20), ("small", 40), ("medium", 30), ("dense", 10)) for _ in range(n * pct // 100)
    ]
    lengths = [s for s, pct in (("short", 50), ("medium", 35), ("long", 15)) for _ in range(n * pct // 100)]
    rng = random.Random(SEED + (0 if split == "test" else 10000))
    # Ensure every workflow has two non-short positives, so required formats/labels
    # are possible even in the small dev tranche. No sampled outcome is consulted.
    for _ in range(10000):
        rng.shuffle(subjects)
        rng.shuffle(lengths)
        result = list(zip(subjects, lengths))
        if all(
            sum(s != "negative" and length != "short" for i, (s, length) in enumerate(result) if i % 8 == w) >= 2
            for w in range(8)
        ):
            return result
    raise ValueError("too few slots for all workflow strata")


def make_draft(language: str, split: str, index: int, mix: str, length: str, tokenizer, prose: dict) -> dict:
    workflow, slot = index % 8, index // 8
    family_number = workflow * 3 + (2 if split == "test" else 1)
    family = f"gateway-v1/family-{family_number:03d}"
    row_id = f"gateway-v1/{split}/{language}/{workflow:02d}-{slot:03d}"
    seed = SEED + LANGUAGES.index(language) * 100000 + (10000 if split == "dev" else 0) + index
    rng = random.Random(seed)
    n = {"negative": 0, "small": 1 + slot % 2, "medium": 3 + slot % 3, "dense": 6}[mix]
    fields = []
    for person in range(n):
        key = f"{'t' if split == 'test' else 'd'}{LANGUAGES.index(language)}{index:04d}{person}"
        for _ in range(1000):
            values = person_values(language, rng, key)
            if values["name"] not in {v["name"] for v in fields}:
                fields.append(values)
                break
        else:
            raise ValueError("locale name pool exhausted")
    p = prose[language]
    labels = dict(zip(KEYS, p["labels"]))
    if language == "fr":
        labels["dob"] = "Naissance (mois/année sur deux chiffres)"
    extra = EXTRA[language]
    features = {"unicode", "punctuation"}
    secondary = []
    # Numeric product IDs are explicitly public catalogue codes, including checksum
    # look-alikes. Different split prefixes avoid an accidental text sibling.
    product = f"{'73' if split == 'test' else '84'}{LANGUAGES.index(language)}{index:010d}"
    if not n:
        template = p[f"negative_{split}"] + f"\nSKU: {product}."
        features.update(("public_date", "public_org", "public_statute"))
    else:
        template = p[split][workflow]
        template += "\n" + extra[0] + ":\n"
        template += f"{labels['name']}: [[0.name]]"
        if length == "short" and n <= 2:
            template += f"\n{labels['email']}: [[0.email]]"
            features.add("email")
        if length != "short":
            if workflow in (1, 2):
                template += "\n" + p[("billing_" if workflow == 1 else "hr_") + split]
            keys = {
                0: ("email", "phone", "address"),
                1: ("iban", "card", "company"),
                2: ("email", "national", "dob"),
                3: ("national", "dob", "mrn", "health"),
                4: ("case", "national", "address"),
                5: ("email", "phone", "secret"),
                6: ("email", "secret"),
                7: ("national", "iban", "card"),
            }[workflow]
            for key in keys:
                if fields[0][key] is not None:
                    template += f"\n{labels[key]}: [[0.{key}]]"
                    feature = {
                        "national": "national_id",
                        "iban": "bank_account",
                        "case": "case_id",
                        "company": "company_id",
                        "mrn": "medical_id",
                        "health": "health_condition",
                    }.get(key, key)
                    features.add(feature)
            # Repeated full mention and first-name alias denote the same subject.
            template += f"\n{extra[1]}:\n> [[0.name]] — [[0.alias]]"
            features.update(("quoted_history", "repeated_entity", "aliases"))
            if workflow == 6:
                fields[0]["obfuscated"] = fields[0]["email"].replace("@", " [at] ").replace(".", " [dot] ")
                template += '\n```json\n{"user":"[[0.obfuscated]]","token":"[[0.secret]]","retry":2}\n```'
                features.update(("obfuscated_identifier", "json_code"))
            if workflow == 7:
                fields[0]["split_iban"] = fields[0]["iban"][:8] + "\n" + fields[0]["iban"][8:]
                template += f"\n{labels['iban']}: [[0.split_iban]]"
                features.add("split_identifier")
            if language == "en" and workflow == 4:
                # A separately labelled foreign identifier; no invented encoded DOB.
                template += "\nRomanian identity record supplied separately, CNP: [[0.foreign]]"
            if workflow == 5:
                secondary = ["ro" if language == "en" else "en"]
                template += (
                    "\nTe rog, răspunde pe scurt; am nevoie de pașii de verificare."
                    if language == "en"
                    else "\nPlease keep the error message unchanged; the shared helpdesk works in English."
                )
                features.add("code_switch")
    if n > 1:
        template += "\n" + p["others"] + ": " + "; ".join(f"[[{j}.name]]" for j in range(1, n))
    if length != "short":
        template += "\n\n" + p[f"context_{split}"]
    if length == "long":
        template += "\n\n" + p[f"tail_{split}"] + "\n\n----- " + extra[1] + " -----\n" + p[f"attachment_{split}"]
        features.add("quoted_history")
    message, spans = splice(template, fields, 0, row_id + "/subject")
    messages = [message]
    if n and length != "short" and workflow == 6:
        payload, payload_spans = splice(
            '{"status":401,"owner":"[[0.name]]","access_token":"[[0.secret]]"}', fields, 1, row_id + "/subject"
        )
        payload["role"] = "tool"
        messages.append(payload)
        spans.extend(payload_spans)
        features.add("tool_payload")
    lo, hi = {"short": (32, 128), "medium": (129, 512), "long": (513, 2048)}[length]
    tokens = count_tokens(messages, tokenizer)
    if tokens > hi and length == "short" and n:
        # Use the initial complete sentence, never truncate a span or token sequence.
        lead = p[split][workflow].split(". ")[0].rstrip(".") + "."
        template = lead + "\n" + "; ".join(f"[[{j}.name]]" for j in range(n))
        if n <= 2:
            template += "\n[[0.email]]"
        message, spans = splice(template, fields, 0, row_id + "/subject")
        messages = [message]
        tokens = count_tokens(messages, tokenizer)
    if tokens < lo:
        raise ValueError(f"length underflow {row_id}: {tokens} < {lo}")
    if tokens > hi:
        raise ValueError(f"length overflow {row_id}: {tokens} > {hi}")
    return dict(
        schema_version="gateway-traffic-v1",
        config_status="dev",
        taxonomy_version=TAXONOMY_VERSION,
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
        tokenizer_id=TOKENIZER_ID,
        tokenizer_revision=TOKENIZER_REVISION,
        truncated=False,
        authoring_seed=seed,
        intended_mix=mix,
        intended_length=length,
    )


def attach_provenance(draft: dict, artifact: Path, revision: str, artifact_hash: str) -> Conversation:
    data = dict(draft)
    seed = data.pop("authoring_seed")
    data.pop("intended_mix")
    data.pop("intended_length")
    data["provenance"] = dict(
        source_revision=revision,
        source_split="original-authored-tranche1",
        source_record_id=data["id"],
        artifact_path=str(artifact.relative_to(ROOT)),
        file_sha256=artifact_hash,
        author="KlusAI / Codex",
        tool="Codex session; deterministic Python renderer",
        session="RES-124/2026-10-11",
        generator_version=VERSION,
        seed=seed,
        prompt_sha256=file_digest(PROSE),
        content_sha256=digest(data["messages"]),
        identity_provenance="New fictional locale-pack value draws, no source document prose. "
        "Language adaptations share family/scenario/translation identities within one split. "
        "Subjects are local fictional identities; names alone do not establish real identity. "
        "Prose families independently authored for dev and test; human semantic-overlap review pending.",
        exclusions=["No training document templates", "No external corpus prose", "No customer logs", "No Piiranha"],
        review=dict(
            annotators=["openai/codex-session"], native_reviewers=[], adjudicator=None, guide_sha256=file_digest(GUIDE)
        ),
    )
    return Conversation.model_validate(data)
