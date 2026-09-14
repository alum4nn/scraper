"""Erkennung deutscher Personennamen (Impressum, Team-Seiten, Telefon-Zuordnung)."""

from __future__ import annotations

import re

from leadscraper.extract.vornamen import is_known_first_name

_TITLE = (
    r"(?:Prof\.|Dr\.|Dipl\.-\w+\.|Dipl\.\s?\w+\.?|Mag\.|Ing\.|MBA|LL\.M\.|B\.A\.|M\.A\.|B\.Sc\.|M\.Sc\.|"
    r"M\.Eng\.|B\.Eng\.|RA|StB|WP|vBP|med\.|dent\.|vet\.|rer\.\s?\w+\.|jur\.|phil\.|h\.c\.|mult\.|Dres\.)"
)
_PARTICLE = r"(?:von|van|de|der|den|zu|zur|da|di|del|dos|le|la|el|und zu|von der|van der|van den)"
_TOKEN = r"[A-ZÄÖÜ][a-zäöüßé]+(?:-[A-ZÄÖÜ][a-zäöüßé]+)*"
_INITIAL = r"[A-ZÄÖÜ]\."

NAME_RE: re.Pattern[str] = re.compile(
    rf"(?<![\w-])(?:(?:Herrn?|Frau)\s+)?(?:{_TITLE}\s+)*"
    rf"(?:{_TOKEN}|{_INITIAL})(?:\s+(?:{_PARTICLE}\s+)?(?:{_TOKEN}|{_INITIAL})){{1,3}}(?![\w-])"
)
_TITLE_RE = re.compile(rf"^(?:{_TITLE}\s+)+")
_SALUTATION_RE = re.compile(r"^(?:Herrn?|Frau|Hr\.|Fr\.)\s+", re.IGNORECASE)
_PARTICLES = set(_PARTICLE.strip("(?:)").split("|")) | {"und"}
# Berufs-/Rollenwörter, die wie Namen aussehen ("Leitung Personal", "Anna Meister" verliert bewusst)
_ROLE_SUFFIX = re.compile(
    r"(leitung|leiter|leiterin|berater|beraterin|beratung|manager|managerin|kaufmann|kauffrau|assistenz|"
    r"assistent|assistentin|abteilung|verwaltung|verwalter|verwalterin|makler|maklerin|buchhalter|buchhalterin|"
    r"buchhaltung|sachbearbeiter|sachbearbeiterin|techniker|technikerin|mechaniker|meister|meisterin|monteur|"
    r"planer|planerin|designer|designerin|entwickler|entwicklerin|betreuer|betreuerin|anwalt|anwältin|anwaelte|"
    r"ärztin|arzt|therapeut|therapeutin|spezialist|spezialistin|experte|expertin|direktor|direktorin|"
    r"vorsitzender|vorsitzende|mitarbeiter|mitarbeiterin|gesellschafter|gesellschafterin|führung|fuehrung|"
    r"führer|führerin|inhaber|inhaberin|personal|marketing|vertrieb|verkauf|einkauf|controlling|sekretariat|"
    r"empfang|rezeption|disposition|logistik|produktion|werkstatt|azubi|auszubildende|auszubildender|praktikant|"
    r"praktikantin|werkstudent|werkstudentin|student|studentin|trainee|volontär|volontärin|referent|referentin|"
    r"koordinator|koordinatorin|consultant|partner|partnerin|prokurist|prokuristin|vorstand|aufsichtsrat)$",
    re.I,
)
_STREET_SUFFIX = re.compile(
    r"(straße|strasse|str\.?|weg|platz|allee|gasse|ring|damm|ufer|chaussee|steig)$", re.I
)
# Abstrakta/Substantive, die nie Namen sind („Wohnflächenberechnung“, „Kompetenz“, „Präsentation“);
# „-ung“ nur ab 9 Zeichen, damit Nachnamen wie Jung/Hartung bleiben.
_NOUN_SUFFIX = re.compile(
    r"(heit|keit|schaft|schaften|tion|tionen|ität|ismus|ierung|ungen|thek)$|^.{6,}ung$", re.I
)
# Firmen- und Gewerbebezeichnungen: „Elektrotechnik Alexander Tibelius“ ist eine Partnerfirma, kein
# Mitarbeiter. Solche Wörter tauchen in Handwerker- und Netzwerklisten neben echten Namen auf.
_TRADE_SUFFIX = re.compile(
    r"(technik|büro|buero|service|dienst|dienste|bau|werk|werke|handel|kanzlei|praxis|zentrum|center|"
    r"factory|company|systems|solutions|consulting|immobilien|makler|verwaltung|group|gruppe|team|"
    r"studio|agentur|montage|logistik|transport|reinigung|entsorgung|gerüstbau|energie|betrieb|"
    r"betriebe|meisterbetrieb|fachbetrieb|manufaktur|kontor|partners|projekte)$",
    re.I,
)

