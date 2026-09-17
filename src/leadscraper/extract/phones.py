"""Telefonnummern finden, als mobil/festnetz klassifizieren und Personen zuordnen.

Kernidee: Die Handynummer des Entscheiders steht selten im Impressum, sondern auf Team-/Kontakt-/
Objektseiten neben dem Namen. Jede gefundene Nummer wird deshalb der nächstgelegenen Person im Text
zugeordnet (gleiche Zeile, sonst bis 4 Zeilen davor) – bekannte Personen (z. B. aus dem Impressum)
haben Vorrang, es reicht der Nachname.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlsplit

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberType

from leadscraper.extract.htmlutil import Link
from leadscraper.extract.names import find_plausible_names, normalize_name, surname
from leadscraper.extract.people import _DIENSTLEISTER_FENSTER, _DIENSTLEISTER_RE
from leadscraper.models import Person, PhoneNumber, PhoneSource, RoleCategory

# Kandidaten im Fließtext: beginnt mit +49 / 0049 / 0, dann Ziffern mit üblichen Trennern
_CANDIDATE_RE = re.compile(r"(?<![\w+])(?:\+49|0049|0)[\d\s\-–—/.()]{5,24}\d(?![\w])")
_MOBILE_LABEL_RE = re.compile(
    r"\b(?:mobil(?:e|nummer|telefon)?|handy(?:nummer)?|cell(?:phone)?|whats\s?app|m\s*:)\s*[:.]?", re.I
)
_FAX_LABEL_RE = re.compile(r"\b(?:tele)?fax\b|\bf\s*[:.]", re.I)
_TEL_LABEL_RE = re.compile(
    r"\b(?:tel(?:efon|\.|:)?|fon|phone|telephone|zentrale|festnetz|büro|t\s*:|durchwahl|notdienst|notruf|bereitschaft|hotline)\b",
    re.I,
)
_LABEL_WORD_RE = re.compile(
    r"(mobil(?:e|nummer|telefon)?|handy(?:nummer)?|cell(?:phone)?|whats\s?app|telefax|fax|telefon|tel\.?|fon|phone|"
    r"festnetz|zentrale|büro|durchwahl|notdienst|notruf|bereitschaft|hotline)",
    re.I,
)
# Kontext, in dem Ziffernfolgen keine Telefonnummern sind
_BAD_CONTEXT_RE = re.compile(
    r"(iban|bic|swift|konto|blz|bankleitzahl|hrb|hra|gnr|vr\s?\d|pr\s?\d|registernummer|handelsregister|"
    r"ust[\s.-]*id|umsatzsteuer|steuernummer|steuer-?nr|st\.?-?nr|kundennummer|auftragsnummer|"
    r"objekt-?nr|exposé|expose|artikel|art\.-?nr|isbn|ean|plz|postleitzahl|\bde\s?\d{9})",
    re.I,
)
_DATE_RE = re.compile(r"^\d{1,2}\.\d{1,2}\.(?:\d{2}|\d{4})$")
_MAX_LOOKBACK = 4
# Notdienst-Kontext: Eine Nummer in diesem Umfeld ist die Bereitschaftsnummer, auch wenn der Name des
# Chefs daneben steht. Von 237 geprüften „Entscheider-Handys“ waren 51 solche Nummern; 27 trugen sogar
# das Label „Notdienst“ und wurden trotzdem dem Chef zugeschrieben.
_NOTDIENST_RE = re.compile(
    r"notdienst|notfall|notruf|bereitschaft|störungs?dienst|störung|havarie|24\s?(?:h|std|stunden)|"
    r"rund um die uhr|außerhalb der (?:geschäfts|öffnungs|büro)zeiten|abschlepp|pannen",
    re.I,
)


def _kind_from_type(num_type: int) -> str:
    if num_type == PhoneNumberType.MOBILE:
        return "mobile"
    if num_type == PhoneNumberType.FIXED_LINE:
        return "landline"
    if num_type == PhoneNumberType.VOIP:
        return "voip"
    return "unknown"


def _parse(raw: str) -> phonenumbers.PhoneNumber | None:
    digits = re.sub(r"\D", "", raw)
    if not 7 <= len(digits) <= 15:
        return None
    try:
        num = phonenumbers.parse(raw, "DE")
    except NumberParseException:
        return None
    if not phonenumbers.is_valid_number(num):
        return None
    return num


def classify_number(
    raw: str,
    *,
    source: PhoneSource = "sonstige",
    source_url: str | None = None,
    label: str | None = None,
    person: str | None = None,
) -> PhoneNumber | None:
    num = _parse(raw)
    if num is None:
        return None
    kind = _kind_from_type(phonenumbers.number_type(num))
    if kind == "unknown" and label and _MOBILE_LABEL_RE.search(label):
        kind = "mobile"
    return PhoneNumber(
        raw=raw.strip(),
        e164=phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164),
        national=phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.NATIONAL),
        kind=kind,
        source=source,
        source_url=source_url,
        label=label,
        person=person,
    )


def parse_whatsapp_link(href: str) -> str | None:
    """Nummer aus wa.me/49171…, api.whatsapp.com/send?phone=…, whatsapp://send?phone=…"""
    href = unquote(href.strip())
    low = href.lower()
    parts = urlsplit(href)
    if "wa.me" in low:
        seg = parts.path.strip("/").split("/")[0]
        if seg.lower() == "message" or not seg:
            return None
        digits = re.sub(r"\D", "", seg)
        return f"+{digits}" if len(digits) >= 8 else None
    if "whatsapp" in low:
        phone = parse_qs(parts.query).get("phone", [""])[0]
        digits = re.sub(r"\D", "", phone)
        return f"+{digits}" if len(digits) >= 8 else None
    return None


