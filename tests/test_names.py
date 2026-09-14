import pytest

from leadscraper.extract.names import (
    find_names,
    find_plausible_names,
    is_plausible_person_name,
    is_probable_person_name,
    normalize_name,
    surname,
)


@pytest.mark.parametrize(
    "name",
    [
        "Thomas Berger",
        "Dr. Hans-Peter Müller-Lüdenscheidt",
        "Frau Dipl.-Ing. Sabine van der Berg",
        "Karl Heinz Schmidt",
        "Prof. Dr. med. Anna Öztürk",
        "Jean-Claude Léon",
        "Herr Peter Kaminski",
        "M. Weber",
    ],
)
def test_probable_names(name):
    assert is_probable_person_name(name)


@pytest.mark.parametrize(
    "text",
    [
        "Musterstraße 12",
        "Max Mustermann GmbH",
        "Köln Hauptbahnhof",
        "Rheinblick Immobilien",
        "Geschäftsführer Thomas",
        "Herzlich Willkommen",
        "Unser Team",
        "Thomas",
        "THOMAS BERGER",
        "Berger Immobilien Verwaltung Gesellschaft Mit",
        "Montag Freitag",
        "Bergisch Gladbach",
        "Amtsgericht Köln",
    ],
)
def test_improbable_names(text):
    assert not is_probable_person_name(text)


def test_find_names_in_impressum_line():
    names = find_names(
        "Geschäftsführer: Dr. Hans-Peter Müller-Lüdenscheidt und Anna Schmidt, Prokurist: Kai Lang"
    )
    assert names == ["Dr. Hans-Peter Müller-Lüdenscheidt", "Anna Schmidt", "Kai Lang"]


def test_find_names_trims_role_words_and_dedupes():
    text = "Thomas Berger Geschäftsführer\nIhr Ansprechpartner: Thomas Berger\nMusterstraße 5, 50667 Köln"
    assert find_names(text) == ["Thomas Berger"]


def test_find_names_ignores_company_and_places():
    assert find_names("Rheinblick Immobilien GmbH, Amtsgericht Köln HRB 12345, Bergisch Gladbach") == []


def test_normalize_and_surname():
    assert normalize_name("Herrn Dr. med. Hans-Peter Müller ") == "Hans-Peter Müller"
    assert normalize_name("Frau Anna Schmidt") == "Anna Schmidt"
    assert surname("Dr. Sabine van der Berg") == "Berg"
    assert surname("Karl Heinz Schmidt jun.") == "Schmidt"
    assert surname("") == ""


@pytest.mark.parametrize(
    "text",
    [
        "Baupläne Wohnflächenberechnung",  # Substantiv-Suffix -ung (≥ 9 Zeichen)
        "Transparente Kommunikation",
        "Bevorzugte Kontaktart",
        "Mein Konto",
    ],
)
def test_nouns_are_not_names(text):
    assert not is_probable_person_name(text)


def test_short_ung_surnames_survive_suffix_rule():
    assert is_probable_person_name("Carl Jung") and is_probable_person_name("Petra Hartung")
    assert is_probable_person_name("Julia Kranz") and is_probable_person_name("Nina Lenz")


@pytest.mark.parametrize(
    ("text", "plausible"),
    [
        ("Stephan Hollenders", True),
        ("Hans-Peter Müller", True),
        ("Dipl.-Kff. Julia Braschoß", True),
        ("Herr Yüksel Turan", True),  # Anrede belegt die Person trotz unbekanntem Vornamen
        ("Karl Heinz Schmidt", True),
        ("Stadtbezirk Hörde", False),
        ("Häufige Fragen", False),
        ("Yüksel Turan", False),  # ohne Kontext nicht sicher genug
        ("Immobilienbewertung Frechen", False),
    ],
)
def test_plausible_person_name_requires_known_first_name_or_salutation(text, plausible):
    assert is_plausible_person_name(text) is plausible


def test_find_plausible_names_uses_salutation_from_context():
    text = "Kontakt: Herr Yüksel Turan, Fachliche Kompetenz, Anna Heck, Stadtbezirk Hörde, Nazim Uzun"
    assert find_plausible_names(text) == ["Yüksel Turan", "Anna Heck"]