STOPWORDS: frozenset[str] = frozenset(
    w.lower()
    for w in """
    Geschäftsführer Geschäftsführerin Geschäftsführung Geschäftsführende Geschäftsführender Gesellschafter
    Gesellschafterin Inhaber Inhaberin Vorstand Vorstandsvorsitzender Vorstandsvorsitzende Aufsichtsrat
    Prokurist Prokuristin Partner Partnerin Vertreten Vertretungsberechtigt Vertretungsberechtigter
    Vertretungsberechtigte Verantwortlich Verantwortlicher Verantwortliche Ansprechpartner Ansprechpartnerin
    Impressum Kontakt Telefon Telefax Fax Mobil Mobile Handy WhatsApp Mail E-Mail Email Web Internet Homepage
    Straße Strasse Weg Platz Allee Gasse Ring Damm Ufer Hausnummer Postfach
    GmbH KG AG UG OHG GbR SE eG mbH Co Cie Holding Group Gruppe Verwaltungs Beteiligungs Immobilien Immobilie
    Makler Maklerin Hausverwaltung Verwaltung Vertrieb Verkauf Vermietung Beratung Berater Beraterin
    Amtsgericht Registergericht Handelsregister Umsatzsteuer Umsatzsteuer-ID Steuernummer Registernummer
    Montag Dienstag Mittwoch Donnerstag Freitag Samstag Sonntag Januar Februar März April Mai Juni Juli August
    September Oktober November Dezember Uhr Öffnungszeiten Sprechzeiten Bürozeiten Termine Termin
    Datenschutz Datenschutzerklärung Rechte Alle Haftung Haftungsausschluss Inhalte Links Urheberrecht
    Bildnachweis Quelle Hinweis Hinweise Streitschlichtung Verbraucherstreitbeilegung Berufsbezeichnung
    Berufsordnung Kammer Aufsichtsbehörde Zuständige Zuständig Mitglied Sitz Standort Standorte Filiale
    Niederlassung Büro Zentrale Service Kunden Kunde Team Unser Unsere Unserem Unseren Ihr Ihre Ihrem Ihren
    Ihres Ihnen Sie Wir Uns Über Herzlich Willkommen Startseite Home Aktuelles News Blog Ratgeber Karriere
    Jobs
    Stellenangebote Stellen Ausbildung Praktikum Werkstudent Unternehmen Firma Gesellschaft Deutschland
    Europa Nord Süd West Ost Mitte Stadt Land Kreis Landkreis Region Hauptbahnhof Bahnhof Zentrum Park Markt
    Wohnung Wohnungen Haus Häuser Grundstück Grundstücke Objekt Objekte Exposé Neubau Bestand Kauf Miete
    Mietwohnung Eigentumswohnung Einfamilienhaus Mehrfamilienhaus Gewerbe Investment Finanzierung Bewertung
    Wertermittlung Marktbericht Referenzen Leistungen Leistung Angebot Angebote Anfrage Kontaktformular
    Newsletter Presse Downloads Login Suche Menü Navigation Seite Seiten Weiter Zurück Mehr Erfahren Jetzt
    Anrufen Schreiben Senden Absenden Nachricht Betreff Name Vorname Nachname Adresse Anschrift Ort PLZ
    Der Die Das Und Oder Mit Für Von Am An Im In Zum Zur Auf Bei Aus Nach Vor Seit Bis Als Wie Ein Eine Einer
    Sehr Geehrte Geehrter Damen Herren Liebe Lieber Guten Tag Morgen Abend Hallo Grüße Freundliche Beste
    Berlin Hamburg München Köln Frankfurt Stuttgart Düsseldorf Dortmund Essen Leipzig Bremen Dresden Hannover
    Nürnberg Duisburg Bochum Wuppertal Bielefeld Bonn Münster Karlsruhe Mannheim Augsburg Wiesbaden
    Gelsenkirchen Braunschweig Aachen Kiel Chemnitz Halle Magdeburg Freiburg Krefeld Mainz Lübeck Erfurt
    Oberhausen Rostock Kassel Hagen Saarbrücken Potsdam Hamm Ludwigshafen Oldenburg Mülheim Osnabrück
    Leverkusen Heidelberg Darmstadt Solingen Regensburg Herne Paderborn Neuss Ingolstadt Offenbach Fürth Ulm
    Würzburg Heilbronn Pforzheim Wolfsburg Göttingen Bottrop Reutlingen Koblenz Bremerhaven Recklinghausen
    Jena Remscheid Trier Erlangen Moers Siegen Hildesheim Salzgitter Cottbus Bayern Hessen Sachsen Thüringen
    Brandenburg Niedersachsen Westfalen Nordrhein Nordrhein-Westfalen Rheinland Rheinland-Pfalz Pfalz
    Baden Baden-Württemberg Württemberg Schleswig Schleswig-Holstein Holstein Saarland Mecklenburg
    Mecklenburg-Vorpommern Vorpommern Sachsen-Anhalt Anhalt Rhein Main Ruhr Neckar Elbe Donau Weser Mosel
    Bodensee Allgäu Eifel Sauerland Bergisch Gladbach Taunus Odenwald Harz
    Österreich Schweiz Wien Zürich
    Mein Meine Dein Deine Konto Formular Neues Neue Neuer Fotos Foto Backoffice Kontaktart Bevorzugte
    Stadtbezirk Häufige Fragen Frage Cookie Cookies Analytics Google Vimeo Youtube Videos Video Database
    Previous Next Contact Free Text Premium Angabe Angaben Hauptsitz Standortleitung Eigentümer Verkäufer
    Käufer Interessenten
    """.split()
)