def _label_before(text: str) -> str | None:
    """Letztes Label-Wort im Text unmittelbar vor der Nummer (max. 30 Zeichen)."""
    snippet = text[-30:]
    matches = list(_LABEL_WORD_RE.finditer(snippet))
    if not matches:
        return None
    return matches[-1].group(1)


def _normalize_label(label: str | None) -> str | None:
    if not label:
        return None
    low = label.lower().replace(" ", "")
    if low.startswith(("mobil", "handy", "cell")):
        return "Mobil"
    if low.startswith("whats"):
        return "WhatsApp"
    if "fax" in low:
        return "Fax"
    if low.startswith(("notdienst", "notruf", "notfall", "bereitschaft", "störung")):
        return "Notdienst"
    if low == "dienstleister":
        return "Dienstleister"
    if low.startswith(("tel", "fon", "phone", "zentrale", "festnetz", "büro", "durchwahl", "hotline")):
        return "Tel"
    return label


# E-Mail-Adressen und URLs enthalten den Nachnamen der Firma („brandes@brandes-immobilien.de“) und
# dürfen deshalb keine Personen-Zuordnung auslösen.
_ADDRESS_RE = re.compile(r"\S+@\S+|https?://\S+|www\.\S+|\b[\w-]+\.(?:de|com|net|org|eu|info|immo)\b", re.I)


class _NameIndex:
    """Personennamen je Zeile (lazy), bekannte Personen zuerst."""

    def __init__(self, lines: list[str], known: list[Person] | None) -> None:
        self.lines = lines
        self.known = [
            (p.name, normalize_name(p.name).casefold(), surname(p.name).casefold()) for p in (known or [])
        ]
        self._cache: dict[int, list[str]] = {}

    def known_in(self, idx: int) -> str | None:
        line = self.lines[idx].casefold()
        ohne_adressen = _ADDRESS_RE.sub(" ", line)
        treffer: list[str] = []
        for name, full, sn in self.known:
            if full and full in line:
                return name
            if sn and len(sn) >= 3 and re.search(rf"(?<!\w){re.escape(sn)}(?!\w)", ohne_adressen):
                treffer.append(name)
        # Mehrere Personen mit demselben Nachnamen (Familienbetrieb) – ohne Vornamen ist das nicht
        # entscheidbar, dann lieber keine Zuordnung als die falsche.
        return treffer[0] if len(treffer) == 1 else None

    def any_in(self, idx: int) -> list[str]:
        if idx not in self._cache:
            self._cache[idx] = find_plausible_names(self.lines[idx])
        return self._cache[idx]


