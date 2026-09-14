from pathlib import Path

from openpyxl import load_workbook

from leadscraper.demo import demo_leads
from leadscraper.excel import LEAD_COLUMNS, lead_rows, write_workbook
from leadscraper.funding import funding_reference_rows
from leadscraper.models import SearchSpec

SPEC = SearchSpec(queries=["Immobilienmakler"], city="Köln")


def test_workbook_structure_and_formats(tmp_path: Path):
    leads = demo_leads(SPEC)
    out = write_workbook(leads, SPEC, tmp_path / "demo.xlsx", funding_rows=funding_reference_rows())
    wb = load_workbook(out)
    assert wb.sheetnames == ["Leads", "Entscheider", "Alle Nummern", "Förderung", "Meta"]
    ws = wb["Leads"]
    headers = [c.value for c in ws[1]]
    assert headers == list(LEAD_COLUMNS)
    assert ws.max_row == len(leads) + 1
    assert ws.freeze_panes == "F2"
    assert ws.auto_filter.ref
    col = headers.index("Nummer") + 1
    cell = ws.cell(row=2, column=col)
    assert isinstance(cell.value, str) and cell.number_format == "@"
    web = ws.cell(row=2, column=headers.index("Webseite") + 1)
    assert web.hyperlink is not None and web.hyperlink.target.startswith("https://")
    score_col = headers.index("Score") + 1
    scores = [ws.cell(row=r, column=score_col).value for r in range(2, ws.max_row + 1)]
    assert scores == sorted(scores, reverse=True)
    assert ws.data_validations.dataValidation  # Dropdown "Status Akquise"
    people = wb["Entscheider"]
    first = [c.value for c in people[2]]
    assert first[5]  # erste Zeile hat Handy (Handy-Einträge zuerst)
    prem_col = headers.index("Premium") + 1
    assert [ws.cell(row=r, column=prem_col).value for r in range(2, ws.max_row + 1)].count("ja") == 2
    assert headers[:5] == ["Name", "Unternehmensname", "E-Mail", "Nummer", "Webseite"]
    meta = {row[0].value: row[1].value for row in wb["Meta"].iter_rows(min_row=2)}
    assert meta["Anzahl Firmen"] == len(leads)
    assert meta["Entscheider mit Handy"] == 2
    assert wb["Förderung"].max_row > 5


def test_lead_rows_and_empty_workbook(tmp_path: Path):
    rows = lead_rows(demo_leads(SPEC))
    assert rows[0]["Score"] >= rows[-1]["Score"]
    assert all(set(r) == set(LEAD_COLUMNS) for r in rows)
    out = write_workbook([], SPEC, tmp_path / "empty.xlsx")
    wb = load_workbook(out)
    assert [c.value for c in wb["Leads"][1]] == list(LEAD_COLUMNS)
    assert wb["Förderung"]["A1"].value  # Hinweis statt Tabelle
