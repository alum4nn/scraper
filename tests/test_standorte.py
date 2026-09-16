"""Mehrere Standorte heißen: Für die Förderung zählt das ganze Unternehmen, nicht der Betrieb."""

from leadscraper.extract.standorte import standort_hinweise


def test_navigationspunkt_verraet_die_filialen():
    mehr, beleg, _ = standort_hinweise(["Willkommen"], ["Start", "Unsere Standorte", "Kontakt"])
    assert mehr and beleg and "Standorte" in beleg


def test_standort_und_anfahrt_ist_kein_hinweis():
    """Fast jeder Einzelbetrieb hat „Standort & Anfahrt“ in der Navigation."""
    mehr, _, _ = standort_hinweise(["Willkommen"], ["Standort & Anfahrt", "Impressum"])
    assert not mehr


def test_ausdrueckliche_zahl_zaehlt():
    mehr, beleg, _ = standort_hinweise(["Wir betreuen Sie an 7 Standorten in Norddeutschland."], [])
    assert mehr and beleg and "7 Standorten" in beleg


def test_eine_anschrift_bleibt_unauffaellig():
    zeilen = [
        "Mustermann Hausverwaltung GmbH",
        "Hauptstraße 5",
        "50667 Köln",
        "Zuständige Kammer: IHK Köln",
    ]
    mehr, _, plz = standort_hinweise(zeilen, ["Impressum", "Kontakt"])
    assert not mehr
    assert plz == 1


def test_zwei_anschriften_reichen_nicht():
    """Neben der eigenen Anschrift steht oft die der Schlichtungsstelle oder des Datenschutzbeauftragten."""
    zeilen = ["Hauptstraße 5", "50667 Köln", "Schlichtungsstelle, Postfach", "10179 Berlin"]
    mehr, _, plz = standort_hinweise(zeilen, [])
    assert not mehr and plz == 2


def test_drei_anschriften_wecken_verdacht():
    zeilen = ["50667 Köln", "40210 Düsseldorf", "53111 Bonn", "Unsere Büros"]
    mehr, beleg, plz = standort_hinweise(zeilen, [])
    assert mehr and plz == 3
    assert beleg and "verschiedene Anschriften" in beleg
