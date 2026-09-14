"""Personen + Rollen auf Team-/Kontakt-/Ansprechpartner-Seiten; Zusammenführen von Personen."""

from __future__ import annotations

import re

from leadscraper.extract.htmlutil import Link
from leadscraper.extract.names import find_names, is_probable_person_name, normalize_name, surname
from leadscraper.models import ROLE_PRIORITY, Person, PhoneNumber, RoleCategory

ROLE_PATTERNS: list[tuple[str, RoleCategory]] = [
    (
        r"geschäftsführ|geschaeftsfuehr|\bceo\b|managing\s+director|geschäftsleit|gründer|founder|geschäftsinhaber",
        "geschaeftsfuehrung",
    ),
    (r"inhaber|betriebsinhaber|eigentümer|\bowner\b|einzelunternehmer", "inhaber"),
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


def categorize_role(role_text: str | None) -> RoleCategory:
    if not role_text:
        return "sonstige"
    for pat, cat in _ROLE_RES:
        if pat.search(role_text):
            return cat
    return "sonstige"


def _is_roleish(line: str) -> bool:
    if len(line) > 80 or is_probable_person_name(line):
        return False
    if re.search(r"\d", _YEAR_RE.sub("", line)):
        return False
    return bool(categorize_role(line) != "sonstige" or _ROLEISH_RE.search(line))


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
        if role or page_kind in ("team", "kontakt"):
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
