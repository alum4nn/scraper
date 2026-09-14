from leadscraper.geo import bundesland_from_plz, normalize_bundesland
from leadscraper.models import Company, Enrichment, Lead, Person, PhoneNumber, SizeEstimate


def test_normalize_bundesland():
    assert normalize_bundesland("Nordrhein-Westfalen") == "Nordrhein-Westfalen"
    assert normalize_bundesland("North Rhine-Westphalia") == "Nordrhein-Westfalen"
    assert normalize_bundesland("bayern") == "Bayern"
    assert normalize_bundesland("Baden-Wurttemberg") == "Baden-Württemberg"
    assert normalize_bundesland(None) is None
    assert normalize_bundesland("Atlantis") is None


def test_bundesland_from_plz():
    assert bundesland_from_plz("50667") == "Nordrhein-Westfalen"
    assert bundesland_from_plz("80331") == "Bayern"
    assert bundesland_from_plz("01067") == "Sachsen"
    assert bundesland_from_plz("20095") == "Hamburg"
    assert bundesland_from_plz("x") is None
    assert bundesland_from_plz(None) is None


def test_size_in_range():
    assert SizeEstimate().in_range(5, 50) is None
    assert SizeEstimate(point_estimate=20).in_range(5, 50) is True
    assert SizeEstimate(point_estimate=80).in_range(5, 50) is False
    assert SizeEstimate(employees_min=40, employees_max=60).in_range(5, 50) is True  # überlappt
    assert SizeEstimate(employees_min=60, employees_max=90).in_range(5, 50) is False
    assert SizeEstimate(employees_min=1, employees_max=3).in_range(5, None) is False
    assert SizeEstimate(point_estimate=3).in_range(None, 50) is True


def _pn(e164, kind, source, person=None):
    return PhoneNumber(raw=e164, e164=e164, national=e164, kind=kind, source=source, person=person)


def test_lead_best_mobile_and_contact():
    gf = Person(name="Thomas Berger", role_category="geschaeftsfuehrung")
    hr = Person(
        name="Anja Roth", role_category="hr", phones=[_pn("+491515550999", "mobile", "team", "Anja Roth")]
    )
    other = Person(name="Kai Sonst", role_category="sonstige")
    enr = Enrichment(
        people=[other, hr, gf],
        phones=[
            _pn("+492215550000", "landline", "impressum"),
            _pn("+491765550321", "mobile", "whatsapp"),
            _pn("+491515550999", "mobile", "team", "Anja Roth"),
        ],
    )
    lead = Lead(company=Company(place_id="1", name="X"), enrichment=enr)
    assert lead.best_contact is hr  # Handy schlägt Rollen-Priorität
    enr.phones = [enr.phones[0]]
    hr.phones = []
    assert lead.best_contact is gf  # ohne Handys entscheidet die Rollen-Priorität
    assert lead.best_mobile.e164 == "+491515550999"  # Nummer mit Person vor WhatsApp ohne Person
    assert [p.name for p in enr.decision_makers] == ["Thomas Berger", "Anja Roth"]
    assert Lead(company=Company(place_id="2", name="Y")).best_mobile is None
