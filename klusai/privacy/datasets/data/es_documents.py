"""Offset-deterministic Spanish document generation (localized synthetic, template-based).

The ``es-synthetic-v1`` track: the Spanish sibling of ``ro_documents``. Documents splice
checksum-valid Spanish PII (DNI/NIF, IBAN, …) into template segments; spans are computed from the
splice positions, so ``text[start:end] == value`` holds by construction. The shared
``localepack.fill_document`` runs the byte-equality assert and the strict ``char_spans_to_bioes`` +
``validate_bioes`` gate.

The DNI is coverage-only (no embedded quasi-identifier) but checksum-valid; it is validated against
``europriv_bench.national_id`` (single source of truth). Slots are whitespace/punctuation-separated
so two entities never share a whitespace token.
"""

from __future__ import annotations

import random
import unicodedata

from .es_generators import (
    dni_valid,
    gen_iban_es,
    gen_nie,
    gen_person,
    iban_es_valid,
)
from .localepack import ChecksummedID, Doc, LocalePack

COMPANIES = ["Ejemplo S.L.", "TecnoPlus S.A.", "Gestoría S.L.", "MediCare S.L."]
HOSPITALS = ["Hospital General", "Hospital Universitario", "Clínica San Juan"]
CONDITIONS = [
    "hipertensión arterial", "diabetes tipo 2", "neumonía",
    "gastritis crónica", "bronquitis aguda",
]

TEMPLATES = [
    ("legal",
     "Yo, el abajo firmante {person}, DNI {dni}, con domicilio en {address}, "
     "teléfono {phone}, declaro lo anterior como cierto a fecha de {date}."),
    ("legal",
     "Contrato celebrado entre {person} (DNI {dni}) y la empresa {company}, "
     "cuenta IBAN {iban}, en fecha {date}."),
    ("clinical",
     "Paciente: {person}, DNI {dni}, ingresado en fecha {date}. "
     "Teléfono de contacto: {phone}."),
    ("clinical",
     "Informe de alta — {person}, con domicilio en {address}, diagnóstico: {condition}."),
    ("admin",
     "Estimado/a {person}, correo {email}, confirmamos que el pago en la cuenta {iban} "
     "ha sido registrado en fecha {date}."),
    ("general",
     "{person} ({email}, tel. {phone}) ha solicitado una cita para el {date} "
     "en {address}."),
]


def _ascii(s: str) -> str:
    """ASCII-fold Spanish accents/ñ for realistic emails."""
    s = s.replace("ñ", "n").replace("Ñ", "N")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    """Build a coherent set of slot → (value, KP-label)."""
    p = gen_person(rng)
    email = _ascii(f"{p.first_name}.{p.last_name}").lower() + "@example.es"
    date = f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(1990, 2024)}"
    return {
        "person": (f"{p.first_name} {p.last_name}", "PERSON"),
        "dni": (p.dni, "NATIONAL_ID"),
        "address": (p.address, "ADDRESS"),
        "phone": (p.phone, "PHONE"),
        "iban": (p.iban, "ACCOUNT_ID"),
        "email": (email, "EMAIL"),
        "date": (date, "DATE"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated ES document (shared splice/byte-equality/strict-BIOES gate)."""
    return es_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated ES documents ({text, spans, language, domain})."""
    return es_pack.generate_dataset(n, seed=seed)


es_pack = LocalePack(
    language="es",
    name="Spanish",
    checksummed_ids=(
        ChecksummedID("DNI/NIF", lambda r: gen_person(r).dni, dni_valid),
        ChecksummedID("NIE", gen_nie, dni_valid),
        ChecksummedID("IBAN", gen_iban_es, iban_es_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
    no_checksum_ids=("phone (+34)",),
)
