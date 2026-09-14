"""Impressum parsen (§ 5 DDG-Pflichtangaben): Entscheider, Rechtsform, Register, USt-IdNr, Adresse."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from leadscraper.extract.names import find_names, is_probable_person_name, normalize_name
from leadscraper.models import Person, RoleCategory

_URL_HINT_RE = re.compile(
    r"impressum|imprint|legal[-_]?notice|anbieterkennzeichnung|rechtliche[-_]hinweise", re.I
)

# (Regex auf Zeilenanfang, Rollentext, Kategorie oder None = Label nur zum Abgrenzen)
_LABELS: list[tuple[re.Pattern[str], RoleCategory | None]] = [
    (
        re.compile(
            r"^(?:der\s+|die\s+)?(?:alleinvertretungsberechtigte[rn]?\s+|vertretungsberechtigte[rn]?\s+|einzelvertretungsberechtigte[rn]?\s+)?geschäftsführ(?:er(?:in|innen)?|ung|ende[rn]?\s+gesellschafter(?:in|innen)?)",
            re.I,
        ),
        "geschaeftsfuehrung",
    ),
    (
        re.compile(
            r"^(?:gesetzlich\s+)?vertreten\s+durch|^vertretungsberechtigte?r?\b|^vertretungsberechtigung",
            re.I,
        ),
        "geschaeftsfuehrung",
    ),
    (
        re.compile(
            r"^(?:managing\s+directors?|ceo|geschäftsleitung|unternehmensleitung|betriebsleitung)\b", re.I
        ),
        "geschaeftsfuehrung",
    ),
    (
        re.compile(
            r"^(?:betriebs)?inhaber(?:in|innen)?\b|^einzelunternehmer(?:in)?\b|^eigentümer(?:in)?\b|^firmeninhaber(?:in)?\b",
            re.I,
        ),
        "inhaber",
    ),
    (
        re.compile(
            r"^vorstand(?:svorsitzende[rn]?|smitglied(?:er)?|sprecher)?\b|^vorsitzende[rn]?\s+des\s+vorstand",
            re.I,
        ),
        "vorstand",
    ),
    (
        re.compile(r"^(?:komplementär(?:in)?|persönlich\s+haftende[rn]?\s+gesellschafter(?:in)?)\b", re.I),
        "inhaber",
    ),
    (re.compile(r"^partner(?:in|innen)?\b|^gesellschafter(?:in|innen)?\b", re.I), "geschaeftsfuehrung"),
    (re.compile(r"^prokurist(?:in|en)?\b|^prokura\b", re.I), "prokura"),
    (
        re.compile(r"^(?:inhaltlich\s+)?verantwortlich|^redaktion|^v\.\s*i\.\s*s\.\s*d\.|^chefredakt", re.I),
        "sonstige",
    ),
    (re.compile(r"^aufsichtsrat|^beirat|^kuratorium", re.I), None),
]
_STOP_LABEL_RE = re.compile(
    r"^(?:registergericht|handelsregister|register(?:nummer)?|amtsgericht|umsatzsteuer|ust|steuernummer|steuer-?nr|"
    r"telefon|tel\.?|telefax|fax|mobil|e-?mail|mail|internet|web|kontakt|anschrift|adresse|postanschrift|sitz|"
    r"berufsbezeichnung|kammer|zuständige|aufsichtsbehörde|berufsrechtliche|berufshaftpflicht|haftung|"
    r"streitschlichtung|eu-streitschlichtung|verbraucherstreitbeilegung|datenschutz|urheberrecht|bildnachweis|"
    r"quellenangaben|hinweis|angaben\s+gemäß|dienstanbieter|diensteanbieter|anbieter|firma|firmenname|"
    r"unternehmen|rechtsform|gerichtsstand|bankverbindung|iban|wirtschafts-?id|d-u-n-s)\b",
    re.I,
)
_CUTOFF_RE = re.compile(
    r"^(?:haftungsausschluss|haftung\s+für\s+(?:inhalte|links)|disclaimer|urheberrecht|copyright|"
    r"streitschlichtung|eu-streitschlichtung|verbraucherstreitbeilegung|datenschutz(?:erklärung)?|"
    r"realisierung|webdesign|web-?entwicklung|umsetzung|konzeption|programmierung|technische\s+umsetzung|"
    r"gestaltung|design|bildnachweis|bildnachweise|bildquellen|fotos?|fotografie|credits|quellenangaben|"
    r"agentur|website\s+by|erstellt\s+von|powered\s+by)\b",
    re.I,
)
_RECHTSFORMEN: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgGmbH\s*&\s*Co\.?\s*KG\b", re.I), "gGmbH & Co. KG"),
    (re.compile(r"\bGmbH\s*&\s*Co\.?\s*KGaA\b", re.I), "GmbH & Co. KGaA"),
    (re.compile(r"\bGmbH\s*&\s*Co\.?\s*(?:KG|OHG)\b", re.I), "GmbH & Co. KG"),
    (re.compile(r"\bUG\s*\(haftungsbeschränkt\)\s*&\s*Co\.?\s*KG\b", re.I), "UG & Co. KG"),
    (re.compile(r"\bAG\s*&\s*Co\.?\s*KG\b"), "AG & Co. KG"),
    (re.compile(r"\bSE\s*&\s*Co\.?\s*KG(?:aA)?\b"), "SE & Co. KG"),
    (re.compile(r"\bUG\s*\(haftungsbeschränkt\)|\bUG\b(?=\s*(?:$|[,;(]|haftungs))", re.I), "UG"),
    (re.compile(r"\bgGmbH\b"), "gGmbH"),
    (re.compile(r"\b(?:GmbH|G\.m\.b\.H\.|Gesellschaft\s+mit\s+beschränkter\s+Haftung)\b|\bmbH\b"), "GmbH"),
    (re.compile(r"\bPartG\s*mbB\b|\bPartnerschaftsgesellschaft\s+mbB\b|\bmbB\b"), "PartG mbB"),
    (re.compile(r"\bPartG\b|\bPartnerschaft(?:sgesellschaft)?\b"), "PartG"),
    (re.compile(r"\bKGaA\b"), "KGaA"),
    (re.compile(r"\bSE\b(?=\s*(?:$|[,;(]))"), "SE"),
    (re.compile(r"\bAG\b(?=\s*(?:$|[,;(]))|\bAktiengesellschaft\b"), "AG"),
    (re.compile(r"\bOHG\b|\boHG\b"), "OHG"),
    (re.compile(r"\bKG\b(?=\s*(?:$|[,;(]))|\bKommanditgesellschaft\b"), "KG"),
    (
        re.compile(
            r"\be\.\s?K\.|\be\.\s?Kfm\.|\be\.\s?Kfr\.|\beingetragene[rn]?\s+Kau(?:fmann|ffrau)\b", re.I
        ),
        "e.K.",
    ),
    (re.compile(r"\be\.\s?G\.|\beG\b(?=\s*(?:$|[,;(]))|\beingetragene\s+Genossenschaft\b"), "eG"),
    (re.compile(r"\be\.\s?V\.|\beingetragener\s+Verein\b"), "e.V."),
    (re.compile(r"\bGbR\b|\bGesellschaft\s+bürgerlichen\s+Rechts\b"), "GbR"),
    (re.compile(r"\bStiftung\b"), "Stiftung"),
    (re.compile(r"\bKdöR\b|\bAöR\b|\bKörperschaft\s+des\s+öffentlichen\s+Rechts\b"), "KdöR"),
    (
        re.compile(r"\bLtd\.?\b|\bLimited\b|\bB\.V\.|\bS\.à\s?r\.l\.|\bS\.r\.l\.|\bInc\.?\b|\bLLC\b"),
        "ausländisch",
    ),
]
_REGISTER_RE = re.compile(r"\b(HRA|HRB|GnR|PR|VR|GsR)\s*[:.]?\s*(\d{1,7}(?:\s?[A-Z]{1,2})?)\b")
_REGISTER_NR_RE = re.compile(r"(?:handelsregister|register)-?(?:nummer|nr\.?)\s*:?\s*(\d{2,7})", re.I)
_AMTSGERICHT_RE = re.compile(
    r"Amtsgericht[ \t]+([A-ZÄÖÜ][\wäöüß.\-]+"
    r"(?:[ \t]+(?:am|an|im|in|der|\(Oder\))[ \t]+[A-ZÄÖÜ][\wäöüß.\-]+|[ \t]+[A-ZÄÖÜ][\wäöüß.\-]+){0,2})"
)
_USTID_RE = re.compile(r"\bDE\s?\d{3}\s?\d{3}\s?\d{3}\b")
_STEUERNR_RE = re.compile(r"Steuer-?(?:nummer|nr\.?)\s*:?\s*(\d[\d/ ]{7,18}\d)", re.I)
_PLZ_ORT_RE = re.compile(r"^(?:D[- ]\s?)?(\d{5})\s+([A-ZÄÖÜ][\wäöüß.\-]+(?:\s+[\wäöüß.\-()]+){0,3})\s*$")
_STREET_RE = re.compile(r"^[A-ZÄÖÜ][\wäöüß.\- ]{2,40}\s\d+[a-zA-Z]?(?:\s?[-/]\s?\d+[a-zA-Z]?)?\s*$")
_ROLE_TAIL_RE = re.compile(r"\s*\((?:[^)]*)\)\s*$")
_SPLIT_RE = re.compile(r"\s*(?:,|;|/|\|| und | & | sowie )\s*", re.I)


@dataclass
class ImpressumData:
    legal_name: str | None = None
    rechtsform: str | None = None
    register: str | None = None
    amtsgericht: str | None = None
    ustid: str | None = None
    steuernummer: str | None = None
    people: list[Person] = field(default_factory=list)
    street: str | None = None
    plz: str | None = None
    city: str | None = None


def detect_rechtsform(name: str | None) -> str | None:
    if not name:
        return None
    for pat, form in _RECHTSFORMEN:
        if pat.search(name):
            return form
    return None


def is_impressum_page(url: str, lines: list[str]) -> bool:
    if _URL_HINT_RE.search(url or ""):
        return True
    head = "\n".join(lines[:60])
    has_marker = bool(re.search(r"angaben\s+gemäß\s+§\s*5|impressum|anbieterkennzeichnung", head, re.I))
    has_facts = bool(
        _REGISTER_RE.search(head) or _USTID_RE.search(head) or re.search(r"vertreten\s+durch", head, re.I)
    )
    return has_marker and has_facts


_GENERIC_LABEL_RE = re.compile(r"^(?:gesetzlich\s+)?vertret|^vertretungsberechtig|^(?:der|die)\s", re.I)
_CATEGORY_ROLE: dict[str, str] = {
    "geschaeftsfuehrung": "Geschäftsführung",
    "inhaber": "Inhaber/-in",
    "vorstand": "Vorstand",
    "prokura": "Prokurist/-in",
    "hr": "Personal / HR",
    "ausbildung": "Ausbildungsleitung",
    "betriebsleitung": "Betriebsleitung",
}


def _readable_role(label: str, category: RoleCategory | None) -> str:
    """„Vertreten durch“ / „Vertretungsberechtigter“ sagt nichts über die Funktion – Kategorie anzeigen."""
    text = label.strip(" :")
    if category and _GENERIC_LABEL_RE.match(text):
        return _CATEGORY_ROLE.get(category, text)
    return text


def _match_label(line: str) -> tuple[re.Match[str], RoleCategory | None] | None:
    for pat, cat in _LABELS:
        m = pat.match(line)
        if m:
            return m, cat
    return None


def _is_stop(line: str) -> bool:
    return bool(_STOP_LABEL_RE.match(line) or _match_label(line) or _CUTOFF_RE.match(line))


def _names_from_piece(piece: str) -> list[str]:
    piece = _ROLE_TAIL_RE.sub("", piece).strip(" :.-–")
    if not piece or detect_rechtsform(piece):
        return []
    if is_probable_person_name(piece):
        return [normalize_name(piece)]
    return [normalize_name(n) for n in find_names(piece)]


def _names_after_label(lines: list[str], idx: int, label_end: int) -> tuple[list[str], bool]:
    """Namen hinter einem Label (gleiche Zeile, sonst Folgezeilen); zweiter Wert: Firma dazwischen?"""
    rest = lines[idx][label_end:].strip(" :.-–")
    names: list[str] = []
    saw_company = False
    for piece in _SPLIT_RE.split(rest):
        if not piece:
            continue
        if detect_rechtsform(piece):
            saw_company = True
            continue
        names.extend(_names_from_piece(piece))
    if names and not saw_company:
        return names, False
    # Namen auf den Folgezeilen (eine pro Zeile oder kommagetrennt)
    for j in range(idx + 1, min(idx + 6, len(lines))):
        line = lines[j].strip()
        if not line or _is_stop(line):
            break
        if "@" in line or "http" in line.lower() or re.search(r"\d{4,}", line):
            break
        if detect_rechtsform(line):
            saw_company = True
            continue  # "diese vertreten durch …" kommt oft danach
        # "diese vertreten durch den Geschäftsführer Max Muster"
        inner = re.sub(
            r"^(?:diese|dieser|jeweils)?\s*(?:vertreten\s+durch\s+)?(?:den|die|ihren?|deren)?\s*"
            r"(?:geschäftsführer(?:in)?|inhaber(?:in)?|vorstand)?\s*",
            "",
            line,
            flags=re.I,
        )
        found: list[str] = []
        for piece in _SPLIT_RE.split(inner):
            found.extend(_names_from_piece(piece))
        if not found:
            if names:
                break
            continue
        names.extend(found)
    return names, saw_company


def _find_cut(lines: list[str]) -> int:
    anchor = None
    for i, line in enumerate(lines):
        if _match_label(line) or _REGISTER_RE.search(line) or _USTID_RE.search(line):
            anchor = i
            break
    for i, line in enumerate(lines):
        if anchor is not None and i <= anchor:
            continue
        if len(line) <= 60 and _CUTOFF_RE.match(line.strip()):
            return i
    return len(lines)


def parse_impressum(lines: list[str], url: str | None = None) -> ImpressumData:
    data = ImpressumData()
    lines = [ln.strip() for ln in lines if ln and ln.strip()]
    cut = _find_cut(lines)
    scope = lines[:cut]

    # Firmenname / Rechtsform: erste Zeile mit Rechtsform, die kein Label ist
    for line in scope[:40]:
        if _match_label(line) or _STOP_LABEL_RE.match(line):
            continue
        form = detect_rechtsform(line)
        if form and len(line) <= 90:
            data.legal_name = line.strip(" :")
            data.rechtsform = form
            break

    seen: dict[str, Person] = {}
    for i, line in enumerate(scope):
        hit = _match_label(line)
        if not hit:
            continue
        m, category = hit
        if category is None:
            continue
        role_text = _readable_role(m.group(0), category)
        names, via_company = _names_after_label(scope, i, m.end())
        if via_company and category == "inhaber":
            category, role_text = "geschaeftsfuehrung", "Geschäftsführer (Komplementär-GmbH)"
        for name in names:
            key = normalize_name(name).casefold()
            if key in seen:
                existing = seen[key]
                if category != "sonstige" and existing.role_category == "sonstige":
                    existing.role, existing.role_category = role_text, category
                continue
            if category == "sonstige":
                seen[key] = Person(name=name, role=role_text, role_category="sonstige", source_url=url)
            else:
                seen[key] = Person(name=name, role=role_text, role_category=category, source_url=url)
    data.people = list(seen.values())

    full = "\n".join(scope)
    if m := _REGISTER_RE.search(full):
        data.register = f"{m.group(1)} {m.group(2)}".replace("  ", " ")
    elif m := _REGISTER_NR_RE.search(full):
        data.register = f"Nr. {m.group(1)}"
    if m := _AMTSGERICHT_RE.search(full):
        data.amtsgericht = f"Amtsgericht {m.group(1).strip(' ,.')}"
    if m := _USTID_RE.search(full):
        data.ustid = re.sub(r"\s", "", m.group(0))
    if m := _STEUERNR_RE.search(full):
        data.steuernummer = m.group(1).strip()

    for i, line in enumerate(scope[:40]):
        if m := _PLZ_ORT_RE.match(line):
            data.plz, data.city = m.group(1), m.group(2).strip()
            if i > 0 and _STREET_RE.match(scope[i - 1]):
                data.street = scope[i - 1]
            break

    if data.rechtsform is None and any(p.role_category == "inhaber" for p in data.people):
        data.rechtsform = "Einzelunternehmen"
        if data.legal_name is None:
            data.legal_name = next(p.name for p in data.people if p.role_category == "inhaber")
    return data
