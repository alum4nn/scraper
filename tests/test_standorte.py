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
    mehr, _, orte = standort_hinweise(zeilen, ["Impressum", "Kontakt"])
    assert not mehr
    assert orte == 1


def test_zwei_anschriften_reichen_nicht():
    """Neben der eigenen Anschrift steht oft die der Schlichtungsstelle oder des Datenschutzbeauftragten."""
    zeilen = ["Hauptstraße 5", "50667 Köln", "Schlichtungsstelle, Postfach", "10179 Berlin"]
    mehr, _, orte = standort_hinweise(zeilen, [])
    assert not mehr and orte == 2


def test_mehrere_postleitzahlen_derselben_stadt_sind_ein_standort():
    """Ein Münchner Maklerbüro nennt im Impressum schnell fünf Münchner Postleitzahlen."""
    zeilen = ["80336 München", "80333 München", "80802 München", "81675 München"]
    mehr, _, orte = standort_hinweise(zeilen, [])
    assert not mehr
    assert orte == 1


def test_stadtteile_und_schreibweisen_zaehlen_einmal():
    zeilen = ["60311 Frankfurt am Main", "60313 Frankfurt", "65760 Eschborn"]
    mehr, _, orte = standort_hinweise(zeilen, [])
    assert not mehr and orte == 2


def test_drei_anschriften_wecken_verdacht():
    zeilen = ["50667 Köln", "40210 Düsseldorf", "53111 Bonn", "Unsere Büros"]
    mehr, beleg, orte = standort_hinweise(zeilen, [])
    assert mehr and orte == 3
    assert beleg and "Anschriften in 3 Orten" in beleg


def test_schreibweise_und_sprache_machen_keinen_zweiten_standort():
    """„München.“, „München“ und „Munich“ sind derselbe Ort – vorher zählten sie dreifach."""
    zeilen = ["80538 München", "80333 München.", "80333 Munich", "68161 Mannheim Postfach"]
    mehr, _, orte = standort_hinweise(zeilen, [])
    assert orte == 2
    assert not mehr
