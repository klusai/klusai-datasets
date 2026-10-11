"""RES-77: authored Romanian v2 correspondence, independent of the v1 publishing entrypoint.

Original synthetic prose; no real records or external corpus. Labels retain the v1
PERSON/ORG_PARTY policy pending independent taxonomy adjudication. One template family.
"""

from __future__ import annotations

import random

from .localepack import ChecksummedID, LocalePack
from .ro_generators import gen_ci, gen_cui, gen_iban_ro, gen_person, iban_ro_valid
from .ro_skeletons import _ascii, ro_skeleton_pack

LOCALITIES = {
    "Cluj": "Cluj-Napoca", "Timiș": "Timișoara", "Iași": "Iași", "Brașov": "Brașov",
    "Constanța": "Constanța", "București": "București", "Bihor": "Oradea", "Dolj": "Craiova",
    "Prahova": "Ploiești", "Sibiu": "Sibiu",
}
# Diagnosis and specialty are selected together; no unsupported treatment scheme references.
CASES = (
    ("cardiologie", "hipertensiune arterială esențială",
     "Evaluarea de astăzi a urmărit controlul tensiunii arteriale. "
     "Valorile măsurate în cabinet au fost discutate cu persoana examinată.",
     "Se recomandă consemnarea valorilor tensionale măsurate la domiciliu și prezentarea "
     "jurnalului la următorul control."),
    ("diabet zaharat, nutriție și boli metabolice", "diabet zaharat tip 2",
     "Consultația a avut ca scop evaluarea periodică a controlului glicemic. "
     "Au fost analizate valorile din jurnalul de automonitorizare.",
     "Se recomandă continuarea automonitorizării și prezentarea jurnalului glicemic "
     "la următoarea consultație."),
    ("neurologie", "lombosciatică",
     "Consultația a avut ca scop reevaluarea evoluției clinice. "
     "La examinarea de astăzi, mobilitatea este mai bună față de evaluarea precedentă.",
     "Se recomandă evitarea suprasolicitării și reevaluare dacă simptomele persistă."),
)

TEMPLATES = (
    ("clinical", """SCRISOARE MEDICALĂ
{hospital}
Cabinet de {section}
Data consultației: {date}

Nume și prenume: {patient}
CNP: {cnp}
Data nașterii: {dob}; sex: {sex}
Domiciliu: {address}
Telefon: {phone}

Diagnostic: {condition}.
Motivul prezentării și evaluare: {history}
Conduită: la această consultație nu s-au făcut modificări ale tratamentului.
Recomandări: {plan}
Scrisoarea se eliberează pentru informarea medicului de familie.

Medic: dr. {sender}
Semnătura și parafa: ____________"""),
    ("legal", """CONTRACT DE PRESTĂRI SERVICII
Nr. {number} din {date}

1. Părțile contractante
{company}, cu sediul în {address2}, CUI {cui}, cont IBAN {iban},
prin reprezentantul său, {sender}, în calitate de prestator,
și {patient}, CNP {cnp}, cu domiciliul în {address}, în calitate de beneficiar,
au convenit încheierea prezentului contract.
Date de contact ale beneficiarului: {phone}; {email}.

2. Obiectul și termenul
Prestatorul se obligă să configureze conexiunea la internet și imprimanta pe un calculator
al beneficiarului, la domiciliul acestuia. Lucrarea se efectuează în cel mult cinci zile
lucrătoare de la semnare, la o oră stabilită de comun acord.

3. Prețul și recepția
Prețul total este de 250 lei, cu toate taxele incluse. Plata se face prin transfer în
contul prestatorului, în termen de cinci zile lucrătoare de la primirea facturii.
La final, părțile verifică împreună conexiunea și imprimarea unei pagini de probă și
consemnează rezultatul într-un proces-verbal. Eventualele deficiențe ale lucrării se
remediază fără costuri suplimentare în cel mult trei zile lucrătoare de la notificare.

Contractul s-a încheiat în două exemplare, câte unul pentru fiecare parte.
Prestator: ____________    Beneficiar: ____________"""),
    ("legal", """DECLARAȚIE PE PROPRIA RĂSPUNDERE
privind adresa de corespondență

{subsemnat} {patient}, CNP {cnp}, act de identitate seria și numărul {ci},
cu domiciliul în {address}, declar că doresc să primesc la această adresă
corespondența referitoare la cererea de eliberare a copiilor din dosarul nr. {number}.
Mă oblig să comunic în scris orice schimbare a adresei până la soluționarea cererii.
Pentru clarificări, pot fi {contactat} la telefon {phone} sau prin e-mail la {email}.

Data: {date}
Semnătura: ____________"""),
    ("admin", """{company}
Compartimentul relații cu clienții
Nr. de înregistrare: {number}
Data: {date}

Către: {patient}
Adresa de corespondență: {address}
Obiect: confirmarea înregistrării cererii de eliberare a unor copii

{salutation},

Vă confirmăm înregistrarea cererii dumneavoastră sub numărul menționat mai sus.
Cererea a fost transmisă compartimentului care păstrează dosarul, pentru identificarea
documentelor solicitate. Vă vom comunica în scris când puteți ridica aceste copii.
Dacă sunt necesare clarificări, vă vom contacta folosind datele din cerere.
Pentru informații despre stadiul solicitării, vă rugăm să menționați numărul de
înregistrare atunci când ne contactați.

Persoană de contact: {sender}
Telefon: {sender_phone}; e-mail: {sender_email}
Cu stimă,
Compartimentul relații cu clienții"""),
)


