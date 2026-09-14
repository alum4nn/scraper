import pytest

from leadscraper.extract.size import estimate_size

U = "https://x.de/"


@pytest.mark.parametrize(
    ("text", "point", "lo", "hi", "conf"),
    [
        ("Unser Team aus 14 Mitarbeiterinnen und Mitarbeitern berät Sie gern.", 14, 14, 14, "high"),
        ("Mit über 100 Mitarbeitern an drei Standorten", 120, 100, 150, "high"),
        ("Wir sind ein 6-köpfiges Team", 6, 6, 6, "medium"),
        ("Mitarbeitende: 48", 48, 48, 48, "high"),
        ("Unser Team von 12 Immobilienprofis", 12, 12, 12, "medium"),
        ("rund 40 Beschäftigte", 40, 32, 49, "high"),
        ("zwischen 20 und 30 Mitarbeitern", 25, 20, 30, "high"),
        ("zwölf Mitarbeiter", 12, 12, 12, "high"),
        ("knapp 30 Kolleginnen und Kollegen", 27, 24, 30, "high"),
        ("1.200 Mitarbeiter", 1200, 1200, 1200, "high"),
    ],
)
def test_explicit_counts(text, point, lo, hi, conf):
    est = estimate_size([(U, text)])
    assert (est.point_estimate, est.employees_min, est.employees_max, est.confidence) == (point, lo, hi, conf)
    assert est.evidence and U in est.evidence[0]


@pytest.mark.parametrize(
    "text",
    [
        "seit über 30 Jahren für Sie da",
        "500 zufriedene Kunden",
        "3 Standorte in NRW",
        "100 % Qualität",
        "24 Stunden Notdienst",
        "über 200 Objekte verkauft",
        "gegründet 1998",
        "2.500 Referenzen",
    ],
)
def test_anti_patterns_ignored(text):
    est = estimate_size([(U, text)])
    assert est.point_estimate is None and est.confidence == "none"


def test_group_mention_not_preferred_over_local():
    text = "Die Gruppe beschäftigt weltweit 12.000 Mitarbeiter. Am Standort Köln sind 35 Kollegen für Sie da."
    est = estimate_size([(U, text)])
    assert est.point_estimate == 35
    assert any("Gruppe" in e for e in est.evidence)


def test_group_only_is_medium():
    est = estimate_size([(U, "Weltweit 12.000 Mitarbeiter")])
    assert est.point_estimate == 12000 and est.confidence == "medium"


def test_team_page_count_fallback():
    est = estimate_size([(U, "Herzlich willkommen")], team_member_count=7)
    assert (est.point_estimate, est.employees_min, est.employees_max, est.confidence) == (7, 7, 10, "medium")


def test_rechtsform_prior_and_rating_fallback():
    est = estimate_size([], rechtsform="e.K.")
    assert est.confidence == "low" and est.employees_max == 9
    est = estimate_size([], rechtsform="GmbH & Co. KG")
    assert est.employees_min == 10
    est = estimate_size([], user_rating_count=150)
    assert est.confidence == "low" and est.employees_max == 100
    assert estimate_size([]).confidence == "none"


def test_multiple_local_hits_take_median_of_best_unit():
    pages = [
        (U, "Team von 5"),
        (U + "ueber-uns", "25 Mitarbeiter"),
        (U + "karriere", "27 Mitarbeitende und 3 Azubis"),
    ]
    est = estimate_size(pages)
    assert est.point_estimate in (25, 27) and est.confidence == "high"


@pytest.mark.parametrize(
    "text",
    [
        "CAPITAL TOP-5 Makler Köln (5 Sterne) – unabhängige Auszeichnung",
        "F.A.Z. INSTITUT TOP 1.000 Makler Deutschlands",
        "Platz 3 Makler des Jahres",
        "Optimal für 2 Personen – Eckhaus in Bestform",
        "Wir sind 2019 in neue Büroräume umgezogen",
    ],
)
def test_ranks_and_household_sizes_are_not_headcounts(text):
    est = estimate_size([(U, text)])
    assert est.point_estimate is None and est.confidence == "none"


def test_team_besteht_aus_personen_counts():
    est = estimate_size([(U, "Unser Team besteht aus 12 Personen mit langjähriger Erfahrung.")])
    assert est.point_estimate == 12 and est.confidence == "medium"