def _associate_same_line(index: _NameIndex, line_idx: int, before_text: str) -> str | None:
    """Nur dieselbe Zeile: für WhatsApp-Nummern. Die stehen im Seitenkopf als Firmennummer, und ein
    Rückgriff auf Namen aus den Zeilen davor machte sie in 25 von 237 geprüften Fällen zum Chef-Handy."""
    name = index.known_in(line_idx)
    if name:
        return name
    before_names = find_plausible_names(before_text) if before_text else []
    return before_names[-1] if before_names else None


def _associate(index: _NameIndex, line_idx: int, before_text: str) -> str | None:
    """Person für eine Nummer in Zeile line_idx; before_text = Zeilentext vor der Nummer."""
    # 1) bekannte Personen: gleiche Zeile, dann rückwärts
    for offset in range(0, _MAX_LOOKBACK + 1):
        i = line_idx - offset
        if i < 0:
            break
        name = index.known_in(i)
        if name:
            return name
        if offset > 0 and index.any_in(i):
            break  # eine andere Person steht dazwischen → nicht weiter zurück
    # 2) plausibler Name (bekannter Vorname/Anrede): gleiche Zeile (vor der Nummer bevorzugt), dann
    #    bis 3 Zeilen zurück – sonst landen Handynummern bei „Immobilienbewertung Frechen“
    before_names = find_plausible_names(before_text) if before_text else []
    same = before_names or index.any_in(line_idx)
    if same:
        return same[-1] if before_names else same[0]
    for offset in range(1, _MAX_LOOKBACK):
        i = line_idx - offset
        if i < 0:
            break
        names = index.any_in(i)
        if names:
            return names[-1]
    return None


