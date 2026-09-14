"""Belegschaft zählen: Wie viele Menschen arbeiten in diesem Betrieb *nachweislich*?

Für die Förderung nach § 82 SGB III zählen nur sozialversicherungspflichtig Beschäftigte. Die
Mitarbeiterzahl steht fast nie auf der Website, deshalb werden unterscheidbare Personen gezählt:

* **Namentlich** auf Team-/Kontaktseiten genannte Menschen (Fundstelle muss eine solche Seite sein).
* **Persönliche Postfächer** (`vorname.nachname@`, `m.mustermann@`) – Rollenadressen wie `info@` zählen nicht.
* **Eigene Durchwahlen**: mehrere Festnetznummern mit gleichem Stamm und unterschiedlicher Endung
  (`0221 5550-11`, `-12`, `-13`) bedeuten ebenso viele Arbeitsplätze.
* **Ausdrückliche Angabe** („Team aus 14 Mitarbeitern“) – schlägt alles andere.

Die Signale überschneiden sich (dieselbe Person hat Name, Postfach und Durchwahl), deshalb werden
Identitäten über den Nachnamen zusammengeführt und nicht addiert. Das Ergebnis ist eine **Untergrenze**:
Innendienst, Buchhaltung und Azubis stehen selten auf der Website.
"""

from __future__ import annotations

import re
from collections import defaultdict

from leadscraper.extract.names import surname
from leadscraper.models import Person, PhoneNumber, StaffEvidence

# Rollen-/Funktionspostfächer – kein Hinweis auf eine Person
_ROLE_MAILBOX_RE = re.compile(
    r"^(?:info|kontakt|mail|e?mail|office|buero|büro|service|verwaltung|immobilien|makler|team|post|"
    r"zentrale|anfrage|anfragen|beratung|vertrieb|verkauf|vermietung|marketing|presse|datenschutz|"
    r"webmaster|admin|noreply|no-reply|bewerbung|jobs|karriere|support|hallo|moin|willkommen|termin|"
    r"empfang|sekretariat|buchhaltung|rechnung|finanzen|newsletter|shop|web|www|mail2|test)$",
    re.I,
)
# „m.mustermann“, „max.mustermann“, „mustermann“, „max-mustermann“
_PERSONAL_MAILBOX_RE = re.compile(r"^[a-zäöüß]{1,20}[._-][a-zäöüß][a-zäöüß-]{2,25}$", re.I)
_MIN_SURNAME = 4


def _identity(value: str) -> str:
    return re.sub(r"[^a-zäöüß]", "", value.casefold())


def personal_mailboxes(emails: list[str], people: list[Person]) -> dict[str, str]:
    """Persönliche Postfächer → {Identität: Adresse}. Identität ist der Nachnamen-Teil."""
    known = {_identity(surname(p.name)) for p in people if len(surname(p.name)) >= _MIN_SURNAME}
    found: dict[str, str] = {}
    for addr in emails:
        local = addr.split("@", 1)[0].strip().lower()
        if _ROLE_MAILBOX_RE.match(local):
            continue
        parts = [p for p in re.split(r"[._-]", local) if p]
        ident = None
        for part in parts:
            key = _identity(part)
            if key in known:
                ident = key
                break
        if ident is None and _PERSONAL_MAILBOX_RE.match(local):
            ident = _identity(parts[-1])
        if ident is None and len(parts) == 1 and _identity(local) in known:
            ident = _identity(local)
        if ident and len(ident) >= 3:
            found.setdefault(ident, addr)
    return found


def extension_count(phones: list[PhoneNumber]) -> tuple[int, str | None]:
    """Wie viele Durchwahlen hat die größte Nummerngruppe? (Anzahl, Beispiel-Beleg)

    Mehrere Festnetznummern mit demselben Stamm und unterschiedlicher Endung sind eigene Arbeitsplätze:
    +49221555011, +49221555012, +49221555013 → drei Durchwahlen.
    """
    groups: dict[str, set[str]] = defaultdict(set)
    for phone in phones:
        if phone.kind != "landline" or phone.source == "places":
            continue
        digits = phone.e164
        if len(digits) < 10:
            continue
        groups[digits[:-2]].add(digits)
    if not groups:
        return 0, None
    stem, numbers = max(groups.items(), key=lambda kv: len(kv[1]))
    if len(numbers) < 2:
        return 0, None
    beispiel = ", ".join(sorted(numbers)[:3])
    return len(numbers), f"{len(numbers)} Durchwahlen unter einem Anschluss ({beispiel} …)"


_ROLE_IS_STAFF = {
    "geschaeftsfuehrung",
    "inhaber",
    "vorstand",
    "prokura",
    "hr",
    "ausbildung",
    "betriebsleitung",
}


def count_staff(
    staff_people: list[Person],
    emails: list[str],
    phones: list[PhoneNumber],
    *,
    all_people: list[Person] | None = None,
    stated: int | None = None,
    stated_evidence: str | None = None,
) -> StaffEvidence:
    """Belegte Kopfzahl aus zusammengeführten Identitäten. `staff_people` sind Personen von
    Team-/Kontaktseiten (dort stehen Mitarbeitende), `all_people` alle bekannten Personen – aus ihnen
    zählen zusätzlich die mit einer Funktion im Betrieb (Geschäftsführung, Prokura, Personal …), denn
    auch der Chef arbeitet dort."""
    people = all_people if all_people is not None else staff_people
    named: dict[str, str] = {}
    for person in [*staff_people, *(p for p in people if p.role_category in _ROLE_IS_STAFF)]:
        key = _identity(surname(person.name))
        if len(key) >= 3:
            named.setdefault(key, person.name)
    mailboxes = personal_mailboxes(emails, people)
    extensions, ext_evidence = extension_count(phones)

    identities = set(named) | set(mailboxes)
    evidence: list[str] = []
    if named:
        wer = ", ".join(list(named.values())[:4])
        evidence.append(f"{len(named)} namentlich genannte Mitarbeitende ({wer})")
    if mailboxes:
        evidence.append(
            f"{len(mailboxes)} persönliche E-Mail-Postfächer ({', '.join(list(mailboxes.values())[:3])})"
        )
    if ext_evidence:
        evidence.append(ext_evidence)
    if stated is not None and stated_evidence:
        evidence.insert(0, stated_evidence)

    headcount = max(len(identities), extensions, stated or 0)
    return StaffEvidence(
        headcount=headcount,
        named=len(named),
        mailboxes=len(mailboxes),
        extensions=extensions,
        stated=stated,
        evidence=evidence[:5],
    )
