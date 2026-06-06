"""RES-19: harder, *discriminating* held-out general eval — ≥2 independent template families/language.

**Why this exists.** The KLU-106 kp-deid v2 scorecard used a *single* held-out general template per
language. That skeleton was so unambiguous (capitalised name after a fixed lead-in, ``@``-email, IBAN
prefix, fixed-position fields) that the zero-shot control already scored entity-F1 ≈ 1.000 on
de/fr/nl/pl/ro (0.999 es). With the control pinned at the ceiling, the ``v2 − control`` Δ is
structurally ≈ 0 and the eval **cannot discriminate** a breadth/finetune gain (only ``it``, whose
control sat at 0.865, showed a CI-clearing gain). That is an eval-design limitation, not a model
result.

**What this module builds.** For every one of the 8 languages, **two independent template families**
(mirroring the RO real-skeleton Family-A/B approach, KLU-101):

* **Family A — bureaucratic form / record card**: fielded layout, terse labels, register of an
  administrative record. PII sits in *non-fixed positions* (sometimes mid-line, sometimes after a
  colon, sometimes parenthetical), with *varied lead-ins* per slot.
* **Family B — narrative correspondence / case note**: running prose, mixed register, PII embedded
  inside sentences with no fixed cue word — the surface a saturated single-template eval never tests.

Both families **reuse each locale's existing ``_fields`` builder** (so PII generators, checksum
validity, and KP labels are byte-identical to the trained ``*-synthetic`` tracks) and run through the
shared ``localepack.fill_document`` splice → byte-equality assert → strict ``char_spans_to_bioes`` gate,
so spans are offset-correct **by construction**.

**Independence is hard-gated** (see ``tests/test_hardgeneral_families.py``), not eyeballed:
  1. token 5-gram Jaccard overlap **≤ 0.10** between Family A and Family B (per language);
  2. token 5-gram Jaccard overlap **≤ 0.10** between EACH new family and the *original* training
     ``*_documents.TEMPLATES`` skeletons — so the new families are template-disjoint from training and
     therefore inherently held-out (the trained models never saw these skeletons).

This is a **detection-eval-quality fix**, not a re-id claim: the real-skeleton tracks remain the
headline re-id signal. Fully synthetic, cleanly-licensed; ``config_status=dev``, contamination-clean.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from .localepack import LocalePack

# Per-language NATIONAL_ID and COMPANY_ID slot names (as defined by each locale's _fields builder).
# person/address/date/email/iban/phone are uniform across every locale; only the id slots differ.
_NID_SLOT = {
    "ro": "cnp", "en": "nino", "de": "steuerid", "fr": "nir",
    "es": "dni", "it": "cf", "nl": "bsn", "pl": "pesel",
}
_ORGID_SLOT = {
    "ro": "cui", "de": "ustid", "fr": "siren", "it": "piva", "nl": "kvk", "pl": "nip",
    # en/es have no separate company-registration id slot in _fields.
}

# --------------------------------------------------------------------------- #
# Per-language template families.
#
# Each entry: lang -> {"A": (genre, [(domain, template), ...]),
#                      "B": (genre, [(domain, template), ...])}.
# Slot placeholders use {nid}/{orgid} — substituted to the locale's real slot name at pack-build time
# (so we author once per language and the id generators/labels come straight from the locale _fields).
#
# Hardening levers (vs the single saturated KLU-106 template):
#   * non-fixed PII position (line-initial, mid-sentence, parenthetical, end-of-line);
#   * varied/absent lead-in cues (no single "CNP {x}" style giveaway);
#   * mixed register between the two families (terse form vs running prose);
#   * disjoint boilerplate wording (5-gram Jaccard ≤ 0.10, gated).
# --------------------------------------------------------------------------- #
_FAMILIES: dict[str, dict[str, tuple[str, list[tuple[str, str]]]]] = {
    "ro": {
        "A": ("fișă de evidență administrativă", [
            ("admin", "FIȘĂ DOSAR\nTitular .......... {person}\nCod numeric .......... {nid}\n"
                      "Reședință .......... {address}\nDeschis la .......... {date}"),
            ("admin", "REGISTRU INTRĂRI — poziția curentă\n{person} | contact {phone} | {email}\n"
                      "cont virament {iban} — operațiune înregistrată {date}"),
            ("legal", "ÎMPUTERNICIRE\nMandant: {person} ({nid})\nMandatar plăți cont {iban}\n"
                      "Firma reprezentată — cod fiscal {orgid}. Întocmit {date}."),
        ]),
        "B": ("notă narativă / corespondență", [
            ("general", "Bună ziua, sunt {person} și v-am scris săptămâna trecută; mă găsiți "
                        "tot la {phone} sau pe {email} dacă e mai comod."),
            ("clinical", "La revenire în {date} pacientul, domnul {person}, locuia încă pe {address} "
                         "și ne-a lăsat codul {nid} pentru dosarul de internare."),
            ("legal", "Am convenit ca suma să meargă în {iban}; restul detaliilor despre {person} "
                      "le discutăm când treceți, nu le mai notez aici."),
        ]),
    },
    "en": {
        "A": ("administrative record card", [
            ("admin", "CASE RECORD\nName ............ {person}\nNI no ........... {nino}\n"
                      "Address ......... {address}\nOpened .......... {date}"),
            ("admin", "INTAKE LOG (current row)\n{person} | tel {phone} | {email}\n"
                      "transfer to {iban} — logged {date}"),
            ("legal", "POWER OF ATTORNEY\nGrantor: {person} ({nino})\nPayments to {iban}\n"
                      "Counterparty {company}. Executed {date}."),
        ]),
        "B": ("narrative correspondence / case note", [
            ("general", "Hi, it's {person} again — easiest to reach me on {phone}, or drop a line "
                        "to {email} and I'll get back to you."),
            ("clinical", "When we followed up on {date} the gentleman, {person}, was still living at "
                         "{address}, and he left {nino} for the admission file."),
            ("legal", "We agreed the balance goes to {iban}; the rest of what concerns {person} we'll "
                      "sort out in person, no point writing it down here."),
        ]),
    },
    "de": {
        "A": ("behördliche Karteikarte", [
            ("admin", "FALLAKTE\nName ........... {person}\nSteuer-IdNr .... {steuerid}\n"
                      "Anschrift ...... {address}\nAngelegt ....... {date}"),
            ("admin", "EINGANGSLISTE (laufende Zeile)\n{person} | Tel {phone} | {email}\n"
                      "Überweisung an {iban} — erfasst {date}"),
            ("legal", "VOLLMACHT\nVollmachtgeber: {person} ({steuerid})\nZahlungen auf {iban}\n"
                      "Vertragspartner {company}. Ausgefertigt {date}."),
        ]),
        "B": ("erzählender Schriftwechsel / Vermerk", [
            ("general", "Hallo, hier ist {person} — am besten erreichen Sie mich unter {phone}, "
                        "oder schreiben Sie kurz an {email}, ich melde mich."),
            ("clinical", "Beim Nachtermin am {date} wohnte der Herr, {person}, noch in {address} und "
                         "hinterließ {steuerid} für die Aufnahmeakte."),
            ("legal", "Wir waren uns einig, dass der Restbetrag auf {iban} geht; alles Weitere zu "
                      "{person} klären wir persönlich, das notiere ich hier nicht."),
        ]),
    },
    "fr": {
        "A": ("fiche administrative", [
            ("admin", "DOSSIER\nNom ............ {person}\nNo NIR ......... {nir}\n"
                      "Adresse ........ {address}\nOuvert le ...... {date}"),
            ("admin", "REGISTRE D'ENTRÉE (ligne courante)\n{person} | tél {phone} | {email}\n"
                      "virement vers {iban} — enregistré {date}"),
            ("legal", "PROCURATION\nMandant : {person} ({nir})\nPaiements sur {iban}\n"
                      "Partie représentée {company}. Établi le {date}."),
        ]),
        "B": ("correspondance narrative / note", [
            ("general", "Bonjour, c'est de nouveau {person} — le plus simple est de m'appeler au "
                        "{phone}, ou un mot à {email} et je vous réponds."),
            ("clinical", "Lors du suivi du {date}, le monsieur, {person}, habitait toujours {address} "
                         "et nous a laissé {nir} pour le dossier d'admission."),
            ("legal", "Nous étions convenus que le solde irait sur {iban} ; le reste concernant "
                      "{person}, on le règle de vive voix, je ne le note pas ici."),
        ]),
    },
    "es": {
        "A": ("ficha administrativa", [
            ("admin", "EXPEDIENTE\nNombre ......... {person}\nDNI ............ {dni}\n"
                      "Domicilio ...... {address}\nAbierto ........ {date}"),
            ("admin", "REGISTRO DE ENTRADA (línea actual)\n{person} | tel {phone} | {email}\n"
                      "transferencia a {iban} — anotado {date}"),
            ("legal", "PODER\nPoderdante: {person} ({dni})\nPagos a {iban}\n"
                      "Parte representada {company}. Otorgado {date}."),
        ]),
        "B": ("correspondencia narrativa / nota", [
            ("general", "Hola, soy {person} otra vez — lo más fácil es llamarme al {phone}, o "
                        "escribir a {email} y le contesto."),
            ("clinical", "En la revisión del {date} el señor, {person}, seguía viviendo en {address} "
                         "y nos dejó {dni} para la ficha de ingreso."),
            ("legal", "Acordamos que el resto iría a {iban}; lo demás sobre {person} lo arreglamos "
                      "en persona, aquí no lo apunto."),
        ]),
    },
    "it": {
        "A": ("scheda amministrativa", [
            ("admin", "FASCICOLO\nNome .......... {person}\nCodice fiscale  {cf}\n"
                      "Indirizzo ..... {address}\nAperto il ..... {date}"),
            ("admin", "REGISTRO INGRESSI (riga corrente)\n{person} | tel {phone} | {email}\n"
                      "bonifico verso {iban} — annotato {date}"),
            ("legal", "PROCURA\nMandante: {person} ({cf})\nPagamenti su {iban}\n"
                      "Parte rappresentata {company}. Redatto {date}."),
        ]),
        "B": ("corrispondenza narrativa / nota", [
            ("general", "Salve, sono di nuovo {person} — il modo più semplice è chiamarmi al {phone}, "
                        "oppure due righe a {email} e le rispondo."),
            ("clinical", "Al controllo del {date} il signore, {person}, abitava ancora in {address} "
                         "e ci ha lasciato {cf} per la cartella di ricovero."),
            ("legal", "Avevamo concordato che il saldo andasse su {iban}; il resto che riguarda "
                      "{person} lo sistemiamo di persona, qui non lo scrivo."),
        ]),
    },
    "nl": {
        "A": ("administratieve kaart", [
            ("admin", "DOSSIER\nNaam .......... {person}\nBSN ........... {bsn}\n"
                      "Adres ......... {address}\nGeopend ....... {date}"),
            ("admin", "INTAKELIJST (huidige regel)\n{person} | tel {phone} | {email}\n"
                      "overboeking naar {iban} — vastgelegd {date}"),
            ("legal", "VOLMACHT\nVolmachtgever: {person} ({bsn})\nBetalingen op {iban}\n"
                      "Tegenpartij {company}. Opgemaakt {date}."),
        ]),
        "B": ("verhalende correspondentie / notitie", [
            ("general", "Hallo, met {person} weer — u bereikt me het makkelijkst op {phone}, of een "
                        "berichtje naar {email} en ik kom erop terug."),
            ("clinical", "Bij de nacontrole op {date} woonde meneer, {person}, nog op {address} en "
                         "liet {bsn} achter voor het opnamedossier."),
            ("legal", "We waren het erover eens dat het restant naar {iban} gaat; de rest over "
                      "{person} regelen we persoonlijk, dat noteer ik hier niet."),
        ]),
    },
    "pl": {
        "A": ("karta ewidencyjna", [
            ("admin", "AKTA SPRAWY\nNazwisko ...... {person}\nPESEL ......... {pesel}\n"
                      "Adres ......... {address}\nZałożono ...... {date}"),
            ("admin", "REJESTR WPŁYWÓW (bieżący wiersz)\n{person} | tel {phone} | {email}\n"
                      "przelew na {iban} — zapisano {date}"),
            ("legal", "PEŁNOMOCNICTWO\nMocodawca: {person} ({pesel})\nPłatności na {iban}\n"
                      "Strona reprezentowana {company}. Sporządzono {date}."),
        ]),
        "B": ("korespondencja narracyjna / notatka", [
            ("general", "Dzień dobry, to znów {person} — najłatwiej złapać mnie pod {phone}, albo "
                        "proszę napisać na {email}, odezwę się."),
            ("clinical", "Na wizycie kontrolnej {date} pan, {person}, mieszkał jeszcze przy {address} "
                         "i zostawił {pesel} do akt przyjęcia."),
            ("legal", "Ustaliliśmy, że reszta pójdzie na {iban}; resztę dotyczącą {person} omówimy "
                      "osobiście, tutaj tego nie zapisuję."),
        ]),
    },
}


def _materialise(lang: str, templates: list[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """Substitute the generic {nid}/{orgid} placeholders with the locale's real _fields slot names."""
    nid, orgid = _NID_SLOT[lang], _ORGID_SLOT.get(lang, "")
    out: list[tuple[str, str]] = []
    for domain, t in templates:
        t = t.replace("{nid}", "{" + nid + "}")
        if orgid:
            t = t.replace("{orgid}", "{" + orgid + "}")
        out.append((domain, t))
    return tuple(out)