def find_phones(
    lines: list[str],
    links: list[Link],
    *,
    source: PhoneSource,
    source_url: str | None,
    known_people: list[Person] | None = None,
) -> list[PhoneNumber]:
    index = _NameIndex(lines, known_people)
    found: list[PhoneNumber] = []
    digits_to_line: dict[str, int] = {}
    gesperrt: set[str] = set()  # Nummern aus Notdienst- oder Agentur-Kontext: keiner Person zuordnen
    agentur = 0

    for i, line in enumerate(lines):
        # Agentur-Block wie in people.py: „Realisierung: …“, „Webdesign …“ – die Nummern darunter
        # gehören dem Dienstleister, nicht dem Betrieb (8 von 237 geprüften „Entscheider-Handys“).
        if _DIENSTLEISTER_RE.search(line):
            agentur = _DIENSTLEISTER_FENSTER + 1
        im_agentur_block = agentur > 0
        agentur = max(0, agentur - 1)
        # Notdienst-Kontext: diese Zeile, und eine kurze Zeile davor („24h Notdienst“ über der Nummer)
        # Die Zeile davor zählt nur als Überschrift („24h Störungsdienst“): kurz und ohne eigene Nummer –
        # sonst sperrt „… Notdienst: 0171 …“ auch das „Mobil: 0172 …“ in der nächsten Zeile.
        notdienst_kontext = bool(_NOTDIENST_RE.search(line)) or (
            i > 0
            and len(lines[i - 1]) <= 60
            and not _CANDIDATE_RE.search(lines[i - 1])
            and bool(_NOTDIENST_RE.search(lines[i - 1]))
        )
        last_end = 0
        for m in _CANDIDATE_RE.finditer(line):
            raw = m.group(0)
            if _DATE_RE.match(raw.strip()):
                last_end = m.end()
                continue
            region = line[last_end : m.start()]
            last_end = m.end()
            context = line[max(0, m.start() - 40) : m.start()]
            if _BAD_CONTEXT_RE.search(context) and not _LABEL_WORD_RE.search(region[-25:]):
                continue
            label = _label_before(region)
            if label is None and i > 0 and len(lines[i - 1]) <= 25 and _LABEL_WORD_RE.search(lines[i - 1]):
                label = _LABEL_WORD_RE.search(lines[i - 1]).group(1)  # type: ignore[union-attr]
            norm_label = _normalize_label(label)
            if norm_label == "Fax":
                continue
            if im_agentur_block:
                norm_label = "Dienstleister"
            elif notdienst_kontext:
                norm_label = "Notdienst"
            phone = classify_number(raw, source=source, source_url=source_url, label=norm_label)
            if phone is None:
                continue
            key = re.sub(r"\D", "", phone.e164)
            if norm_label in ("Notdienst", "Dienstleister"):
                gesperrt.add(key)
            elif norm_label == "WhatsApp":
                phone.person = _associate_same_line(index, i, line[: m.start()])
            else:
                phone.person = _associate(index, i, line[: m.start()])
            found.append(phone)
            digits_to_line.setdefault(key, i)

    for link in links:
        if link.kind == "tel":
            raw = unquote(link.href.split(":", 1)[1]).strip()
            raw = re.sub(r"[^\d+]", "", raw)
            if raw.startswith("00"):
                raw = "+" + raw[2:]
            label = _normalize_label(_label_before(link.text)) if link.text else None
            if link.text and _NOTDIENST_RE.search(link.text):
                label = "Notdienst"
            phone = classify_number(raw, source=source, source_url=source_url, label=label or "tel-link")
            if phone is None:
                continue
            key = re.sub(r"\D", "", phone.e164)
            if label in ("Notdienst", "Dienstleister"):
                gesperrt.add(key)
            elif key in gesperrt:
                phone.label = "Notdienst" if phone.label != "Dienstleister" else phone.label
            elif key in digits_to_line:
                phone.person = _associate(index, digits_to_line[key], "")
            else:
                names = find_plausible_names(link.text) if link.text else []
                phone.person = names[0] if names else None
            found.append(phone)
        elif link.kind == "whatsapp":
            number = parse_whatsapp_link(link.href)
            if not number:
                continue
            phone = classify_number(number, source="whatsapp", source_url=source_url, label="WhatsApp")
            if phone is None:
                continue
            if phone.kind == "unknown":
                phone.kind = "mobile"
            key = re.sub(r"\D", "", phone.e164)
            if key in gesperrt:
                phone.label = "Notdienst"
            elif key in digits_to_line:
                phone.person = _associate_same_line(index, digits_to_line[key], "")
            found.append(phone)

    # Eine Nummer, die irgendwo als Notdienst oder beim Dienstleister steht, bleibt es überall:
    # Wer sie als Bereitschaftshandy nutzt, will keinen Verkaufsanruf darauf.
    for phone in found:
        if re.sub(r"\D", "", phone.e164) in gesperrt:
            phone.person = None
            if phone.label not in ("Notdienst", "Dienstleister"):
                phone.label = "Notdienst"
    return dedupe_phones(found)


def dedupe_phones(phones: list[PhoneNumber]) -> list[PhoneNumber]:
    """Pro e164 ein Eintrag: mit Person > mit Label > Rest; Person/Label werden zusammengeführt."""
    best: dict[str, PhoneNumber] = {}
    order: list[str] = []
    for p in phones:
        cur = best.get(p.e164)
        if cur is None:
            best[p.e164] = p
            order.append(p.e164)
            continue
        rank_new = (0 if p.person else 1, 0 if p.label and p.label != "tel-link" else 1)
        rank_cur = (0 if cur.person else 1, 0 if cur.label and cur.label != "tel-link" else 1)
        if rank_new < rank_cur:
            merged = p.model_copy()
            merged.person = merged.person or cur.person
            merged.label = merged.label if merged.label and merged.label != "tel-link" else cur.label
            if merged.kind == "unknown" and cur.kind != "unknown":
                merged.kind = cur.kind
            best[p.e164] = merged
        else:
            if not cur.person and p.person:
                cur.person = p.person
            if (not cur.label or cur.label == "tel-link") and p.label:
                cur.label = p.label
            if cur.kind == "unknown" and p.kind != "unknown":
                cur.kind = p.kind
    return [best[k] for k in order]


