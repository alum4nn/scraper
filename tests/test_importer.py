from pathlib import Path

from openpyxl import Workbook

from leadscraper.importer import read_company_list


def test_csv_semicolon_with_german_headers(tmp_path: Path):
    f = tmp_path / "firmen.csv"
    f.write_text(
        "Firma;Webseite;Telefon;PLZ;Ort\n"
        "Berger Immobilien GmbH;www.berger-immobilien.example;0221 5550000;50667;Köln\n"
        ";https://ohne-name.example;;;\n"
        "Leer;;;;\n",
        encoding="utf-8",
    )
    cs = read_company_list(f)
    assert [c.name for c in cs] == ["Berger Immobilien GmbH", "ohne-name.example", "Leer"]
    assert cs[0].website == "https://www.berger-immobilien.example"
    assert cs[0].domain == "berger-immobilien.example"
    assert cs[0].bundesland == "Nordrhein-Westfalen"
    assert cs[0].place_id == "list-1"
    assert cs[2].website is None


def test_xlsx_with_leading_zero_plz(tmp_path: Path):
    f = tmp_path / "liste.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Name", "URL", "Plz"])
    ws.append(["Elbe Makler", "elbe-makler.example", 1067])
    ws.append([None, None, None])
    wb.save(f)
    cs = read_company_list(f)
    assert len(cs) == 1
    assert cs[0].plz == "01067"
    assert cs[0].bundesland == "Sachsen"