def _locale_fields(lang: str):
    mod = __import__(f"klusai.privacy.datasets.data.{lang}_documents", fromlist=["_fields"])
    return mod._fields


def hard_general_pack(lang: str, family: str) -> LocalePack:
    """Build a held-out hard-general LocalePack for ``lang`` and template ``family`` ("A"/"B").

    Reuses the locale's real ``_fields`` builder (same checksum-valid generators + KP labels as the
    trained ``*-synthetic`` track), so only the *skeleton wording / PII position* differs — which is
    exactly the held-out axis (template-disjoint from training, gated)."""
    genre, templates = _FAMILIES[lang][family]
    return LocalePack(
        language=lang,
        name=f"{lang} hard-general family {family} ({genre})",
        checksummed_ids=(),  # PII generators (and their self-tests) are owned by the *_documents pack
        fields=_locale_fields(lang),
        templates=_materialise(lang, templates),
        family=family,
        genre=genre,
    )


LANGUAGES: tuple[str, ...] = tuple(_FAMILIES.keys())
FAMILIES: tuple[str, ...] = ("A", "B")


def generate_hard_general(
    lang: str, n_per_family: int, seed: int = 0
) -> Iterator[dict]:
    """Yield ``2 * n_per_family`` rows for ``lang``: family A then family B, each tagged ``family``.

    Distinct per-family seeds so the two PII streams never coincide (subject-disjoint by construction
    on top of the near-unique checksum-valid national IDs)."""
    yield from hard_general_pack(lang, "A").generate_dataset(n_per_family, seed=seed)
    yield from hard_general_pack(lang, "B").generate_dataset(n_per_family, seed=seed + 10_000)


