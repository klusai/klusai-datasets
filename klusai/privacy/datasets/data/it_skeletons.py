"""it-realskeleton-v1: faithful real-structure Italian documents + synthetic PII (codice fiscale).

The Italian sibling of ``ro_skeletons`` / ``pl_skeletons``: documents that mirror the STRUCTURE and
boilerplate of real Italian official document types — a hospital discharge letter (`LETTERA DI
DIMISSIONE`), a services contract (`CONTRATTO DI PRESTAZIONE DI SERVIZI`), a self-declaration
(`DICHIARAZIONE SOSTITUTIVA DI CERTIFICAZIONE`, the classic Italian *autocertificazione*), and an
administrative letter — populated with **synthetic** Italian identifiers (checksum-valid *codice
fiscale*, CF-consistent date of birth, partita IVA, Italian IBAN, +39 phones, addresses), with
Italian gender agreement.

This is the **third decode-bearing measurement** (after RO/CNP and PL/PESEL): the codice fiscale is
the richest of the three — a missed (un-redacted) CF deterministically discloses **DATE_OF_BIRTH +
SEX + PLACE_OF_BIRTH** (the Belfiore comune/country of birth), so the re-identification leak counts
place-of-birth, not just DOB+sex (KLU-105). Re-identification is scored by ``national_id_leakage``;
rows carry ``country='IT'`` so the metric dispatches to the codice-fiscale validator.

**Omocodia is exercised in-dataset.** A documented fraction of subjects carry an *omocode* CF (the
letter-for-digit variant the tax authority assigns on collision) rather than the base form. The
benchmark decoder reverses omocodia before decoding, so a leaked omocode discloses the same QIs as a
leaked base CF — the leak metric must not be fooled by the letter substitution. (Each omocode is a
distinct synthetic identity; it is NOT the same subject as any base CF.)

Because the skeletons are authored faithful reproductions of *public document structure* (not scraped
real records), there is **no residual real PII by construction** — every identifier is synthetic — so
the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a quality spot-check,
not a personal-data hunt.

Offset-determinism, the byte-equality assert and the strict BIOES gate are inherited unchanged from
the shared ``localepack.fill_document`` (same invariants as RO/PL). This config is
``config_status=dev`` — a citable-track candidate, not yet validated (pending native-speaker review +
IAA). All four templates are **one authored skeleton family** sharing a single fill path; a leak
headline from a single template family is not validated generalization — a second independent IT
template family is required before this is cited (the KLU-101 RO hardening, replicated for IT).

Re-identification accounting is **per distinct subject** (KLU-49): the discharge-letter template
deliberately repeats the patient's codice fiscale — once in the identity header and again in the
`Codice Fiscale:` line, as real Italian discharge letters do — so the gold count and leak metric must
NOT double-count that subject. The harness ``national_id_leakage`` dedups by ``(document, country,
normalized value)``.
"""

from __future__ import annotations

import random
import unicodedata
from collections.abc import Iterator

from .it_generators import (
    CITIES,
    codice_fiscale_valid,
    gen_iban_it,
    gen_omocode,
    gen_partita_iva,
    gen_person,
    iban_it_valid,
    partita_iva_valid,
)
from .localepack import ChecksummedID, Doc, LocalePack

COUNTRY = "IT"

# Probability that a subject's CF is rendered as an omocode rather than the base form. Keeps the
# omocodia decode path exercised end-to-end in the published dataset (~1 in 6 subjects).
_OMOCODE_RATE = 0.17

HOSPITALS = ["Ospedale Civile", "Ospedale Maggiore", "Policlinico Universitario", "Ospedale San Paolo"]
COMPANIES = ["Esempio S.r.l.", "TecnoPlus S.p.A.", "StudioRag S.r.l.", "MediCare S.r.l."]
CONDITIONS = [
    "ipertensione arteriosa essenziale", "diabete mellito di tipo 2", "polmonite comunitaria",
    "gastrite cronica", "lombosciatalgia", "bronchite acuta",
]
WARDS = ["Reparto di Medicina Interna", "Reparto di Cardiologia", "Reparto di Chirurgia Generale", "Reparto di Neurologia"]


def _ascii(s: str) -> str:
    """ASCII-fold Italian accents for realistic emails."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two entities
# share a whitespace token (the strict BIOES gate fails loud otherwise).
TEMPLATES = [
    ("clinical", """LETTERA DI DIMISSIONE OSPEDALIERA

{hospital} — {ward}

Paziente: {patient}
Codice Fiscale: {cf} , telefono: {phone}
Data di nascita: {dob} , residenza: {address}

Diagnosi principale: {condition} .
Anamnesi: {paziente_word} si è presentato in data {date} con la sintomatologia descritta.
Indicazioni alla dimissione: terapia secondo schema, controllo tra 30 giorni.

