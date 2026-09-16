"""Hat der Betrieb mehrere Standorte? Für die Förderung entscheidet das über 100 oder 50 Prozent.

§ 82 Abs. 6 Satz 3 Nr. 2 SGB III zählt bei der Betriebsgröße „sämtliche Beschäftigte des Unternehmens,
dem der Betrieb angehört, und, falls das Unternehmen einem Konzern angehört, die Zahl der Beschäftigten
des Konzerns“. Eine Niederlassung mit 30 Leuten hilft also nichts, wenn das Unternehmen 400 hat: Die
Lehrgangskosten fallen von 100 auf 50 Prozent, und das Gespräch ist ein anderes.

Von außen sichtbar wird das an zwei Dingen: einer Standortseite in der Navigation und mehreren
Postleitzahlen in Adressblöcken derselben Website. Beides ist ein Verdacht, kein Beweis – die Zahl der
Standorte gehört deshalb in die Vorqualifizierung am Telefon und nicht in einen stillen Ausschluss.
"""

from __future__ import annotations

import re

# Navigationspunkte, die auf mehrere Standorte zeigen. „Standort“ im Singular ist bewusst nicht dabei:
# „Standort & Anfahrt“ steht auf fast jeder Website eines Einzelbetriebs.
_STANDORT_LINK_RE = re.compile(
    r"^\s*(?:unsere\s+)?(?:standorte|niederlassungen|filialen|geschäftsstellen|zweigstellen|"
    r"unsere\s+(?:büros|häuser|praxen|niederlassung\w*)|standortübersicht)\s*$",
    re.I,
)
# „an 7 Standorten“, „12 Filialen“, „bundesweit 30 Niederlassungen“
_STANDORT_ZAHL_RE = re.compile(
    r"\b(?:an\s+)?(\d{1,3})\s+(standorte[n]?|niederlassungen|filialen|geschäftsstellen|büros)\b", re.I
)
# Adressblock: „50667 Köln“ – die Postleitzahl allein genügt nicht, der Ort muss folgen
_ADRESSE_RE = re.compile(r"\b(\d{5})\s+([A-ZÄÖÜ][\wäöüß.-]{2,}(?:[ -][A-ZÄÖÜ][\wäöüß.-]{2,})?)")
_MIN_PLZ_FUER_VERDACHT = 3


def standort_hinweise(
    lines: list[str], anchor_texts: list[str] | None = None
) -> tuple[bool, str | None, int]:
    """(mehrere Standorte?, Beleg, Zahl gefundener Postleitzahlen)

    Drei Postleitzahlen sind die Schwelle, nicht zwei: Viele Betriebe nennen neben der eigenen Anschrift
    noch die des Steuerberaters, der Schlichtungsstelle oder der Kammer.
    """
    for text in anchor_texts or []:
        if _STANDORT_LINK_RE.match(text.strip()):
            return True, f"Navigationspunkt „{text.strip()}“", 0

    plz: dict[str, str] = {}
    for line in lines:
        for treffer in _ADRESSE_RE.finditer(line):
            plz.setdefault(treffer.group(1), treffer.group(2))
        if m := _STANDORT_ZAHL_RE.search(line):
            anzahl = int(m.group(1))
            if 2 <= anzahl <= 300:
                return True, f"„{m.group(0).strip()}“ auf der Website", len(plz)

    if len(plz) >= _MIN_PLZ_FUER_VERDACHT:
        beispiele = ", ".join(f"{p} {o}" for p, o in list(plz.items())[:3])
        return True, f"{len(plz)} verschiedene Anschriften auf der Website ({beispiele} …)", len(plz)
    return False, None, len(plz)
