"""ro-realskeleton-v1: faithful real-structure Romanian documents + synthetic PII.

Upgrade over `ro_documents` (the toy `ro-synthetic-v1` track): these mirror the STRUCTURE and
boilerplate of real Romanian official document types — the CNAS `SCRISOARE MEDICALĂ` discharge
letter, a services contract, a `DECLARAȚIE PE PROPRIA RĂSPUNDERE`, an administrative letter.
Because the skeletons are authored faithful reproductions of *public document structure* (not
scraped real records), there is **no residual real PII by construction** — every identifier is
synthetic — so the artifact is GDPR-clean and CC-BY-redistributable, and human validation is a
quality spot-check, not a personal-data hunt.

Offset-determinism is inherited from `ro_documents._fill` (splice → exact spans → byte-equality
assert → strict BIOES projection). The synthetic-context (`ro-synthetic-v1`) vs real-context
(this) gap is the Paper-2 measurement.
"""

from __future__ import annotations

import random
import unicodedata


def _ascii(s: str) -> str:
    """ASCII-fold Romanian diacritics (ă→a, î/â→i/a, ș→s, ț→t) for realistic emails."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes

from .ro_documents import Doc, _fill
from .ro_generators import COUNTIES, gen_ci, gen_cui, gen_person

HOSPITALS = ["Spitalul Clinic Județean", "Spitalul Municipal", "Spitalul Clinic de Urgență"]
COMPANIES = ["SC ExempluServ SRL", "SC TehnoPlus SRL", "SC ContabExpert SRL", "SC MediCare SRL"]
CONDITIONS = [
    "hipertensiune arterială esențială", "diabet zaharat tip 2", "pneumonie comunitară",
    "gastrită cronică", "lombosciatică", "bronșită acută",
]
SECTIONS = ["Medicină Internă", "Cardiologie", "Chirurgie Generală", "Neurologie"]

# Faithful real-structure templates. Slots are whitespace/punctuation-separated so no two
# entities share a whitespace token.
TEMPLATES = [
    ("clinical", """SCRISOARE MEDICALĂ

{hospital} — Secția {section}

Pacient: {patient}
CNP: {cnp} , Serie/nr. act identitate: {ci}
Data nașterii: {dob} , Cod asigurat: {cass}
Domiciliu: {address}
Telefon: {phone}

Diagnostic principal: {condition} .
Istoricul bolii: Pacientul s-a prezentat în data de {date} acuzând simptomatologia descrisă.
Recomandări la externare: tratament conform schemei, control peste 30 de zile.

Medic curant: Dr. {doctor}
Data întocmirii: {date}"""),

    ("legal", """CONTRACT DE PRESTĂRI SERVICII
Nr. {contractno} din {date}

Părțile contractante:
1. {company} , cu sediul în {address2} , CUI {cui} , cont IBAN {iban} , reprezentată de {doctor} ;
2. {patient} , CNP {cnp} , {domiciliat} în {address} , telefon {phone} , e-mail {email} .

Obiectul contractului îl constituie prestarea serviciilor convenite de părți.
Prezentul contract s-a încheiat astăzi, {date} , în două exemplare."""),

    ("legal", """DECLARAȚIE PE PROPRIA RĂSPUNDERE

{subsemnat} {patient} , CNP {cnp} , {posesor} al actului de identitate seria/nr. {ci} ,
{domiciliat} în {address} , telefon {phone} , e-mail {email} , declar pe propria răspundere,
cunoscând prevederile legale privind falsul în declarații, că datele furnizate sunt reale.

Data: {date}
Semnătura: ____________"""),

    ("admin", """Către: {patient}
Adresa: {address}

Ref: dosarul nr. {contractno} / {date}

{salutation} {patient} , vă comunicăm că solicitarea dumneavoastră a fost
înregistrată. Pentru informații suplimentare ne puteți contacta la {phone} sau {email} .

Cu stimă,
{doctor}
{company}
{date}"""),
]


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    patient = gen_person(rng)
    doctor = gen_person(rng)
    _, _, county = rng.choice(COUNTIES)
    m = patient.sex == "M"  # Romanian gender agreement for boilerplate (not PII → label "O")
    return {
        "subsemnat": ("Subsemnatul" if m else "Subsemnata", "O"),
        "domiciliat": ("domiciliat" if m else "domiciliată", "O"),
        "posesor": ("posesor" if m else "posesoare", "O"),
        "salutation": ("Stimate domnule" if m else "Stimată doamnă", "O"),
        "patient": (f"{patient.first_name} {patient.last_name}", "PERSON"),
        "doctor": (f"{doctor.first_name} {doctor.last_name}", "PERSON"),
        "cnp": (patient.cnp, "NATIONAL_ID"),
        "ci": (gen_ci(rng), "NATIONAL_ID"),
        "cass": (gen_person(rng).cnp, "NATIONAL_ID"),  # cod asigurat (distinct synthetic CNP)
        "dob": (f"{rng.randint(1,28):02d}.{rng.randint(1,12):02d}.{rng.randint(1950,2005)}", "DATE"),
        "address": (patient.address, "ADDRESS"),
        "address2": (doctor.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.ro", "EMAIL"),
        "iban": (patient.iban, "ACCOUNT_ID"),
        "cui": (gen_cui(rng), "COMPANY_ID"),
        "company": (f"{rng.choice(COMPANIES)}", "ORG_PARTY"),
        "hospital": (f"{rng.choice(HOSPITALS)} {county}", "ORG_PARTY"),
        "condition": (rng.choice(CONDITIONS), "HEALTH_CONDITION"),
        "section": (rng.choice(SECTIONS), "O"),   # not PII — rendered as plain text, no span
        "contractno": (f"{rng.randint(100,9999)}", "CASE_NUMBER"),
        "date": (f"{rng.randint(1,28):02d}.{rng.randint(1,12):02d}.{rng.randint(2018,2025)}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    domain, template = rng.choice(TEMPLATES)
    fields = _fields(rng)
    text, spans = _fill(template, fields)
    spans = [s for s in spans if s["label"] != "O"]  # drop non-PII filled slots (e.g. section)
    for sp in spans:
        assert text[sp["start"]:sp["end"]] == sp.pop("value"), "offset mismatch"
    validate_bioes(char_spans_to_bioes(text, [Span(s["start"], s["end"], s["label"]) for s in spans]))
    return Doc(text=text, spans=spans, domain=domain)


def generate_dataset(n: int, seed: int = 0):
    """Yield n offset-validated faithful-structure RO documents ({text, spans, language, domain})."""
    rng = random.Random(seed)
    for _ in range(n):
        d = gen_document(rng)
        yield {"text": d.text, "spans": d.spans, "language": "ro", "domain": d.domain}
