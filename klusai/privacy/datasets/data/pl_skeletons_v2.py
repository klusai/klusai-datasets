"""RES-77 authored Polish v2 correspondence; one family, local dev candidate.

Nominative identity fields avoid uninflected names after case-governing prepositions.
The v1 PERSON/ORG_PARTY policy is retained pending independent gold adjudication.
"""

from __future__ import annotations

import random

from .localepack import LocalePack
from .pl_generators import gen_nip, gen_person, gen_regon9
from .pl_skeletons import _ascii, pl_skeleton_pack

# Locative forms are authored, never obtained by appending a suffix to a city name.
LOCATIVE = {
    "Warszawa": "Warszawie", "Kraków": "Krakowie", "Łódź": "Łodzi", "Wrocław": "Wrocławiu",
    "Poznań": "Poznaniu", "Gdańsk": "Gdańsku", "Szczecin": "Szczecinie", "Lublin": "Lublinie",
}
CASES = (
    ("kardiologiczna", "nadciśnienie tętnicze samoistne",
     "Wizyta kontrolna w celu oceny ciśnienia tętniczego. "
     "Omówiono wyniki pomiarów wykonywanych w domu oraz pomiaru w gabinecie.",
     "Dalsze prowadzenie dzienniczka pomiarów ciśnienia i przedstawienie go podczas kolejnej wizyty."),
    ("diabetologiczna", "cukrzyca typu 2",
     "Wizyta kontrolna w celu oceny wyrównania glikemii. "
     "Przeanalizowano zapisy w dzienniczku samokontroli.",
     "Kontynuacja samokontroli glikemii. Na kolejną wizytę należy przynieść dzienniczek pomiarów."),
    ("neurologiczna", "rwa kulszowa",
     "Wizyta kontrolna w celu oceny przebiegu dolegliwości. "
     "W badaniu stwierdzono poprawę ruchomości w porównaniu z poprzednią wizytą.",
     "Unikanie przeciążeń. Ponowna konsultacja w razie utrzymywania się dolegliwości."),
)

TEMPLATES = (
    ("clinical", """INFORMACJA Z KONSULTACJI LEKARSKIEJ
{hospital}
Poradnia {ward}
Data wizyty: {date}

Imię i nazwisko: {patient}
PESEL: {pesel}
Data urodzenia: {dob}; płeć: {sex}
Adres zamieszkania: {address}
Telefon: {phone}

Rozpoznanie: {condition}.
Przebieg konsultacji: {history}
Postępowanie: podczas dzisiejszej wizyty nie wprowadzono zmian w leczeniu.
Zalecenia: {plan}
Informację wydano w celu przekazania lekarzowi podstawowej opieki zdrowotnej.

Lekarz: {sender}
Podpis i pieczątka: ____________"""),
    ("legal", """UMOWA O ŚWIADCZENIE USŁUG
Nr {number}, zawarta w dniu {date}

§ 1. Strony
Wykonawca: {company}
Siedziba i adres: {address2}
NIP: {nip}; REGON: {regon}
Osoba reprezentująca wykonawcę: {sender}
Rachunek do zapłaty: {iban}

Zamawiający: {patient}
PESEL: {pesel}
Adres zamieszkania: {address}
Telefon: {phone}; e-mail: {email}

§ 2. Przedmiot i termin wykonania
Wykonawca zobowiązuje się skonfigurować połączenie internetowe i drukarkę na jednym
komputerze zamawiającego, pod wskazanym wyżej adresem zamieszkania. Usługa zostanie
wykonana w ciągu pięciu dni roboczych od zawarcia umowy, w godzinach uzgodnionych przez strony.

§ 3. Wynagrodzenie i odbiór
Łączne wynagrodzenie wynosi 250 zł brutto. Zapłata nastąpi przelewem na rachunek
wykonawcy w ciągu pięciu dni roboczych od otrzymania faktury. Po zakończeniu prac
strony sprawdzą działanie połączenia i wykonają wydruk próbny, a wynik odnotują
w protokole odbioru. Wady wykonanej usługi zostaną usunięte bez dodatkowych opłat
w ciągu trzech dni roboczych od ich zgłoszenia.

Umowę sporządzono w dwóch jednobrzmiących egzemplarzach, po jednym dla każdej ze stron.
Wykonawca: ____________    Zamawiający: ____________"""),
    ("legal", """OŚWIADCZENIE
w sprawie adresu do korespondencji

Ja, {nizej} {patient}, PESEL {pesel}, oświadczam, że moim adresem
zamieszkania jest: {address}.
Proszę o kierowanie na ten adres korespondencji dotyczącej wniosku o wydanie kopii
dokumentów z akt sprawy nr {number}. Zobowiązuję się pisemnie poinformować o zmianie
adresu do czasu rozpatrzenia wniosku.
Dane do kontaktu w razie pytań: telefon {phone}, e-mail {email}.

Data: {date}
Podpis: ____________"""),
    ("admin", """{company}
Dział obsługi klienta
Numer sprawy: {number}
Data: {date}

Adresat: {patient}
Adres do korespondencji: {address}
Dotyczy: potwierdzenia przyjęcia wniosku o wydanie kopii dokumentów

{salutation},

potwierdzamy przyjęcie {possessive} wniosku pod podanym wyżej numerem sprawy.
Wniosek przekazaliśmy do komórki przechowującej akta w celu odszukania wskazanych
dokumentów. O możliwości odbioru kopii poinformujemy pisemnie. Jeśli potrzebne
będą dodatkowe wyjaśnienia, skontaktujemy się, korzystając z danych podanych we wniosku.
Prosimy o podawanie numeru sprawy przy kontakcie dotyczącym jej przebiegu.

Osoba do kontaktu: {sender}
Telefon: {sender_phone}; e-mail: {sender_email}

Z poważaniem
Dział obsługi klienta"""),
)