# --------------------------------------------------------------------------- #
# RES-19 independence gate: token 5-gram Jaccard overlap on PII-masked skeletons.
# Two gates: (1) family A vs family B (per language); (2) each new family vs the ORIGINAL training
# *_documents.TEMPLATES (template-disjoint-from-training → inherently held-out). Both ≤ 0.10.
# --------------------------------------------------------------------------- #
_SLOT_RE = re.compile(r"\{[a-z0-9_]+\}")


def _masked_tokens(template: str) -> list[str]:
    """Tokenize a template's FIXED text with every PII ``{slot}`` collapsed to a ``§`` mask.

    Masking the slots compares *skeleton boilerplate wording* (authored prose / layout), not the
    synthetic PII values — the same definition the KLU-101 RO gate uses."""
    masked = _SLOT_RE.sub(" § ", template)
    return [t for t in re.findall(r"§|\w+", masked.lower())]


def _five_grams(templates) -> set[tuple[str, ...]]:
    grams: set[tuple[str, ...]] = set()
    for _domain, t in templates:
        toks = _masked_tokens(t)
        grams.update(tuple(toks[i:i + 5]) for i in range(len(toks) - 4))
    return grams


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def family_5gram_jaccard(lang: str) -> float:
    """5-gram Jaccard overlap between Family A and Family B masked skeletons for ``lang`` (≤ 0.10)."""
    a = _five_grams(_materialise(lang, _FAMILIES[lang]["A"][1]))
    b = _five_grams(_materialise(lang, _FAMILIES[lang]["B"][1]))
    return _jaccard(a, b)


def _training_template_5grams(lang: str) -> set[tuple[str, ...]]:
    """5-grams of the ORIGINAL training ``*_documents.TEMPLATES`` skeletons for ``lang``."""
    mod = __import__(f"klusai.privacy.datasets.data.{lang}_documents", fromlist=["TEMPLATES"])
    return _five_grams(mod.TEMPLATES)


def vs_training_5gram_jaccard(lang: str, family: str) -> float:
    """5-gram Jaccard overlap between a new family's skeletons and the training templates (≤ 0.10).

    Low overlap is the falsifiable evidence that these families are *template-disjoint from training*,
    so the trained v2 (and control) models never saw these skeletons — the eval is inherently held-out.
    """
    fam = _five_grams(_materialise(lang, _FAMILIES[lang][family][1]))
    return _jaccard(fam, _training_template_5grams(lang))