# --- vCard ----------------------------------------------------------------------------------------

_ROLE_MAP: list[tuple[re.Pattern[str], RoleCategory]] = [
    (
        re.compile(r"geschäftsführ|geschaeftsfuehr|managing director|\bceo\b|geschäftsleit", re.I),
        "geschaeftsfuehrung",
    ),
    (re.compile(r"inhaber|eigentümer|owner", re.I), "inhaber"),
    (re.compile(r"vorstand|\bcfo\b|\bcoo\b|\bcto\b", re.I), "vorstand"),
    (re.compile(r"personal|human resources|\bhr\b|people", re.I), "hr"),
    (re.compile(r"ausbild|weiterbild", re.I), "ausbildung"),
    (re.compile(r"prokur", re.I), "prokura"),
    (re.compile(r"betriebsleit|niederlassungsleit|standortleit", re.I), "betriebsleitung"),
]


def _vcard_role(role: str | None) -> RoleCategory:
    if not role:
        return "sonstige"
    for pat, cat in _ROLE_MAP:
        if pat.search(role):
            return cat
    return "sonstige"


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def parse_vcard(vcf_text: str, source_url: str | None = None) -> list[Person]:
    people: list[Person] = []
    current: dict[str, list[str]] | None = None
    for line in _unfold(vcf_text):
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        key_up = key.upper()
        if key_up == "BEGIN" and value.strip().upper() == "VCARD":
            current = {}
            continue
        if key_up == "END" and current is not None:
            person = _person_from_vcard(current, source_url)
            if person:
                people.append(person)
            current = None
            continue
        if current is None:
            continue
        prop, *params = key_up.split(";")
        prop = prop.split(".")[-1]  # Gruppen wie "item1.TEL"
        current.setdefault(prop, []).append(";".join(params) + "\x00" + value.strip())
    return people


def _person_from_vcard(fields: dict[str, list[str]], source_url: str | None) -> Person | None:
    name = None
    if "FN" in fields:
        name = fields["FN"][0].split("\x00", 1)[1]
    elif "N" in fields:
        parts = fields["N"][0].split("\x00", 1)[1].split(";")
        family, given = (parts + ["", ""])[:2]
        name = f"{given} {family}".strip()
    if not name:
        return None
    name = normalize_name(name)
    role = None
    for key in ("TITLE", "ROLE"):
        if key in fields:
            role = fields[key][0].split("\x00", 1)[1] or None
            if role:
                break
    email = None
    if "EMAIL" in fields:
        email = fields["EMAIL"][0].split("\x00", 1)[1].lower() or None
    phones: list[PhoneNumber] = []
    for entry in fields.get("TEL", []):
        params, _, value = entry.partition("\x00")
        params_up = params.upper()
        is_cell = "CELL" in params_up or "MOBILE" in params_up
        is_fax = "FAX" in params_up
        if is_fax:
            continue
        value = re.sub(r"^tel:", "", value, flags=re.I)
        phone = classify_number(
            value, source="vcard", source_url=source_url, label="Mobil" if is_cell else "Tel", person=name
        )
        if phone:
            if is_cell and phone.kind == "unknown":
                phone.kind = "mobile"
            phones.append(phone)
    return Person(
        name=name,
        role=role,
        role_category=_vcard_role(role),
        phones=dedupe_phones(phones),
        email=email,
        source_url=source_url,
    )
