"""legal-realskeleton-v1: cleanly-licensed legal-domain real-structure documents + synthetic PII.

The **legal-domain** real-skeleton track (KLU-111) — the under-served, differentiating domain bet.
Where ``ro_skeletons`` (family A) is official correspondence and ``ro_skeletons_edu`` (family B) is
the academic registry, this track is the **legal genre**: documents that mirror the STRUCTURE and
boilerplate of the public legal-document types the EU privacy world runs on —

  1. an **EUR-Lex-style legal instrument** (titled act → numbered recitals "Whereas (n) …" → numbered
     "Article n" operative provisions → "Done at … done on …"), modelled on the *layout* of EU
     legislation as published on EUR-Lex;
  2. an **ECHR-style court judgment** (case caption ``CAUZA X împotriva României``, application
     number, composition, then the canonical ``ÎN FAPT`` / ``ÎN DREPT`` / ``PENTRU ACESTE MOTIVE,
     CURTEA`` operative sections), modelled on the *structure* of European Court of Human Rights
     judgments as published on HUDOC;
  3. a **GDPR Article 15 DSAR response** (a data controller's reply to a data-subject access
     request — identification block, categories of personal data processed, recipients, retention,
     rights), the privacy-operational legal document type the benchmark is ultimately about.

**Licensing — structure only, no redistributed text (the load-bearing KLU-111 guard).** These are
**authored** skeletons that reproduce the public *document structure / section layout* of EUR-Lex
legislation, ECHR judgments and GDPR access-request replies. **No copyrighted source text is
included or redistributed** — every sentence is original boilerplate and every identifier/party is
synthetic. Two source-license facts were verified and are recorded in ``conf/datasets.yaml``:

  * **EUR-Lex** — general reuse of Commission documents is authorised under **Commission Decision
    2011/833/EU** (reuse permitted, attribution, no exclusive rights). We do not even rely on this:
    we redistribute **no** EUR-Lex text, only the (uncopyrightable) section-layout convention.
  * **ECHR / HUDOC** — judgment reuse is permitted only "for private use or … information and
    education" with ``© ECHR-CEDH`` attribution, and HUDOC translations are copyright-protected.
    This is **NOT** cleanly redistributable under the program's license gate, so **no ECHR/HUDOC
    text is included** — we reproduce only the public judgment *structure* (caption → facts → law →
    operative parts), which is not copyrightable.

Because the skeletons are authored and every identifier is synthetic, there is **no residual real
PII by construction** — the artifact is GDPR-clean and CC-BY-4.0-redistributable, and human
validation is a quality spot-check, not a personal-data hunt.

**Decode-bearing re-identification (the dissociation headline).** Identifiers reuse the proven RO
generators: a valid-checksum **CNP** whose encoded date matches the document's stated date of birth.
A missed (un-redacted) CNP deterministically discloses **DATE_OF_BIRTH + SEX + COUNTY**, so the
re-identification leak is scored by the harness ``national_id_leakage`` (rows carry ``country='RO'``
→ the metric dispatches to the CNP validator). Re-identification is counted **per distinct subject**
``(document, country, normalized value)`` (KLU-49): the DSAR response legitimately repeats the
applicant's CNP (identification block + "cod numeric personal" confirmation line), as real
access-request replies do, so the repeat collapses to one subject and never double-counts.

Offset-determinism, the byte-equality assert and the strict BIOES gate are inherited unchanged from
the shared ``localepack.fill_document`` (same invariants as RO/PL/IT). This config is
``config_status=dev`` — a citable-track candidate, not yet validated (pending native-speaker review
+ IAA). All three templates are **one authored skeleton family** (the legal genre) sharing a single
fill path; a leak headline from a single template family is not validated generalization, so a
second independent legal template family is required before this is cited (the KLU-101 hardening,
replicated for the legal track). The track is a bounded proof-of-concept (1 language, 3 legal
document types) proving the harness generalizes to the legal domain — not a full legal corpus.
"""

from __future__ import annotations

import random
import unicodedata
from collections.abc import Iterator

from europriv_bench.national_id import validate_cnp

