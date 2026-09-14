"""Personen + Rollen auf Team-/Kontakt-/Ansprechpartner-Seiten; Zusammenführen von Personen."""

from __future__ import annotations

import re

from leadscraper.extract.htmlutil import Link
from leadscraper.extract.names import (
    find_names,
    find_plausible_names,
    is_plausible_person_name,
    is_probable_person_name,
    normalize_name,
    surname,
)
from leadscraper.models import ROLE_PRIORITY, Person, PhoneNumber, RoleCategory

ROLE_PATTERNS: list[tuple[str, RoleCategory]] = [
    (
        r"geschäftsführ|geschaeftsfuehr|\bceo\b|managing\s+director|geschäftsleit|gründer|founder|geschäftsinhaber",
        "geschaeftsfuehrung",
    ),
    # „Eigentümer“ fehlt absichtlich: bei Maklern ist das die Kundengruppe („Für Eigentümer“), keine Rolle
    (r"inhaber(?!gef)|\bowner\b|einzelunternehmer", "inhaber"),  # nicht „inhabergeführt seit 1968“
    (r"vorstand|\bcfo\b|\bcoo\b|\bcto\b|\bcmo\b", "vorstand"),
    (
        r"personalleit|leitung\s+personal|leiter(?:in)?\s+personal|head\s+of\s+hr|hr[\s-]*(?:manager|leit|business|director|generalist)|human\s+resources|people\s*&?\s*culture|recruit|personalreferent|personalabteilung|personalwesen|personalmanagement|\bhr\b",
        "hr",
    ),
    (r"ausbildungsleit|ausbilder|weiterbildung|personalentwickl|talent\s+development|learning", "ausbildung"),
    (r"prokur", "prokura"),
    (
        r"betriebsleit|werkleit|niederlassungsleit|standortleit|filialleit|büroleit|bereichsleit",
        "betriebsleitung",
    ),
]
_ROLE_RES = [(re.compile(p, re.I), cat) for p, cat in ROLE_PATTERNS]
_ROLEISH_RE = re.compile(
    r"(leiter|leiterin|leitung|manager|managerin|assistenz|assistent|assistentin|berater|beraterin|makler|"
    r"maklerin|sachbearbeit|buchhalt|vertrieb|marketing|techniker|meister|monteur|auszubildende|azubi|"
    r"sekretariat|empfang|disposition|kaufmann|kauffrau|verwalter|verwalterin|verwaltung|immobilien|"
    r"steuerberater|rechtsanwalt|rechtsanwältin|wirtschaftsprüfer|architekt|ingenieur|projekt|kundenbetreu|"
    r"kundenberat|objektbetreu|hausmeister|partner|gesellschafter|mitarbeiter|team|abteilung|bereich|"
    r"consultant|specialist|expert|director|head\s+of|senior|junior|dipl\.|m\.sc|b\.sc|mba)",
    re.I,
)
_ANSPRECH_RE = re.compile(
    r"(?:ihr(?:e)?\s+)?(?:ansprechpartner(?:in)?|kontakt(?:person)?|ihr\s+makler|ihre\s+maklerin|beratung\s+durch|betreut\s+von)\s*:\s*(.+)$",
    re.I,
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_DECIDER_WORDS = (
    r"geschäftsführ(?:er(?:in)?|ung)|geschäftsleitung|inhaber(?:in)?|eigentümer(?:in)?|"
    r"vorstand|gründer(?:in)?|prokurist(?:in)?|betriebsinhaber(?:in)?"
)
# „Inhaber: Rainer Lang“ / „Geschäftsführer – Anna Schmidt“ (außerhalb des Impressums)
_ROLE_LABEL_LINE_RE = re.compile(rf"^\s*({_DECIDER_WORDS})\s*[:\-–]\s*(.+)$", re.I)
# „Seit 2007 ist Thomas Steffens Gründer und Inhaber der …“ / „Inhaberin Claudia Sonnenhof berät Sie“
_PROSE_AFTER_RE = re.compile(
    rf"({_DECIDER_WORDS})\s+(?:ist\s+|der\s+|des\s+)?([A-ZÄÖÜ][^,.;:()]{{2,40}})", re.I
)
_PROSE_BEFORE_RE = re.compile(
    rf"([A-ZÄÖÜ][^,.;:()]{{2,40}}?)\s+(?:ist|war|als)\s+(?:der\s+|die\s+)?({_DECIDER_WORDS})", re.I
)
# „Seit 2007 ist Thomas Steffens Gründer und Inhaber …“ – Name zwischen Hilfsverb und Funktion
_PROSE_MIDDLE_RE = re.compile(
    rf"\b(?:ist|war)\s+([A-ZÄÖÜ][^,.;:()]{{2,40}}?)\s+(?:der\s+|die\s+)?({_DECIDER_WORDS})", re.I
)
# Kontaktdaten in den Zeilen unter einem Namen (Team-Karte): E-Mail, Telefonnummer, Tel/Mobil-Label
_CONTACT_RE = re.compile(r"@|(?:\+49|\b0)[\d\s\-–/.()]{6,}\d|\b(?:tel|mobil|handy|fon|phone)\b", re.I)

# Abschnitte, in denen Namen stehen, die NICHT zur Belegschaft gehören: Kundenstimmen, Partnerlisten,
# freie Mitarbeiter, Gremien. Eine Stichprobe an echten Websites zeigte, dass hier die meisten
# Fehlzählungen entstehen (Rezensenten und Handwerkspartner wurden zu Mitarbeitenden).
_FREMDE_ABSCHNITTE_RE = re.compile(
    r"^(?:das\s+sagen\s+unsere\s+kunden|was\s+(?:unsere\s+)?kunden\s+sagen|kundenstimmen|"
    r"kundenmeinungen|(?:unsere\s+)?bewertungen|rezensionen|referenzen|erfahrungsberichte|testimonials?|"
    r"(?:unsere\s+)?(?:kooperations|netzwerk|vertriebs|premium|handwerks)?partner|partnernetzwerk|"
    r"(?:unser\s+)?netzwerk|kooperationen|handwerker|dienstleister|empfehlungen|"
    r"freie\s+(?:mitarbeiter|experten|berater)(?:\s*&?\s*berater)?|"
    r"beirat|aufsichtsrat|kuratorium|ehemalige|in\s+memoriam)\s*[:–-]?$",
    re.I,
)
# Abschnitte, die wieder zur Belegschaft zurückführen
_TEAM_ABSCHNITTE_RE = re.compile(
    r"^(?:unser\s+team|das\s+team|team|ihre?\s+ansprechpartner(?:in)?|ansprechpartner(?:in)?|"
    r"(?:unsere\s+)?mitarbeiter(?:innen)?|unsere\s+(?:makler|berater|experten|köpfe)|"
    r"geschäftsführung|geschäftsleitung|inhaber(?:in)?|kontakt|standort|büro|über\s+uns|wir\s+über\s+uns)"
    r"\s*[:–-]?$",
    re.I,
)
# Bewertungs-Widgets: die Namen daneben gehören Kunden, nicht dem Betrieb
_BEWERTUNGS_WIDGET_RE = re.compile(
    r"provenexpert|trustindex|trustpilot|gepostet\s+auf\s+google|profile\s+picture|"
    r"verifizierte?\s+bewertung|google[- ]?bewertung",
    re.I,
)
_ABSCHNITT_MAXLEN = 70


def _is_staff_context(lines: list[str]) -> list[bool]:
    """Für jede Zeile: Gehören hier genannte Menschen zur Belegschaft?

    Überschriften schalten den Kontext um. Ohne diese Unterscheidung landen Rezensenten aus dem
    Bewertungs-Widget und Handwerker aus der Partnerliste als Mitarbeitende in der Auswertung.
    """
    erlaubt: list[bool] = []
    aktuell = True
    for line in lines:
        kurz = line.strip()
        if len(kurz) <= _ABSCHNITT_MAXLEN:
            if _FREMDE_ABSCHNITTE_RE.match(kurz):
                aktuell = False
            elif _TEAM_ABSCHNITTE_RE.match(kurz):
                aktuell = True
        if _BEWERTUNGS_WIDGET_RE.search(line):
            aktuell = False
        erlaubt.append(aktuell)
    return erlaubt


def categorize_role(role_text: str | None) -> RoleCategory:
    if not role_text:
        return "sonstige"
    for pat, cat in _ROLE_RES:
        if pat.search(role_text):
            return cat
    return "sonstige"


def _is_roleish(line: str) -> bool:
    if len(line) > 80 or is_probable_person_name(line) or "@" in line or "http" in line.lower():
        return False
    if re.search(r"\d", _YEAR_RE.sub("", line)):
        return False
    words = line.split()
    if len(words) > 8 or (len(words) >= 4 and line.rstrip().endswith((".", "!", "?"))):
        return False  # ganzer Satz („Lädt unsere Bewertungen von …“), keine Funktionsbezeichnung
    return bool(categorize_role(line) != "sonstige" or _ROLEISH_RE.search(line))


def _contact_nearby(lines: list[str], idx: int) -> bool:
    return any(_CONTACT_RE.search(lines[j]) for j in range(idx + 1, min(idx + 4, len(lines))))


def _email_local_matches(local: str, person_name: str) -> bool:
    parts = [p for p in re.split(r"[._-]", local.lower()) if p]
    if len(parts) < 2:
        sn = surname(person_name).lower()
        return bool(parts) and parts[0] == sn
    toks = [t.lower() for t in normalize_name(person_name).split()]
    return any(p == surname(person_name).lower() for p in parts) and any(
        p == toks[0] or p == toks[0][:1] for p in parts
    )


def find_people(
    lines: list[str], links: list[Link], *, source_url: str | None, page_kind: str
) -> list[Person]:
    people: dict[str, Person] = {}
    staff_kontext = _is_staff_context(lines)

    def add(name: str, role: str | None) -> None:
        key = normalize_name(name).casefold()
        cat = categorize_role(role)
        if key in people:
            cur = people[key]
            if role and (
                cur.role is None or ROLE_PRIORITY.get(cat, 9) < ROLE_PRIORITY.get(cur.role_category, 9)
            ):
                cur.role, cur.role_category = role, cat
            return
        people[key] = Person(name=normalize_name(name), role=role, role_category=cat, source_url=source_url)

    for i, line in enumerate(lines):
        if not staff_kontext[i]:
            continue  # Kundenstimmen, Partnerliste, freie Mitarbeiter, Beirat
        if m := _ROLE_LABEL_LINE_RE.match(line):
            for name in find_plausible_names(m.group(2)):
                add(name, m.group(1).strip())
            continue
        for pat, name_group in ((_PROSE_AFTER_RE, 2), (_PROSE_BEFORE_RE, 1), (_PROSE_MIDDLE_RE, 1)):
            for m in pat.finditer(line):
                role = m.group(1 if name_group == 2 else 2).strip()
                for name in find_plausible_names(m.group(name_group)):
                    add(name, role)
        if m := _ANSPRECH_RE.search(line):
            for name in find_names(m.group(1)):
                role = None
                # Rolle ggf. hinter dem Namen ("Thomas Berger, Geschäftsführer")
                tail = m.group(1).split(name, 1)[-1].strip(" ,–-")
                if tail and _is_roleish(tail):
                    role = tail
                add(name, role)
            continue
        if not is_probable_person_name(line):
            continue
        role = None
        for j in (i + 1, i + 2):
            if j < len(lines) and _is_roleish(lines[j]):
                role = lines[j].strip()
                break
            if j < len(lines) and is_probable_person_name(lines[j]):
                break
        # Ohne Rollen-Label reicht die Namensform nicht („Bevorzugte Kontaktart“, „Stadtbezirk Hörde“):
        # bekannter Vorname/Anrede oder Kontaktdaten direkt darunter müssen den Menschen belegen.
        # „Inhabergeführtes Maklerbüro“ und „Erklärung zur Barrierefreiheit“ sehen aus wie Namen: ein
        # bekannter Vorname (oder Anrede/Titel) belegt die Person. Sonst braucht es eine Rolle UND
        # Kontaktdaten direkt darunter – und die Zeile selbst darf kein Berufs-/Abteilungsbegriff sein.
        if is_plausible_person_name(line):
            if role or page_kind in ("team", "kontakt"):
                add(line.strip(), role)
        elif role and _contact_nearby(lines, i) and not _ROLEISH_RE.search(line):
            add(line.strip(), role)

    # E-Mail-Adressen mit Namensbestandteilen zuordnen
    for link in links:
        if link.kind != "mailto":
            continue
        addr = link.href.split(":", 1)[1].split("?", 1)[0].strip().lower()
        local = addr.split("@", 1)[0]
        for person in people.values():
            if person.email is None and _email_local_matches(local, person.name):
                person.email = addr
                break
    return list(people.values())


_PERSON_PATH_SEGMENT_RE = re.compile(
    r"/(?:team|mitarbeiter|makler|berater|ansprechpartner)/[a-zäöü]+-[a-zäöü-]+/?$", re.I
)


def staff_from_links_and_images(
    links: list[Link], image_alts: list[str], *, source_url: str | None
) -> list[Person]:
    """Mitarbeitende, die nur als Link zur eigenen Unterseite oder als Bildunterschrift auftauchen.

    Team-Seiten bestehen oft aus Karten: ein Foto mit `alt="Anna Schmidt"` und ein Link auf
    `/team/anna-schmidt/`. Im Fließtext steht dann nichts – gezählt werden müssen sie trotzdem.
    """
    found: dict[str, Person] = {}

    def add(name: str) -> None:
        key = normalize_name(name).casefold()
        found.setdefault(key, Person(name=normalize_name(name), source_url=source_url))

    for link in links:
        if link.kind not in ("internal", "vcard"):
            continue
        for name in find_plausible_names(link.text or ""):
            add(name)
        match = _PERSON_PATH_SEGMENT_RE.search(link.href)
        if match:
            segment = match.group(0).rstrip("/").rsplit("/", 1)[-1]
            kandidat = " ".join(teil.capitalize() for teil in segment.split("-") if teil)
            for name in find_plausible_names(kandidat):
                add(name)
    for alt in image_alts:
        if _BEWERTUNGS_WIDGET_RE.search(alt):
            continue  # „Max Mustermann profile picture“ aus dem Bewertungs-Widget
        for name in find_plausible_names(alt):
            add(name)
    return list(found.values())


def merge_people(*groups: list[Person]) -> list[Person]:
    merged: dict[str, Person] = {}
    for group in groups:
        for p in group:
            key = normalize_name(p.name).casefold()
            if key not in merged:
                merged[key] = p.model_copy(deep=True)
                continue
            cur = merged[key]
            if ROLE_PRIORITY.get(p.role_category, 9) < ROLE_PRIORITY.get(cur.role_category, 9):
                cur.role, cur.role_category = p.role, p.role_category
            elif cur.role is None and p.role:
                cur.role = p.role
            known = {ph.e164 for ph in cur.phones}
            cur.phones.extend(ph for ph in p.phones if ph.e164 not in known)
            cur.email = cur.email or p.email
            cur.source_url = cur.source_url or p.source_url
    return list(merged.values())


def attach_phones(people: list[Person], phones: list[PhoneNumber]) -> None:
    by_full = {normalize_name(p.name).casefold(): p for p in people}
    by_surname: dict[str, list[Person]] = {}
    for p in people:
        by_surname.setdefault(surname(p.name).casefold(), []).append(p)
    for phone in phones:
        if not phone.person:
            continue
        target = by_full.get(normalize_name(phone.person).casefold())
        if target is None:
            cands = by_surname.get(surname(phone.person).casefold(), [])
            target = cands[0] if len(cands) == 1 else None
        if target is None:
            continue
        if phone.e164 not in {ph.e164 for ph in target.phones}:
            target.phones.append(phone)
