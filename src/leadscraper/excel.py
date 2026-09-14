"""Excel-Export (openpyxl).

Vertrag:
- write_workbook(leads: list[Lead], spec: SearchSpec, path: Path, *,
                 funding_rows: list[dict] | None = None) -> Path
  Blätter:
  1. "Leads" – eine Zeile pro Firma, sortiert nach Score. Spalten (in dieser Reihenfolge):
     Name (Entscheider) | Unternehmensname | E-Mail | Nummer (Handy Entscheider) | Webseite | Score |
     Premium | Premium-Check | Rolle | Handy Fundstelle | Weitere Handynummern | Festnetz (Places) |
     Festnetz (Website) | Mitarbeiter (Schätzung) | MA min | MA max | MA Konfidenz | MA Beleg |
     Im Zielbereich | Beschäftigte | Beschäftigte Beleg | Förderband | Lehrgangskosten % | AEZ % |
     Landesprogramm | Pitch | Anruf-Indikatoren | Branche (Places) | Straße | PLZ | Ort | Bundesland |
     Impressum-URL | Rechtsform | Register | Google-Bewertung | Anzahl Bewertungen | Status | Google Maps |
     LinkedIn | XING | WhatsApp | Suchbegriff | Score-Begründung | Fehler | Gescrapt am | Firmenname Quelle |
     CRM-Spalten (leer, mit Dropdown-Validierung): Status Akquise (offen/angerufen/Termin/kein Interesse/
     Wiedervorlage) | Termin am | Notizen | Nächster Schritt
  2. "Entscheider" – eine Zeile pro Person mit Rolle, Handy, Festnetz, E-Mail, Firma, Website, Fundstelle,
     sortiert: Personen mit Handy zuerst, dann Rollen-Priorität.
  3. "Alle Nummern" – jede gefundene Nummer: Firma, Nummer (national), E.164, Art (mobil/festnetz/…),
     Label, Person, Quelle, Fundstelle-URL.
  4. "Förderung" – Referenztabelle aus funding_rows (Band, Lehrgangskosten %, AEZ %, Bonus, Landesprogramme).
  5. "Meta" – Suchparameter (spec), Datum, Anzahl Firmen/Leads mit Handy/Entscheider mit Handy, Hinweise
     (Google-ToS: Places-Daten ≤ 30 Tage nutzen; §7 UWG: Telefon B2B bei mutmaßlichem Interesse).
  Formatierung: Kopfzeile fett + Hintergrund, Autofilter, Fixierung (A2 / erste 3 Spalten), sinnvolle
  Spaltenbreiten (max 60), Telefonnummern als TEXT (keine Zahl!), Score bedingt formatiert (Farbskala),
  URLs als Hyperlinks, Zeilenumbruch in Beleg/Notizen/Pitch. Datei speichern und Pfad zurückgeben.
- lead_rows(leads) -> list[dict]: die Zeilen des Leads-Blatts (für Tests/CSV).

Spaltenlogik "Name" / "Nummer" (Leads-Blatt):
- Name = Entscheider, d. h. Person mit Rolle ≠ "sonstige"; Personen MIT Handynummer zuerst, dann
  ROLE_PRIORITY (dieselbe Reihenfolge wie im Blatt "Entscheider"). Gibt es keine, fällt die Spalte auf
  Lead.best_contact zurück.
- Nummer = Handynummer dieser Person. Hat sie keine, wird eine Handynummer OHNE
  Personenzuordnung (z. B. WhatsApp-Nummer der Firma) eingetragen – nie die Nummer einer anderen Person.
- Weitere Handynummern = alle übrigen Handynummern, bei bekannter Person mit Name in Klammern.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from leadscraper.models import (
    ROLE_PRIORITY,
    Enrichment,
    FundingAssessment,
    Lead,
    Person,
    PhoneNumber,
    SearchSpec,
    SizeEstimate,
)

SHEET_LEADS = "Leads"
SHEET_PEOPLE = "Entscheider"
SHEET_PHONES = "Alle Nummern"
SHEET_FUNDING = "Förderung"
SHEET_META = "Meta"

CRM_COLUMNS: tuple[str, ...] = ("Status Akquise", "Termin am", "Notizen", "Nächster Schritt")
LEAD_COLUMNS: tuple[str, ...] = (
    "Name",
    "Unternehmensname",
    "E-Mail",
    "Nummer",
    "Webseite",
    "Score",
    "Premium",
    "Premium-Check",
    "Rolle",
    "Handy Fundstelle",
    "Weitere Handynummern",
    "Festnetz (Places)",
    "Festnetz (Website)",
    "Mitarbeiter (Schätzung)",
    "MA min",
    "MA max",
    "MA Konfidenz",
    "MA Beleg",
    "Im Zielbereich",
    "Beschäftigte",
    "Beschäftigte Beleg",
    "Förderband",
    "Lehrgangskosten %",
    "AEZ %",
    "Landesprogramm",
    "Pitch",
    "Anruf-Indikatoren",
    "Branche (Places)",
    "Straße",
    "PLZ",
    "Ort",
    "Bundesland",
    "Impressum-URL",
    "Rechtsform",
    "Register",
    "Google-Bewertung",
    "Anzahl Bewertungen",
    "Status",
    "Google Maps",
    "LinkedIn",
    "XING",
    "WhatsApp",
    "Suchbegriff",
    "Score-Begründung",
    "Fehler",
    "Gescrapt am",
    "Firmenname Quelle",
    *CRM_COLUMNS,
)
PEOPLE_COLUMNS: tuple[str, ...] = (
    "Firma",
    "Ort",
    "Name",
    "Rolle",
    "Kategorie",
    "Handy",
    "Festnetz",
    "E-Mail",
    "Website",
    "Fundstelle",
)
PHONE_COLUMNS: tuple[str, ...] = (
    "Firma",
    "Nummer",
    "E.164",
    "Art",
    "Label",
    "Person",
    "Quelle",
    "Fundstelle",
)
META_COLUMNS: tuple[str, ...] = ("Parameter", "Wert")

AKQUISE_STATUS: tuple[str, ...] = ("offen", "angerufen", "Termin", "kein Interesse", "Wiedervorlage")

DATE_FORMAT = "DD.MM.YYYY HH:MM"
DAY_FORMAT = "DD.MM.YYYY"
TEXT_FORMAT = "@"
MIN_WIDTH = 8
MAX_WIDTH = 60

TOS_NOTE = (
    "Google Maps Platform: Firmenname, Adresse und Telefon stammen aus dem Impressum der Firmenwebsite; "
    "Google-Daten (Spalten 'Firmenname Quelle = Google', 'Festnetz (Places)', Bewertung, Google Maps) sind "
    "nur Fallback/Referenz und dürfen nicht dauerhaft gespeichert oder weitergegeben werden."
)
UWG_NOTE = (
    "§ 7 UWG: Telefonanrufe bei Unternehmen (B2B) nur bei mutmaßlichem Interesse zulässig – bei geförderter "
    "Mitarbeiter-Weiterbildung i. d. R. gegeben. Keine Kalt-E-Mails, SMS oder WhatsApp-Nachrichten ohne "
    "Einwilligung; WhatsApp-Nummern nur telefonisch nutzen."
)
NO_FUNDING_NOTE = "Keine Förderdaten übergeben (funding_rows leer) – siehe config/foerderung.yaml."

# Spalten mit Telefonnummern/PLZ: Textformat, damit Excel führende Nullen nicht verschluckt.
_LEAD_TEXT_COLUMNS = frozenset(
    {"Nummer", "Weitere Handynummern", "Festnetz (Places)", "Festnetz (Website)", "PLZ"}
)
_LEAD_LINK_COLUMNS = frozenset(
    {"Handy Fundstelle", "Webseite", "Impressum-URL", "Google Maps", "LinkedIn", "XING", "WhatsApp"}
)
_LEAD_WRAP_COLUMNS = frozenset(
    {
        "Pitch",
        "MA Beleg",
        "Score-Begründung",
        "Notizen",
        "Fehler",
        "Anruf-Indikatoren",
        "Premium-Check",
        "Beschäftigte Beleg",
    }
)

_KIND_LABEL = {"mobile": "mobil", "landline": "festnetz", "voip": "voip", "unknown": "unbekannt"}
_CONFIDENCE_LABEL = {"high": "hoch", "medium": "mittel", "low": "niedrig", "none": ""}
_TARGET_LABEL = {True: "ja", False: "nein", None: "unbekannt"}
_ROLE_LABEL = {
    "geschaeftsfuehrung": "Geschäftsführung",
    "inhaber": "Inhaber/-in",
    "vorstand": "Vorstand",
    "hr": "Personal / HR",
    "ausbildung": "Ausbildungsleitung",
    "prokura": "Prokura",
    "betriebsleitung": "Betriebsleitung",
    "sonstige": "",
}

_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill(fill_type="solid", start_color="1F4E78", end_color="1F4E78")
_HEADER_ALIGN = Alignment(vertical="center", wrap_text=True)
_DATA_ALIGN = Alignment(vertical="top")
_DATA_ALIGN_WRAP = Alignment(vertical="top", wrap_text=True)


# --- Öffentliche API ------------------------------------------------------------------------------


def write_workbook(
    leads: list[Lead],
    spec: SearchSpec,
    path: Path,
    *,
    funding_rows: list[dict[str, Any]] | None = None,
) -> Path:
    """Schreibt alle fünf Blätter nach `path` (Ordner wird angelegt) und gibt den Pfad zurück."""
    path = Path(path)
    ordered = _sorted_leads(leads)

    wb = Workbook()
    ws_leads = wb.active
    ws_leads.title = SHEET_LEADS
    rows = lead_rows(ordered)
    n_leads = _write_table(
        ws_leads,
        LEAD_COLUMNS,
        ([row[col] for col in LEAD_COLUMNS] for row in rows),
        text_columns=_LEAD_TEXT_COLUMNS,
        link_columns=_LEAD_LINK_COLUMNS,
        wrap_columns=_LEAD_WRAP_COLUMNS,
        freeze="F2",
    )
    _format_leads_sheet(ws_leads, n_leads)

    _write_table(
        wb.create_sheet(SHEET_PEOPLE),
        PEOPLE_COLUMNS,
        _people_rows(ordered),
        text_columns={"Handy", "Festnetz"},
        link_columns={"Website", "Fundstelle"},
    )
    _write_table(
        wb.create_sheet(SHEET_PHONES),
        PHONE_COLUMNS,
        _phone_rows(ordered),
        text_columns={"Nummer", "E.164"},
        link_columns={"Fundstelle"},
    )
    _write_funding(wb.create_sheet(SHEET_FUNDING), funding_rows)
    _write_meta(wb.create_sheet(SHEET_META), ordered, spec)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def lead_rows(leads: list[Lead]) -> list[dict[str, Any]]:
    """Zeilen des Leads-Blatts (Schlüssel = Spaltenüberschriften), sortiert nach Score, dann Firmenname."""
    return [_lead_row(lead) for lead in _sorted_leads(leads)]


# --- Zeilen ---------------------------------------------------------------------------------------


def _sorted_leads(leads: list[Lead]) -> list[Lead]:
    return sorted(leads, key=lambda ld: (-ld.score, ld.company.name.lower()))


def _lead_row(lead: Lead) -> dict[str, Any]:
    company = lead.company
    enr = lead.enrichment
    size = enr.size if enr else SizeEstimate()
    funding = lead.funding or FundingAssessment()
    person = _primary_person(lead)
    mobile = _primary_mobile(lead, person)
    street, plz, city = lead.address
    row: dict[str, Any] = {
        "Score": lead.score,
        "Premium": "ja" if lead.premium else "nein",
        "Premium-Check": "erfüllt" if lead.premium else "\n".join(lead.premium_missing),
        "Unternehmensname": lead.display_name,
        "Name": person.name if person else "",
        "Rolle": _role_label(person) if person else "",
        "Nummer": mobile.national if mobile else "",
        "Handy Fundstelle": (mobile.source_url or "") if mobile else "",
        "Weitere Handynummern": ", ".join(_other_mobiles(enr, mobile)),
        "Festnetz (Places)": company.phone or "",
        "Festnetz (Website)": _website_landline(enr),
        "E-Mail": _email(person, enr),
        "Mitarbeiter (Schätzung)": size.point_estimate,
        "MA min": size.employees_min,
        "MA max": size.employees_max,
        "MA Konfidenz": _CONFIDENCE_LABEL.get(size.confidence, size.confidence) if enr else "",
        "MA Beleg": "\n".join(size.evidence[:3]),
        "Im Zielbereich": _TARGET_LABEL[lead.in_target_size],
        "Förderband": funding.size_band or "",
        "Lehrgangskosten %": funding.lehrgangskosten_pct,
        "AEZ %": funding.arbeitsentgeltzuschuss_pct,
        "Landesprogramm": funding.landesprogramm or "",
        "Pitch": funding.pitch or "",
        "Anruf-Indikatoren": "\n".join(enr.call_indicators) if enr else "",
        "Beschäftigte": {"angestellt": "angestellt", "frei": "freie Vertreter?", "unklar": "unklar"}[
            enr.employment_signal
        ]
        if enr
        else "",
        "Beschäftigte Beleg": "\n".join(enr.employment_evidence[:4]) if enr else "",
        "Branche (Places)": company.primary_type or "",
        "Straße": street or "",
        "PLZ": plz or "",
        "Ort": city or "",
        "Bundesland": company.bundesland or "",
        "Webseite": company.website or (enr.website if enr else None) or "",
        "Impressum-URL": (enr.impressum_url if enr else None) or "",
        "Rechtsform": (enr.rechtsform if enr else None) or "",
        "Register": _register(enr),
        "Google-Bewertung": company.rating,
        "Anzahl Bewertungen": company.user_rating_count,
        "Status": company.business_status or "",
        "Google Maps": company.google_maps_uri or "",
        "LinkedIn": (enr.linkedin_url if enr else None) or "",
        "XING": (enr.xing_url if enr else None) or "",
        "WhatsApp": (enr.whatsapp_url if enr else None) or "",
        "Suchbegriff": company.query or "",
        "Score-Begründung": "\n".join(lead.score_reasons),
        "Fehler": "\n".join(enr.errors) if enr else "",
        "Gescrapt am": lead.scraped_at,
        "Firmenname Quelle": "Impressum"
        if enr and enr.legal_name
        else ("Liste" if company.place_id.startswith("list-") else "Google"),
    }
    row.update(dict.fromkeys(CRM_COLUMNS, ""))
    return row


def _people_rows(leads: list[Lead]) -> list[list[Any]]:
    """Entscheider-Blatt: alle Personen mit Rolle ≠ sonstige oder mit Handynummer."""
    entries: list[tuple[tuple[int, int], list[Any]]] = []
    for lead in leads:
        enr = lead.enrichment
        if not enr:
            continue
        company = lead.company
        for person in enr.people:
            mobile = _person_phone(person, enr, "mobile")
            if person.role_category == "sonstige" and not mobile:
                continue
            landline = _person_phone(person, enr, "landline")
            sort_key = (0 if mobile else 1, ROLE_PRIORITY.get(person.role_category, 9))
            entries.append(
                (
                    sort_key,
                    [
                        lead.display_name,
                        lead.address[2] or "",
                        person.name,
                        _role_label(person),
                        person.role_category,
                        mobile.national if mobile else "",
                        landline.national if landline else "",
                        person.email or "",
                        company.website or enr.website or "",
                        (mobile.source_url if mobile else None) or person.source_url or "",
                    ],
                )
            )
    entries.sort(key=lambda e: e[0])  # stabil: innerhalb einer Gruppe bleibt die Score-Reihenfolge
    return [row for _, row in entries]


def _phone_rows(leads: list[Lead]) -> Iterable[list[Any]]:
    for lead in leads:
        if not lead.enrichment:
            continue
        for phone in lead.enrichment.phones:
            yield [
                lead.display_name,
                phone.national,
                phone.e164,
                _KIND_LABEL.get(phone.kind, phone.kind),
                phone.label or "",
                phone.person or "",
                phone.source,
                phone.source_url or "",
            ]


def _meta_rows(leads: list[Lead], spec: SearchSpec) -> list[tuple[str, Any]]:
    ort = spec.city or (f"{spec.lat}, {spec.lng}" if spec.lat is not None and spec.lng is not None else "")
    return [
        ("Erstellt am", datetime.now()),
        ("Suchbegriffe", ", ".join(spec.queries)),
        ("Ort", ort),
        ("Radius km", spec.radius_km),
        ("Places-Typ", spec.included_type or ""),
        ("Max. Treffer je Suchbegriff", spec.max_results_per_query),
        ("Mitarbeiter von", spec.min_employees),
        ("Mitarbeiter bis", spec.max_employees),
        ("Nur mit Handy", "ja" if spec.require_mobile else "nein"),
        ("Premium-Filter", "ja" if spec.premium else "nein"),
        ("Premium-Leads", sum(1 for ld in leads if ld.premium)),
        ("Anzahl Firmen", len(leads)),
        ("mit Handynummer", sum(1 for ld in leads if ld.best_mobile is not None)),
        ("Entscheider mit Handy", sum(1 for ld in leads if _has_decision_maker_with_mobile(ld))),
        ("Hinweis Google-ToS", TOS_NOTE),
        ("Hinweis § 7 UWG", UWG_NOTE),
    ]


# --- Auswahl Entscheider / Nummern ----------------------------------------------------------------


def _same_name(a: str, b: str) -> bool:
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


def _person_phone(person: Person, enr: Enrichment, kind: str) -> PhoneNumber | None:
    """Nummer der Person: zuerst aus person.phones, sonst namensgleiche Nummer aus enrichment.phones."""
    own = next((p for p in person.phones if p.kind == kind), None)
    if own:
        return own
    return next(
        (p for p in enr.phones if p.kind == kind and p.person and _same_name(p.person, person.name)),
        None,
    )


def _primary_person(lead: Lead) -> Person | None:
    enr = lead.enrichment
    if not enr:
        return None
    decision_makers = enr.decision_makers  # bereits nach ROLE_PRIORITY sortiert
    with_mobile = [p for p in decision_makers if _person_phone(p, enr, "mobile")]
    if with_mobile:
        return with_mobile[0]
    return lead.best_contact


def _primary_mobile(lead: Lead, person: Person | None) -> PhoneNumber | None:
    enr = lead.enrichment
    if not enr:
        return None
    if person:
        own = _person_phone(person, enr, "mobile")
        if own:
            return own
    best = lead.best_mobile
    if best and not best.person:
        return best
    return next((m for m in enr.mobiles if not m.person), None)


def _other_mobiles(enr: Enrichment | None, primary: PhoneNumber | None) -> list[str]:
    if not enr:
        return []
    seen: set[str] = {primary.e164} if primary else set()
    out: list[str] = []
    for m in enr.mobiles:
        if m.e164 in seen:
            continue
        seen.add(m.e164)
        out.append(f"{m.national} ({m.person})" if m.person else m.national)
    return out


def _has_decision_maker_with_mobile(lead: Lead) -> bool:
    enr = lead.enrichment
    if not enr:
        return False
    return any(_person_phone(p, enr, "mobile") for p in enr.decision_makers)


def _website_landline(enr: Enrichment | None) -> str:
    if not enr:
        return ""
    phone = next((p for p in enr.phones if p.kind == "landline" and p.source != "places"), None)
    return phone.national if phone else ""


def _email(person: Person | None, enr: Enrichment | None) -> str:
    if person and person.email:
        return person.email
    if enr and enr.emails:
        return enr.emails[0]
    return ""


def _register(enr: Enrichment | None) -> str:
    if not enr:
        return ""
    if enr.handelsregister and enr.amtsgericht:
        return f"{enr.handelsregister} ({enr.amtsgericht})"
    return enr.handelsregister or enr.amtsgericht or ""


def _role_label(person: Person) -> str:
    return person.role or _ROLE_LABEL.get(person.role_category, person.role_category)


# --- Blätter schreiben / formatieren --------------------------------------------------------------


def _write_table(
    ws: Worksheet,
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    text_columns: Collection[str] = (),
    link_columns: Collection[str] = (),
    wrap_columns: Collection[str] = (),
    freeze: str = "A2",
) -> int:
    """Schreibt Kopfzeile + Datenzeilen mit Formatierung; gibt die Anzahl der Datenzeilen zurück."""
    widths = [len(h) for h in headers]
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGN

    n_rows = 0
    for row in rows:
        n_rows += 1
        for col_idx, (header, value) in enumerate(zip(headers, row, strict=True), start=1):
            cell = ws.cell(row=n_rows + 1, column=col_idx, value=_cell_value(value))
            if header in link_columns and _is_url(value):
                # Erst der benannte Stil (setzt alle Stilattribute), dann Feinheiten darüber.
                cell.hyperlink = value
                cell.style = "Hyperlink"
            cell.alignment = _DATA_ALIGN_WRAP if header in wrap_columns else _DATA_ALIGN
            if header in text_columns:
                cell.number_format = TEXT_FORMAT
            elif isinstance(value, datetime):
                cell.number_format = DATE_FORMAT
            widths[col_idx - 1] = max(widths[col_idx - 1], _display_len(value))

    for col_idx, width in enumerate(widths, start=1):
        letter = get_column_letter(col_idx)
        ws.column_dimensions[letter].width = min(MAX_WIDTH, max(MIN_WIDTH, width + 2))
        if headers[col_idx - 1] in text_columns:
            # Auch später von Hand eingetragene Nummern bleiben Text.
            ws.column_dimensions[letter].number_format = TEXT_FORMAT
    ws.freeze_panes = freeze
    ws.auto_filter.ref = ws.dimensions
    return n_rows


def _format_leads_sheet(ws: Worksheet, n_rows: int) -> None:
    """Farbskala für Score, Dropdown für 'Status Akquise', Datumsformat für 'Termin am'."""
    last = max(2, n_rows + 1)
    score_col = get_column_letter(LEAD_COLUMNS.index("Score") + 1)
    ws.conditional_formatting.add(
        f"{score_col}2:{score_col}{last}",
        ColorScaleRule(
            start_type="num",
            start_value=0,
            start_color="F8696B",
            mid_type="num",
            mid_value=50,
            mid_color="FFEB84",
            end_type="num",
            end_value=100,
            end_color="63BE7B",
        ),
    )

    status_col = get_column_letter(LEAD_COLUMNS.index("Status Akquise") + 1)
    validation = DataValidation(
        type="list",
        formula1='"' + ",".join(AKQUISE_STATUS) + '"',
        allow_blank=True,
        errorTitle="Status Akquise",
        error="Bitte einen Status aus der Liste wählen.",
    )
    ws.add_data_validation(validation)
    validation.add(f"{status_col}2:{status_col}{last}")

    termin_col = get_column_letter(LEAD_COLUMNS.index("Termin am") + 1)
    for row_idx in range(2, last + 1):
        ws[f"{termin_col}{row_idx}"].number_format = DAY_FORMAT


def _write_funding(ws: Worksheet, funding_rows: list[dict[str, Any]] | None) -> None:
    if not funding_rows:
        ws["A1"] = NO_FUNDING_NOTE
        ws.column_dimensions["A"].width = MAX_WIDTH
        return
    headers = list(funding_rows[0].keys())
    _write_table(
        ws,
        headers,
        ([row.get(h, "") for h in headers] for row in funding_rows),
        link_columns=headers,
        wrap_columns=headers,
    )


def _write_meta(ws: Worksheet, leads: list[Lead], spec: SearchSpec) -> None:
    _write_table(ws, META_COLUMNS, _meta_rows(leads, spec), wrap_columns={"Wert"})


# --- Zellwerte ------------------------------------------------------------------------------------


def _cell_value(value: Any) -> Any:
    if value == "":
        return None
    if isinstance(value, datetime) and value.tzinfo is not None:
        # Excel kennt keine Zeitzonen → lokale Zeit ohne tzinfo.
        return value.astimezone().replace(tzinfo=None)
    return value


def _is_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def _display_len(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, datetime):
        return len(DATE_FORMAT)
    return max(len(line) for line in str(value).splitlines() or [""])
