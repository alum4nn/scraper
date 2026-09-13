from leadscraper.models import Company, Enrichment, Lead, Person, PhoneNumber, SearchSpec, SizeEstimate
from leadscraper.scoring import in_target_size, score_lead, sort_key

SPEC = SearchSpec(queries=["x"], min_employees=5, max_employees=50)


def _mobile(person=None, source="team"):
    return PhoneNumber(
        raw="0171 5550123",
        e164="+491715550123",
        national="0171 5550123",
        kind="mobile",
        source=source,
        person=person,
    )


def _landline():
    return PhoneNumber(
        raw="0221 5550000", e164="+492215550000", national="0221 5550000", kind="landline", source="impressum"
    )


def test_decider_with_mobile_scores_highest():
    gf = Person(
        name="Thomas Berger",
        role="Geschäftsführer",
        role_category="geschaeftsfuehrung",
        phones=[_mobile("Thomas Berger")],
    )
    enr = Enrichment(
        pages_crawled=["https://a.example/"],
        people=[gf],
        phones=[_mobile("Thomas Berger"), _landline()],
        emails=["info@a.example"],
        size=SizeEstimate(point_estimate=9, employees_min=9, employees_max=9, confidence="high"),
    )
    lead = Lead(
        company=Company(place_id="1", name="A", website="https://a.example", business_status="OPERATIONAL"),
        enrichment=enr,
    )
    score, reasons = score_lead(lead, SPEC)
    assert score == 40 + 20 + 5
    assert any("Entscheider mit Handy" in r for r in reasons)
    assert in_target_size(lead, SPEC) is True


def test_mobile_without_name_small_company():
    enr = Enrichment(
        pages_crawled=["https://b.example/"],
        phones=[_mobile(None, "kontakt")],
        size=SizeEstimate(point_estimate=6, employees_min=6, employees_max=6, confidence="high"),
    )
    lead = Lead(company=Company(place_id="2", name="B", website="https://b.example"), enrichment=enr)
    score, reasons = score_lead(lead, SPEC)
    assert score == 30 + 20
    assert any("Kleinbetrieb" in r for r in reasons)


def test_out_of_range_and_closed_penalised():
    enr = Enrichment(
        pages_crawled=["https://c.example/"],
        people=[Person(name="Lena Hoffmann", role_category="geschaeftsfuehrung")],
        phones=[_landline()],
        size=SizeEstimate(point_estimate=80, employees_min=70, employees_max=90, confidence="high"),
    )
    lead = Lead(
        company=Company(
            place_id="3", name="C", website="https://c.example", business_status="CLOSED_TEMPORARILY"
        ),
        enrichment=enr,
    )
    score, reasons = score_lead(lead, SPEC)
    assert score == 0  # -40 -30 +15 → geklemmt auf 0
    assert in_target_size(lead, SPEC) is False
    assert any("außerhalb" in r for r in reasons)


def test_no_website_only_places_phone():
    enr = Enrichment(phones=[_mobile(None, "places")], size=SizeEstimate())
    lead = Lead(company=Company(place_id="4", name="D", phone="0171 5550123"), enrichment=enr)
    score, reasons = score_lead(lead, SPEC)
    assert score == -20 + 25 if False else score == 5
    assert "keine Website" in reasons
    assert in_target_size(lead, SPEC) is None


def test_unreachable_website():
    enr = Enrichment(website="https://e.example", pages_crawled=[], errors=["timeout"])
    lead = Lead(company=Company(place_id="5", name="E", website="https://e.example"), enrichment=enr)
    score, reasons = score_lead(lead, SPEC)
    assert score == 0 and "Website nicht erreichbar" in reasons


def test_sort_key():
    a = Lead(company=Company(place_id="1", name="Zeta"), score=50)
    b = Lead(company=Company(place_id="2", name="alpha"), score=50)
    c = Lead(company=Company(place_id="3", name="Beta"), score=90)
    assert [ld.company.name for ld in sorted([a, b, c], key=sort_key)] == ["Beta", "alpha", "Zeta"]