def _tokens(s: str) -> list[str]:
    return [t for t in s.replace(",", " ").split() if t]


def normalize_name(s: str) -> str:
    s = " ".join(s.split())
    s = _SALUTATION_RE.sub("", s)
    s = _TITLE_RE.sub("", s)
    # Titel auch mitten im Namen (z. B. "Max Dr. Muster") sind selten – nur Anfang behandeln
    return s.strip(" ,;:")


def _core_tokens(s: str) -> list[str]:
    """Name-Tokens ohne Anrede/Titel/Partikel-Kleinschreibung."""
    return [t for t in _tokens(normalize_name(s)) if t.lower() not in _PARTICLES]


def is_probable_person_name(s: str) -> bool:
    if not s or len(s) > 60 or any(ch.isdigit() for ch in s) or "@" in s:
        return False
    tokens = _core_tokens(s)
    if not 2 <= len(tokens) <= 4:
        return False
    for tok in tokens:
        if tok.lower().strip(".") in STOPWORDS:
            return False
        if _STREET_SUFFIX.search(tok) or _ROLE_SUFFIX.search(tok) or _NOUN_SUFFIX.search(tok):
            return False
        if _TRADE_SUFFIX.search(tok):
            return False
        if len(tok) > 3 and tok.isupper():
            return False
        if not (re.fullmatch(_TOKEN, tok) or re.fullmatch(_INITIAL, tok)):
            return False
    # Mindestens ein "richtiges" Wort ≥ 2 Zeichen am Ende (Nachname)
    return len(tokens[-1].rstrip(".")) >= 2 and not re.fullmatch(_INITIAL, tokens[-1])


def _trim(candidate: str) -> str | None:
    """Stoppwörter am Rand entfernen (z. B. 'Thomas Berger Geschäftsführer' → 'Thomas Berger')."""
    toks = _tokens(candidate)
    while toks and (toks[0].lower().strip(".") in STOPWORDS or _SALUTATION_RE.match(toks[0] + " ")):
        toks.pop(0)
    while toks and toks[-1].lower().strip(".") in STOPWORDS:
        toks.pop()
    if not toks:
        return None
    return " ".join(toks)


def is_plausible_person_name(s: str) -> bool:
    """Strenger als is_probable_person_name: zusätzlich bekannter Vorname oder Anrede/Titel.

    Für Kontexte ohne Rollen-Label (Team-Karten ohne Funktion, Nummern-Zuordnung, Zähler für die
    Teamgröße), in denen „Bevorzugte Kontaktart“ oder „Stadtbezirk Hörde“ sonst als Person durchgehen.
    """
    if not is_probable_person_name(s):
        return False
    stripped = s.strip()
    if _SALUTATION_RE.match(stripped) or _TITLE_RE.match(_SALUTATION_RE.sub("", stripped)):
        return True
    toks = _core_tokens(s)
    if is_known_first_name(toks[0]):
        return True
    return len(toks) >= 3 and is_known_first_name(toks[1])


def find_plausible_names(text: str) -> list[str]:
    """Wie find_names, nur plausible Personen; eine Anrede im Text („Herr Yüksel Turan“) zählt als Beleg."""
    found: dict[str, str] = {}
    for m in NAME_RE.finditer(text):
        cand = _trim(m.group(0))
        if not cand or not is_probable_person_name(cand):
            continue
        if not (is_plausible_person_name(cand) or _SALUTATION_RE.match(m.group(0))):
            continue
        found.setdefault(normalize_name(cand).casefold(), cand)
    return list(found.values())


def find_names(text: str) -> list[str]:
    found: dict[str, str] = {}
    for m in NAME_RE.finditer(text):
        cand = _trim(m.group(0))
        if not cand or not is_probable_person_name(cand):
            continue
        key = normalize_name(cand).casefold()
        found.setdefault(key, cand)
    return list(found.values())


def surname(s: str) -> str:
    toks = [t for t in _core_tokens(s) if t.lower().rstrip(".") not in ("jun", "sen", "jr", "sr")]
    return toks[-1] if toks else ""