def _adult(rng):
    while True:
        person = gen_person(rng)
        if 1950 <= int(person.dob[-4:]) <= 1995:
            return person


def _address(person):
    # Omit the v1 random postcode: its format alone does not establish city coherence.
    return f"{person.address.split(',')[0]}, {person.city}"


def _fields(rng: random.Random):
    patient = _adult(rng)
    sender = _adult(rng)
    while (sender.first_name, sender.last_name) == (patient.first_name, patient.last_name) or sender.phone == patient.phone:
        sender = _adult(rng)
    ward, condition, history, plan = rng.choice(CASES)
    male = patient.sex == "M"
    return {
        "patient": (f"{patient.first_name} {patient.last_name}", "PERSON"),
        "sender": (f"{sender.first_name} {sender.last_name}", "PERSON"),
        "pesel": (patient.pesel, "NATIONAL_ID"), "dob": (patient.dob, "DATE"),
        "sex": ("męska" if male else "żeńska", "O"),
        "nizej": ("niżej podpisany" if male else "niżej podpisana", "O"),
        "salutation": ("Szanowny Panie" if male else "Szanowna Pani", "O"),
        "possessive": ("Pana" if male else "Pani", "O"),
        "address": (_address(patient), "ADDRESS"), "address2": (_address(sender), "ADDRESS"),
        "phone": (patient.phone, "PHONE"), "sender_phone": (sender.phone, "PHONE"),
        "email": (_ascii(f"{patient.first_name}.{patient.last_name}").lower() + "@example.pl", "EMAIL"),
        "sender_email": (_ascii(f"{sender.first_name}.{sender.last_name}").lower() + "@example.pl", "EMAIL"),
        "iban": (sender.iban, "ACCOUNT_ID"),
        "nip": (gen_nip(rng), "COMPANY_ID"), "regon": (gen_regon9(rng), "COMPANY_ID"),
        "company": (rng.choice(("TechPlus sp. z o.o.", "Serwis Komputerowy sp. z o.o.", "Łącze sp. z o.o.")), "ORG_PARTY"),
        "hospital": (f"Centrum Medyczne {'we' if sender.city == 'Wrocław' else 'w'} {LOCATIVE[sender.city]}", "ORG_PARTY"),
        "ward": (ward, "O"), "condition": (condition, "HEALTH_CONDITION"),
        "history": (history, "O"), "plan": (plan, "O"),
        "number": (str(rng.randint(100, 9999)), "CASE_NUMBER"),
        "date": (f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.2025", "DATE"),
    }


pl_skeleton_v2_pack = LocalePack(
    language="pl", name="Polish real-skeleton v2", fields=_fields, templates=TEMPLATES,
    checksummed_ids=pl_skeleton_pack.checksummed_ids, family="A-v2", genre="official correspondence",
)


def generate_dataset(n: int, seed: int = 2026101278):
    for row in pl_skeleton_v2_pack.generate_dataset(n, seed):
        yield {**row, "country": "PL", "config": "pl-realskeleton-v2"}