from .localepack import ChecksummedID, Doc, LocalePack
from .ro_generators import COUNTIES, cui_valid, gen_cui, gen_person

COUNTRY = "RO"


def _ascii(s: str) -> str:
    """ASCII-fold Romanian diacritics (ă→a, î/â→i/a, ș→s, ț→t) for realistic emails."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# Synthetic institutional parties — controllers / authorities / courts (not PII; rendered as
# ORG_PARTY). All invented names; no real institution is the subject of any document.
CONTROLLERS = [
    "SC DataServ Exemplu SRL", "SC TehnoPrivat SRL", "Institutul Exemplu de Cercetare",
    "SC ArhivaPlus SRL",
]
AUTHORITIES = [
    "Autoritatea Exemplu de Supraveghere", "Comisia Exemplu pentru Protecția Datelor",
]
PURPOSES = [
    "executarea contractului de prestări servicii", "îndeplinirea unei obligații legale",
    "gestionarea relației contractuale", "soluționarea cererii formulate",
]
DATA_CATEGORIES = [
    "date de identificare și de contact", "date privind contul bancar",
    "date privind corespondența administrativă", "date privind situația contractuală",
]
RIGHTS_SECTIONS = [
    "dreptul de acces, rectificare și ștergere",
    "dreptul la restricționarea prelucrării și la portabilitate",
]


# Faithful real-STRUCTURE legal templates (authored boilerplate — no redistributed source text).
# Slots are whitespace/punctuation-separated so no two entities share a whitespace token (the strict
# BIOES gate fails loud otherwise).
TEMPLATES = [
    # 1. EUR-Lex-style legal instrument: title → recitals → articles → "done at/on". Models the
    #    LAYOUT of EU legislation as published on EUR-Lex (reuse: Decision 2011/833/EU); text authored.
    ("legal", """DECIZIE-CADRU PRIVIND PRELUCRAREA DATELOR CU CARACTER PERSONAL
adoptată de {authority}

avand in vedere cererea inregistrata sub nr. {contractno} din {date} ,

Intrucat:
(1) prezentul act stabileste conditiile de prelucrare a datelor persoanei vizate {patient} ,
    avand codul numeric personal {cnp} , cu domiciliul in {address} ;
(2) datele de contact comunicate sunt telefon {phone} si adresa de e-mail {email} ;

ADOPTA PREZENTA DECIZIE:

Articolul 1
Operatorul de date este {controller} , inregistrat cu CUI {cui} .

Articolul 2
Prelucrarea are ca temei {purpose} si vizeaza {category} .

Articolul 3
Prezenta decizie produce efecte de la data comunicarii catre persoana vizata.

Adoptata la {city} , {date} ."""),

    # 2. ECHR-style judgment: caption → application no. → facts → law → operative parts. Models the
    #    STRUCTURE of ECHR judgments as published on HUDOC; NO HUDOC text reused (text is authored).
    ("legal", """CAUZA {patient} IMPOTRIVA ROMANIEI
(Cererea nr. {appno} / {year} )

HOTARARE

In cauza de mai sus, instanta, deliberand, pronunta urmatoarea hotarare.

IN FAPT
1. Reclamantul {patient} , resortisant roman nascut in {dob} , avand codul numeric personal {cnp} ,
   cu domiciliul in {address} , a sesizat instanta la data de {date} .
2. Reclamantul poate fi contactat la telefon {phone} sau la adresa {email} .

IN DREPT
3. Instanta examineaza cererea prin raportare la dispozitiile legale aplicabile in materie.

PENTRU ACESTE MOTIVE, INSTANTA,
declara cererea admisibila si dispune comunicarea prezentei hotarari partilor.

Pronuntata la {city} , {date} ."""),

    # 3. GDPR Article 15 DSAR response: identification → categories → recipients → retention → rights.
    #    The privacy-operational legal document type the benchmark targets. Authored boilerplate.
    ("legal", """RASPUNS LA CEREREA DE ACCES LA DATELE CU CARACTER PERSONAL
(art. 15 din Regulamentul general privind protectia datelor)

Catre: {patient}
Adresa: {address}