def _adult(rng):
    while True:
        person = gen_person(rng)
        if 1950 <= int(person.dob[-4:]) <= 1995:
            return person


def _address(person):
    street = person.address.rsplit(", ", 1)[0]
    locality = LOCALITIES[person.county]
    suffix = locality if person.county == "București" else f"{locality}, județul {person.county}"
    return f"{street}, {suffix}"


def _fields(rng: random.Random):
    patient = _adult(rng)
    sender = _adult(rng)
    while (sender.first_name, sender.last_name) == (patient.first_name, patient.last_name) or sender.phone == patient.phone:
        sender = _adult(rng)
    section, condition, history, plan = rng.choice(CASES)
    male = patient.sex == "M"
    return {
        "patient": (f"{patient.first_name} {patient.last_name}", "PERSON"),
        "sender": (f"{sender.first_name} {sender.last_name}", "PERSON"),
        "cnp": (patient.cnp, "NATIONAL_ID"),
        "ci": (gen_ci(rng), "NATIONAL_ID"),
        "dob": (patient.dob, "DATE"),
        "sex": ("masculin" if male else "feminin", "O"),
        "subsemnat": ("Subsemnatul" if male else "Subsemnata", "O"),
        "contactat": ("contactat" if male else "contactată", "O"),
        "salutation": ("Stimate domnule" if male else "Stimată doamnă", "O"),
        "address": (_address(patient), "ADDRESS"),
        "address2": (_address(sender), "ADDRESS"),
        "phone": (patient.phone, "PHONE"),
        "sender_phone": (sender.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.ro", "EMAIL"),
        "sender_email": (_ascii(f"{sender.first_name}.{sender.last_name}").lower() + "@example.ro", "EMAIL"),
        "iban": (sender.iban, "ACCOUNT_ID"),
        "cui": (gen_cui(rng), "COMPANY_ID"),
        "company": (rng.choice(("TehnoPlus SRL", "Servicii Conect SRL", "Digital Practic SRL")), "ORG_PARTY"),
        "hospital": (f"Ambulatoriul de specialitate — Centrul Medical {LOCALITIES[sender.county]}", "ORG_PARTY"),
        "section": (section, "O"), "condition": (condition, "HEALTH_CONDITION"),
        "history": (history, "O"), "plan": (plan, "O"),
        "number": (str(rng.randint(100, 9999)), "CASE_NUMBER"),
        "date": (f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.2025", "DATE"),
    }


ro_skeleton_v2_pack = LocalePack(
    language="ro", name="Romanian real-skeleton v2", fields=_fields, templates=TEMPLATES,
    checksummed_ids=ro_skeleton_pack.checksummed_ids + (ChecksummedID("IBAN", gen_iban_ro, iban_ro_valid),),
    no_checksum_ids=("CI",), family="A-v2", genre="official correspondence",
)


def generate_dataset(n: int, seed: int = 2026101277):
    for row in ro_skeleton_v2_pack.generate_dataset(n, seed):
        yield {**row, "country": "RO", "config": "ro-realskeleton-v2"}
