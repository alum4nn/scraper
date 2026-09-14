from leadscraper.models import Company, Enrichment, Lead, Person, PhoneNumber, SearchSpec, SizeEstimate
from leadscraper.scoring import in_target_size, premium_check, score_lead, sort_key

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
    assert score == 50 + 20 + 3
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
    assert score == 25 + 20
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
    assert score == 0  # -40 -30 +10 → geklemmt auf 0
    assert in_target_size(lead, SPEC) is False
    assert any("außerhalb" in r for r in reasons)


def test_no_website_only_places_phone():
    enr = Enrichment(phones=[_mobile(None, "places")], size=SizeEstimate())
    lead = Lead(company=Company(place_id="4", name="D", phone="0171 5550123"), enrichment=enr)
    score, reasons = score_lead(lead, SPEC)
    assert score == 0  # -20 keine Website, +20 Handy ohne Name
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


def test_owner_signal_bonus():
    from leadscraper.scoring import owner_signal

    gf = Person(name="Thomas Berger", role="Geschäftsführer", role_category="geschaeftsfuehrung")
    enr = Enrichment(
        pages_crawled=["https://x"], people=[gf], phones=[_mobile(None, "kontakt")], size=SizeEstimate()
    )
    lead = Lead(
        company=Company(place_id="7", name="Berger Immobilien GmbH", website="https://x"), enrichment=enr
    )
    assert "Berger" in owner_signal(lead)
    score, reasons = score_lead(lead, SPEC)
    assert score == 20 + 10 + 10  # Handy ohne Name, Entscheider bekannt, inhabergeführt (mit Handy → +10)
    assert any("inhabergeführt" in r for r in reasons)

    enr2 = Enrichment(pages_crawled=["https://y"], rechtsform="e.K.", size=SizeEstimate())
    lead2 = Lead(company=Company(place_id="8", name="Elektro Kaminski", website="https://y"), enrichment=enr2)
    assert owner_signal(lead2) == "inhabergeführt: Rechtsform e.K."
    assert score_lead(lead2, SPEC)[0] == 5

    enr3 = Enrichment(
        pages_crawled=["https://z"],
        people=[Person(name="Anna Lang", role_category="hr")],
        size=SizeEstimate(),
    )
    lead3 = Lead(
        company=Company(place_id="9", name="Lang Logistik GmbH", website="https://z"), enrichment=enr3
    )
    assert owner_signal(lead3) is None  # HR zählt nicht als Inhaber-Signal


def test_premium_check_all_criteria():
    gf = Person(name="Thomas Berger", role_category="geschaeftsfuehrung", phones=[_mobile("Thomas Berger")])
    ok = Lead(
        company=Company(
            place_id="p1",
            name="Berger Immobilien GmbH",
            website="https://b.de",
            business_status="OPERATIONAL",
        ),
        enrichment=Enrichment(
            pages_crawled=["https://b.de/"],
            people=[gf],
            phones=[_mobile("Thomas Berger")],
            size=SizeEstimate(point_estimate=8, employees_min=8, employees_max=8, confidence="medium"),
            employment_signal="angestellt",
        ),
    )
    assert premium_check(ok, SPEC) == []

    # Größe nur indiziert (Rechtsform, niedrige Konfidenz) reicht – eine Zahl auf der Website ist nicht nötig
    weak = ok.model_copy(deep=True)
    weak.enrichment.employment_signal = "unklar"
    weak.enrichment.size = SizeEstimate(
        point_estimate=12, employees_min=5, employees_max=49, confidence="low"
    )
    assert premium_check(weak, SPEC) == []

    # gar kein Anhaltspunkt für Beschäftigte (keine Größe, kein Beschäftigten-Signal) → kein Premium
    bare = ok.model_copy(deep=True)
    bare.enrichment.employment_signal = "unklar"
    bare.enrichment.size = SizeEstimate()
    assert premium_check(bare, SPEC) == ["keine Anhaltspunkte für Beschäftigte (Ein-Personen-Betrieb?)"]

    # freie Handelsvertreter: § 82 SGB III fördert keine Selbstständigen
    frei = ok.model_copy(deep=True)
    frei.enrichment.employment_signal = "frei"
    assert premium_check(frei, SPEC)[0].startswith("freie Handelsvertreter")

    # Handynummer ohne jede Zuordnung reicht nicht
    anon = ok.model_copy(deep=True)
    anon.enrichment.people[0].phones = []
    assert premium_check(anon, SPEC) == ["keine Handynummer beim Entscheider"]

    # belegt zu groß (Angabe auf der Website)
    big = ok.model_copy(deep=True)
    big.enrichment.size = SizeEstimate(
        point_estimate=80, employees_min=80, employees_max=80, confidence="high"
    )
    assert premium_check(big, SPEC) == ["Betriebsgröße belegt außerhalb 5–50"]

    # aus Indizien geschätzt und rechnerisch unter 5 → bleibt Premium (Untergrenze, kein Ausschluss)
    tiny = ok.model_copy(deep=True)
    tiny.enrichment.size = SizeEstimate(
        point_estimate=3, employees_min=2, employees_max=4, confidence="medium"
    )
    assert premium_check(tiny, SPEC) == []

    # HR mit Handy ist kein Entscheider im Premium-Sinn
    hr = ok.model_copy(deep=True)
    hr.enrichment.people = [Person(name="Anja Roth", role_category="hr", phones=[_mobile("Anja Roth")])]
    assert premium_check(hr, SPEC) == ["kein Entscheider im Impressum erkannt"]

    # geschlossen / keine Website
    closed = ok.model_copy(deep=True)
    closed.company.business_status = "CLOSED_PERMANENTLY"
    assert premium_check(closed, SPEC)[0].startswith("Google-Status")
    assert premium_check(Lead(company=Company(place_id="x", name="X")), SPEC) == [
        "Website nicht erreichbar/keine Website"
    ]


def test_many_managing_directors_is_not_a_small_business():
    """Konzerne listen ein Dutzend Geschäftsführer – gefördert werden Betriebe mit 5–49 Beschäftigten."""
    people = [
        Person(name=f"Person {i}", role_category="geschaeftsfuehrung", phones=[_mobile(f"Person {i}")])
        for i in range(9)
    ]
    lead = Lead(
        company=Company(place_id="p", name="Großmakler GmbH", website="https://g.de"),
        enrichment=Enrichment(
            pages_crawled=["https://g.de/"],
            people=people,
            phones=[_mobile("Person 0")],
            size=SizeEstimate(point_estimate=40, employees_min=35, employees_max=63, confidence="medium"),
            employment_signal="angestellt",
        ),
    )
    assert any("Konzern" in m for m in premium_check(lead, SPEC))