Stimata persoana vizata, ca urmare a cererii dumneavoastra inregistrate sub nr. {contractno}
din {date} , {controller} , in calitate de operator, va comunica urmatoarele.

Identificarea solicitantului: {patient} , cod numeric personal {cnp} .
Date de contact verificate: telefon {phone} , e-mail {email} .

Categoriile de date prelucrate: {category} , in scopul {purpose} .
Destinatarii datelor: {authority} . Perioada de stocare: 5 ani de la incetarea relatiei.
Drepturile dumneavoastra includ {rights} .

Pentru confirmarea identitatii a fost utilizat codul numeric personal {cnp_confirm} .

Cu stima,
{controller}
{date}"""),
]


def _fields(rng: random.Random) -> dict[str, tuple[str, str]]:
    patient = gen_person(rng)
    _, _, county = rng.choice(COUNTIES)
    year = rng.randint(2018, 2025)
    return {
        "patient": (f"{patient.first_name} {patient.last_name}", "PERSON"),
        "cnp": (patient.cnp, "NATIONAL_ID"),
        # The DSAR response repeats the applicant's CNP in the identity-confirmation line — same VALUE
        # as {cnp} → the per-subject dedup in national_id_leakage collapses it to ONE subject (KLU-49
        # guard). It is NOT a second subject and must not inflate the gold count.
        "cnp_confirm": (patient.cnp, "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),  # DERIVED from the CNP → birthday matches the CNP
        "address": (patient.address, "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.ro", "EMAIL"),
        "cui": (gen_cui(rng), "COMPANY_ID"),
        "controller": (rng.choice(CONTROLLERS), "ORG_PARTY"),
        "authority": (f"{rng.choice(AUTHORITIES)} {county}", "ORG_PARTY"),
        "purpose": (rng.choice(PURPOSES), "O"),       # not PII — plain text, no span
        "category": (rng.choice(DATA_CATEGORIES), "O"),
        "rights": (rng.choice(RIGHTS_SECTIONS), "O"),
        "city": (county, "O"),                         # place of "done at" / "pronounced at"
        "appno": (f"{rng.randint(1000, 99999)}", "CASE_NUMBER"),
        "contractno": (f"{rng.randint(100, 9999)}", "CASE_NUMBER"),
        "year": (str(year), "O"),
        "date": (f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{year}", "DATE"),
    }


def gen_document(rng: random.Random) -> Doc:
    """Offset-validated faithful-structure RO legal document (shared splice/byte-equality/BIOES gate)."""
    return ro_legal_skeleton_pack.gen_document(rng)


def generate_dataset(n: int, seed: int = 0) -> Iterator[dict]:
    """Yield n offset-validated faithful-structure RO legal documents.

    Each row carries ``country='RO'`` so the country-dispatched ``national_id_leakage`` metric
    validates and decodes the gold CNPs with the CNP validator (DOB + SEX + COUNTY disclosure).
    """
    for row in ro_legal_skeleton_pack.generate_dataset(n, seed=seed):
        yield {**row, "country": COUNTRY}


def _gen_cnp_selftest(rng: random.Random) -> str:
    return gen_person(rng).cnp


# legal-realskeleton-v1 pack. The legal genre — EUR-Lex-style instrument, ECHR-style judgment, GDPR
# Art.15 DSAR response. CNP / CUI carry checksums (self-tested). Single authored family for now
# (KLU-111) — a second independent legal family is required before this is cited (KLU-101 hardening).
GENRE = "legal (EUR-Lex-style instrument / ECHR-style judgment / GDPR Art.15 DSAR response)"

ro_legal_skeleton_pack = LocalePack(
    language="ro",
    name="Romanian (real-skeleton, legal genre)",
    checksummed_ids=(
        ChecksummedID("CNP", _gen_cnp_selftest, validate_cnp),
        ChecksummedID("CUI", gen_cui, cui_valid),
    ),
    fields=_fields,
    templates=tuple(TEMPLATES),
    family="L",
    genre=GENRE,
)

__all__ = ["gen_document", "generate_dataset", "ro_legal_skeleton_pack", "COUNTRY"]
