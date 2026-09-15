"""Der Weg ohne Google: OpenStreetMap-Abruf, Dublettenabbau, CSV für enrich-list."""

import csv

import pytest

from leadscraper.osm import OverpassError, bauen, fetch_branch, write_csv


def _antwort(elemente: list[dict]) -> dict:
    return {"version": 0.6, "elements": elemente}


BETRIEBE = [
    {
        "type": "node",
        "id": 1,
        "tags": {
            "name": "Steuerkanzlei Meier",
            "office": "tax_advisor",
            "website": "www.kanzlei-meier.de",
            "phone": "+49 221 1234560",
            "addr:street": "Hauptstraße",
            "addr:housenumber": "5",
            "addr:postcode": "50667",
            "addr:city": "Köln",
        },
    },
    # Derselbe Betrieb als Gebäudeumriss: darf nicht doppelt in die Liste
    {
        "type": "way",
        "id": 2,
        "tags": {"name": "Steuerkanzlei Meier", "contact:website": "https://kanzlei-meier.de/kontakt"},
    },
    # Ohne Website: für die Pipeline wertlos, zählt aber in der Abdeckung mit
    {"type": "node", "id": 3, "tags": {"name": "Kanzlei ohne Netz", "office": "tax_advisor"}},
    # Ohne Namen
    {"type": "node", "id": 4, "tags": {"office": "tax_advisor", "website": "https://namenlos.de"}},
]


def test_abfrage_umschliesst_das_land():
    abfrage = bauen('["office"="tax_advisor"]')
    assert '["ISO3166-1"="DE"][admin_level=2]' in abfrage
    assert 'nwr["office"="tax_advisor"](area.gebiet)' in abfrage
    assert abfrage.endswith("out tags center;")


def test_fuehrt_zusammen_und_zaehlt_die_abdeckung(httpx_mock):
    httpx_mock.add_response(json=_antwort(BETRIEBE), is_reusable=True)
    ergebnis = fetch_branch(['["office"="tax_advisor"]'], pause=0)
    assert ergebnis.objekte == 4
    assert ergebnis.mit_name == 3
    assert ergebnis.mit_website == 3
    assert [f.name for f in ergebnis.firmen] == ["Steuerkanzlei Meier"]
    firma = ergebnis.firmen[0]
    assert firma.website == "https://www.kanzlei-meier.de"  # fehlendes Schema ergänzt
    assert firma.street == "Hauptstraße 5"
    assert firma.plz == "50667"
    assert firma.bundesland == "Nordrhein-Westfalen"  # aus der Postleitzahl


def test_ohne_website_nur_auf_wunsch(httpx_mock):
    httpx_mock.add_response(json=_antwort(BETRIEBE), is_reusable=True)
    ergebnis = fetch_branch(['["office"="tax_advisor"]'], nur_mit_website=False, pause=0)
    assert {f.name for f in ergebnis.firmen} == {"Steuerkanzlei Meier", "Kanzlei ohne Netz"}


def test_ueberlasteter_server_wird_gewechselt(httpx_mock):
    httpx_mock.add_response(status_code=504, text="zu viel los")
    httpx_mock.add_response(json=_antwort(BETRIEBE[:1]))
    ergebnis = fetch_branch(['["office"="tax_advisor"]'], pause=0)
    assert len(ergebnis.firmen) == 1
    assert len(httpx_mock.get_requests()) == 2


def test_dauerhafter_fehler_wird_gemeldet(httpx_mock):
    httpx_mock.add_response(status_code=400, text="kaputte Abfrage", is_reusable=True)
    with pytest.raises(OverpassError) as fehler:
        fetch_branch(['["office"="kaputt"]'], pause=0)
    assert "400" in str(fehler.value)


def test_csv_passt_zum_importer(httpx_mock, tmp_path):
    from leadscraper.importer import read_company_list

    httpx_mock.add_response(json=_antwort(BETRIEBE), is_reusable=True)
    ergebnis = fetch_branch(['["office"="tax_advisor"]'], pause=0)
    ziel = tmp_path / "osm.csv"
    write_csv(ergebnis.firmen, ziel)

    zeilen = list(csv.reader(ziel.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))
    assert zeilen[0][:2] == ["Firma", "Website"]
    # und der Importer versteht die Datei wieder
    firmen = read_company_list(ziel)
    assert [f.name for f in firmen] == ["Steuerkanzlei Meier"]
    assert firmen[0].website == "https://www.kanzlei-meier.de"
    assert firmen[0].city == "Köln"


def test_gibt_erst_nach_mehreren_runden_auf(httpx_mock, monkeypatch):
    """Overpass ist gespendete Rechenzeit und oft belegt – Aufgeben nach drei Versuchen wäre zu früh."""
    from leadscraper import osm as osm_mod

    monkeypatch.setattr(osm_mod, "_WARTEN", (0.0,))
    httpx_mock.add_response(status_code=504, text="belegt", is_reusable=True)
    with pytest.raises(OverpassError) as fehler:
        fetch_branch(['["office"="tax_advisor"]'], pause=0)
    assert len(httpx_mock.get_requests()) == 9  # drei Runden über drei Spiegel
    assert "kostet nichts" in str(fehler.value)


def test_beachtet_retry_after(httpx_mock, monkeypatch):
    """Nennt der Server selbst eine Wartezeit, gilt sie – nicht die eigene Schätzung."""
    from leadscraper import osm as osm_mod

    gewartet: list[float] = []
    monkeypatch.setattr(osm_mod.time, "sleep", lambda s: gewartet.append(s))
    httpx_mock.add_response(status_code=429, headers={"Retry-After": "7"}, text="zu schnell")
    httpx_mock.add_response(json=_antwort(BETRIEBE[:1]))
    ergebnis = fetch_branch(['["office"="tax_advisor"]'], pause=0)
    assert len(ergebnis.firmen) == 1
    assert gewartet == [7.0]