Identificativo paziente (CF): {cf_id}
Medico curante: Dr. {doctor}
Data di emissione: {date}"""),

    ("legal", """CONTRATTO DI PRESTAZIONE DI SERVIZI
N. {contractno} del {date}

Parti contraenti:
1. {company} , con sede in {address2} , partita IVA {piva} ,
   conto IBAN {iban} , rappresentata da {doctor} ;
2. {patient} , codice fiscale {cf} , {residente} in {address} , telefono {phone} ,
   e-mail {email} .

Oggetto del contratto è la prestazione dei servizi concordati tra le parti.
Il presente contratto è stipulato in data {date} , in due copie di pari tenore."""),

    ("legal", """DICHIARAZIONE SOSTITUTIVA DI CERTIFICAZIONE
(art. 46 D.P.R. 28 dicembre 2000, n. 445)

Io {sottoscritto} {patient} , codice fiscale {cf} , {residente} in {address} ,
telefono {phone} , e-mail {email} , consapevole delle sanzioni penali previste in caso di
dichiarazioni mendaci, dichiaro sotto la mia responsabilità che i dati forniti sono veritieri.

Data: {date}
Firma: ____________"""),

    ("admin", """A: {patient}
Indirizzo: {address}

Oggetto: pratica n. {contractno} / {date}

{salutation} {patient} , La informiamo che la Sua richiesta è stata registrata.
Per ulteriori informazioni La preghiamo di contattarci al numero {phone} o all'indirizzo {email} .

Cordiali saluti,
{doctor}
{company}
{date}"""),
]


def _person_cf(rng: random.Random):
    """A coherent person plus the CF *as it appears in the document*: base form, or — with
    probability ``_OMOCODE_RATE`` — an omocode of that same identity (≥1 substitution). The omocode
    decodes to the same DOB/sex/place as its base, and is a distinct synthetic identity."""
    p = gen_person(rng)
    cf = p.codice_fiscale
    if rng.random() < _OMOCODE_RATE:
        cf = gen_omocode(cf, rng.randint(1, 3))
    return p, cf


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    patient, cf = _person_cf(rng)
    doctor = gen_person(rng)
    m = patient.sex == "M"  # Italian gender agreement for boilerplate (not PII → label "O")
    return {
        "sottoscritto": ("sottoscritto" if m else "sottoscritta", "O"),
        "residente": ("residente" if m else "residente", "O"),  # invariant, kept for parity
        "salutation": ("Egregio Signor" if m else "Gentile Signora", "O"),
        "paziente_word": ("Il paziente" if m else "La paziente", "O"),
        "ward": (rng.choice(WARDS), "O"),  # not PII — plain text, no span
        "patient": (f"{patient.first_name} {patient.last_name}", "PERSON"),
        "doctor": (f"{doctor.first_name} {doctor.last_name}", "PERSON"),
        "cf": (cf, "NATIONAL_ID"),
        # Real Italian discharge letters repeat the CF as the patient identifier. Same VALUE as
        # {cf} → the per-subject dedup in national_id_leakage collapses it (KLU-49 guard); it is NOT
        # a second subject and must not inflate the gold count.
        "cf_id": (cf, "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),  # DERIVED from the CF → birthday matches the CF
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.it", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "piva": (gen_partita_iva(rng), "COMPANY_ID"),
        "company": (rng.choice(COMPANIES), "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} di {patient.city}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "contractno": (f"{rng.randint(100, 9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(2018, 2025)}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure IT document (shared splice/byte-equality/strict-BIOES gate)."""
    return it_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield n offset-validated faithful-structure IT documents.

    Each row carries ``country='IT'`` so the country-dispatched ``national_id_leakage`` metric
    validates the gold IDs with the codice-fiscale validator (the default country is RO).
    """
    for row in it_skeleton_pack.generate_dataset(n, seed=seed):
        yield {**row, "country": COUNTRY}


def _gen_cf_selftest(rng: random.Random) -> str:
    """Self-test draw: a CF as it would appear in the dataset (base or omocode) — both must validate."""
    return _person_cf(rng)[1]


# it-realskeleton-v1 pack. CF / partita IVA / IBAN carry checksums (self-tested, including omocode
# CFs); the +39 phone carries no published checksum so it is documented under ``no_checksum_ids``.
# Single authored family for now (KLU-105) — a second independent IT family is required before this
# is cited, mirroring the KLU-101 RO hardening.
it_skeleton_pack = LocalePack(
    language="it",
    name="Italian (real-skeleton)",
    checksummed_ids=(
        ChecksummedID("codice fiscale", _gen_cf_selftest, codice_fiscale_valid),
        ChecksummedID("partita IVA", gen_partita_iva, partita_iva_valid),
        ChecksummedID("IBAN", gen_iban_it, iban_it_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
    no_checksum_ids=("phone (+39)",),
)

__all__ = ["gen_document", "generate_dataset", "it_skeleton_pack", "COUNTRY", "CITIES"]
