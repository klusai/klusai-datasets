"""Offset-deterministic French document generation (localized synthetic, template-based).

The ``fr-synthetic-v1`` track: the French sibling of ``ro_documents``. Documents splice
checksum-valid French PII (NIR, SIREN, IBAN, …) into template segments; spans are computed from the
splice positions, so ``text[start:end] == value`` holds by construction. The shared
``localepack.fill_document`` runs the byte-equality assert and the strict ``char_spans_to_bioes`` +
``validate_bioes`` gate.

Slots are whitespace/punctuation-separated so two entities never share a whitespace token.
"""

from __future__ import annotations

import random
import unicodedata

from .fr_generators import (
    gen_iban_fr,
    gen_person,
    gen_siren,
    iban_fr_valid,
    nir_valid,
    siren_valid,
)
from .localepack import ChecksummedID, Doc, LocalePack

COMPANIES = ["Exemple SARL", "TechPlus SA", "BureauService SARL", "MediCare SAS"]
HOSPITALS = ["Centre Hospitalier", "Hôpital Universitaire", "Clinique Saint-Jean"]
CONDITIONS = [
    "hypertension artérielle", "diabète de type 2", "pneumonie",
    "gastrite chronique", "bronchite aiguë",
]

TEMPLATES = [
    ("legal",
     "Je soussigné {person}, numéro de sécurité sociale {nir}, demeurant à {address}, "
     "téléphone {phone}, déclare ce qui précède exact en date du {date}."),
    ("legal",
     "Contrat conclu entre {person} (n° SS {nir}) et la société {company}, "
     "SIREN {siren}, compte IBAN {iban}, le {date}."),
    ("clinical",
     "Patient : {person}, n° SS {nir}, admis le {date}. "
     "Téléphone de contact : {phone}."),
    ("clinical",
     "Compte rendu de sortie — {person}, demeurant à {address}, diagnostic : {condition}."),
    ("admin",
     "Cher/Chère {person}, e-mail {email}, nous confirmons que le paiement sur le compte {iban} "
     "a été enregistré le {date}."),
    ("general",
     "{person} ({email}, tél. {phone}) a demandé un rendez-vous pour le {date} "
     "à {address}."),
]


def _ascii(s: str) -> str:
    """ASCII-fold French accents for realistic emails."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Build a coherent set of slot → (value, KP-label)."""
    p = gen_person(rng)
    email = _ascii(f"{p.first_name}.{p.last_name}").lower() + "@example.fr"
    date = f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(1990, 2024)}"
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "nir": (p.nir, "NATIONAL_ID"),
        "address": (p.address, "ADDRESS"),
        "phone": (p.phone, "PHONE"),
        "iban": (p.iban, "ACCOUNT_ID"),
        "email": (email, "EMAIL"),
        "date": (date, "DATE"),
        "siren": (gen_siren(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated FR document (shared splice/byte-equality/strict-BIOES gate)."""
    return fr_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated FR documents ({text, spans, language, domain})."""
    return fr_pack.generate_dataset(n, seed=seed)


fr_pack = LocalePack(
    language="fr",
    name="French",
    checksummed_ids=(
        ChecksummedID("NIR", lambda r: gen_person(r).nir, nir_valid),
        ChecksummedID("SIREN", gen_siren, siren_valid),
        ChecksummedID("IBAN", gen_iban_fr, iban_fr_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
    no_checksum_ids=("phone (+33)",),
)
