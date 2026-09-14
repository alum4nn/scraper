import pytest

from leadscraper.extract.names import find_names, is_probable_person_name, normalize_name, surname


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
