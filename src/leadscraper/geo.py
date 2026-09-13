"""Bundesland-Zuordnung aus Adresskomponenten oder PLZ."""

from __future__ import annotations

BUNDESLAENDER = [
    "Baden-Württemberg",
    "Bayern",
    "Berlin",
    "Brandenburg",
    "Bremen",
    "Hamburg",
    "Hessen",
    "Mecklenburg-Vorpommern",
    "Niedersachsen",
    "Nordrhein-Westfalen",
    "Rheinland-Pfalz",
    "Saarland",
    "Sachsen",
    "Sachsen-Anhalt",
    "Schleswig-Holstein",
    "Thüringen",
]

_ALIASES = {
    "baden-wurttemberg": "Baden-Württemberg",
    "baden-wuerttemberg": "Baden-Württemberg",
    "bavaria": "Bayern",
    "hesse": "Hessen",
    "lower saxony": "Niedersachsen",
    "north rhine-westphalia": "Nordrhein-Westfalen",
    "nrw": "Nordrhein-Westfalen",
    "rhineland-palatinate": "Rheinland-Pfalz",
    "saxony": "Sachsen",
    "saxony-anhalt": "Sachsen-Anhalt",
    "thuringia": "Thüringen",
    "thueringen": "Thüringen",
    "mecklenburg-western pomerania": "Mecklenburg-Vorpommern",
}


def normalize_bundesland(name: str | None) -> str | None:
    if not name:
        return None
    key = name.strip().lower()
    for bl in BUNDESLAENDER:
        if bl.lower() == key:
            return bl
    return _ALIASES.get(key)


# Grobe PLZ-Leitzonen -> Bundesland (Fallback, wenn Places kein administrative_area_level_1 liefert).
# Leitzonen sind nicht deckungsgleich mit Ländergrenzen; erste zwei Ziffern reichen für ~95 %.
_PLZ2: dict[str, str] = {}
_ranges: list[tuple[int, int, str]] = [
    (1, 1, "Sachsen"), (2, 2, "Sachsen"), (3, 3, "Brandenburg"), (4, 4, "Sachsen"),
    (6, 6, "Sachsen-Anhalt"), (7, 7, "Thüringen"), (8, 8, "Sachsen"), (9, 9, "Sachsen"),
    (10, 14, "Berlin"), (15, 16, "Brandenburg"), (17, 19, "Mecklenburg-Vorpommern"),
    (20, 22, "Hamburg"), (23, 25, "Schleswig-Holstein"), (26, 27, "Niedersachsen"),
    (28, 28, "Bremen"), (29, 31, "Niedersachsen"), (32, 33, "Nordrhein-Westfalen"),
    (34, 36, "Hessen"), (37, 38, "Niedersachsen"), (39, 39, "Sachsen-Anhalt"),
    (40, 48, "Nordrhein-Westfalen"), (49, 49, "Niedersachsen"), (50, 53, "Nordrhein-Westfalen"),
    (54, 56, "Rheinland-Pfalz"), (57, 59, "Nordrhein-Westfalen"), (60, 65, "Hessen"),
    (66, 66, "Saarland"), (67, 67, "Rheinland-Pfalz"), (68, 79, "Baden-Württemberg"),
    (80, 87, "Bayern"), (88, 89, "Baden-Württemberg"), (90, 97, "Bayern"), (98, 99, "Thüringen"),
]
for _lo, _hi, _bl in _ranges:
    for _n in range(_lo, _hi + 1):
        _PLZ2[f"{_n:02d}"] = _bl


def bundesland_from_plz(plz: str | None) -> str | None:
    if not plz or len(plz) < 2 or not plz[:2].isdigit():
        return None
    return _PLZ2.get(plz[:2])
