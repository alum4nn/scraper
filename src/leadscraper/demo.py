"""Beispiel-Leads für `leadscraper demo` – zeigt das Excel-Format ohne API-Key und ohne Internet.

Alle Firmen, Personen, Domains und Rufnummern sind frei erfunden.
"""

from __future__ import annotations

from leadscraper import funding, scoring
from leadscraper.models import Company, Enrichment, Lead, Person, PhoneNumber, SearchSpec, SizeEstimate


def _pn(
    raw: str, e164: str, kind: str, source: str, url: str, label: str | None = None, person: str | None = None
) -> PhoneNumber:
    return PhoneNumber(
        raw=raw, e164=e164, national=raw, kind=kind, source=source, source_url=url, label=label, person=person
    )


def _lead(company: Company, enr: Enrichment | None, spec: SearchSpec) -> Lead:
    lead = Lead(company=company, enrichment=enr)
    lead.funding = funding.assess(enr.size, company.bundesland) if enr else None
    lead.in_target_size = scoring.in_target_size(lead, spec)
    lead.score, lead.score_reasons = scoring.score_lead(lead, spec)
    return lead


def demo_leads(spec: SearchSpec) -> list[Lead]:
    site = "https://www.rheinblick-immobilien-koeln.de"
    berger_mobile = _pn(
        "0171 5550123", "+491715550123", "mobile", "team", f"{site}/team/", "Mobil", "Thomas Berger"
    )
    rheinblick = Enrichment(
        website=site,
        impressum_url=f"{site}/impressum/",
        legal_name="Rheinblick Immobilien GmbH",
        rechtsform="GmbH",
        handelsregister="HRB 87654",
        amtsgericht="Amtsgericht Köln",
        ustid="DE298765432",
        impressum_street="Rheinuferstraße 12",
        impressum_plz="50667",
        impressum_city="Köln",
        people=[
            Person(
                name="Thomas Berger",
                role="Geschäftsführer",
                role_category="geschaeftsfuehrung",
                phones=[berger_mobile],
                email="t.berger@rheinblick-immobilien-koeln.de",
                source_url=f"{site}/impressum/",
            ),
            Person(
                name="Julia Kranz",
                role="Immobilienmaklerin",
                role_category="sonstige",
                phones=[
                    _pn(
                        "0172 5550456",
                        "+491725550456",
                        "mobile",
                        "team",
                        f"{site}/team/",
                        "Mobil",
                        "Julia Kranz",
                    )
                ],
                source_url=f"{site}/team/",
            ),
        ],
        phones=[
            _pn("0221 5550000", "+492215550000", "landline", "impressum", f"{site}/impressum/", "Tel"),
            berger_mobile,
            _pn("0172 5550456", "+491725550456", "mobile", "team", f"{site}/team/", "Mobil", "Julia Kranz"),
        ],
        emails=["info@rheinblick-immobilien-koeln.de", "t.berger@rheinblick-immobilien-koeln.de"],
        instagram_url="https://www.instagram.com/rheinblick.immobilien",
        whatsapp_url="https://wa.me/491715550123",
        size=SizeEstimate(
            employees_min=9,
            employees_max=9,
            point_estimate=9,
            confidence="high",
            evidence=[f"Text: „Unser Team aus 9 Mitarbeitern begleitet Sie“ ({site}/)"],
        ),
        call_indicators=[
            "Betriebsgröße < 50 → 100 % Lehrgangskosten möglich (§ 82 SGB III)",
            "Digitalisierung auf der Website erwähnt",
        ],
        pages_crawled=[f"{site}/", f"{site}/impressum/", f"{site}/kontakt/", f"{site}/team/"],
    )
    site2 = "https://www.sonnenhof-immobilien-bonn.de"
    sonnenhof_mobile = _pn(
        "0160 5550777",
        "+491605550777",
        "mobile",
        "kontakt",
        f"{site2}/kontakt/",
        "Mobil",
        "Claudia Sonnenhof",
    )
    sonnenhof = Enrichment(
        website=site2,
        impressum_url=f"{site2}/impressum/",
        legal_name="Sonnenhof Immobilien e.K.",
        rechtsform="e.K.",
        handelsregister="HRA 4711",
        amtsgericht="Amtsgericht Bonn",
        impressum_street="Poppelsdorfer Allee 8",
        impressum_plz="53115",
        impressum_city="Bonn",
        people=[
            Person(
                name="Claudia Sonnenhof",
                role="Inhaberin",
                role_category="inhaber",
                phones=[sonnenhof_mobile],
                source_url=f"{site2}/impressum/",
            )
        ],
        phones=[
            _pn("0228 5550300", "+492285550300", "landline", "impressum", f"{site2}/impressum/", "Tel"),
            sonnenhof_mobile,
        ],
        emails=["info@sonnenhof-immobilien-bonn.de"],
        whatsapp_url="https://wa.me/491605550777",
        size=SizeEstimate(
            employees_min=6,
            employees_max=6,
            point_estimate=6,
            confidence="medium",
            evidence=[f"Text: „ein kleines Team von sechs Immobilienprofis“ ({site2}/)"],
        ),
        call_indicators=["Betriebsgröße < 50 → 100 % Lehrgangskosten möglich (§ 82 SGB III)"],
        pages_crawled=[f"{site2}/", f"{site2}/impressum/", f"{site2}/kontakt/"],
    )
    site3 = "https://www.weber-lind-steuerberater.de"
    weber = Enrichment(
        website=site3,
        impressum_url=f"{site3}/impressum/",
        legal_name="Weber & Lind Steuerberater PartG mbB",
        rechtsform="PartG mbB",
        people=[
            Person(
                name="Markus Weber",
                role="Partner",
                role_category="geschaeftsfuehrung",
                source_url=f"{site3}/impressum/",
            ),
            Person(
                name="Anja Roth",
                role="Leitung Personal",
                role_category="hr",
                email="a.roth@weber-lind.de",
                source_url=f"{site3}/team/",
            ),
        ],
        phones=[_pn("0201 5550900", "+492015550900", "landline", "impressum", f"{site3}/impressum/", "Tel")],
        emails=["a.roth@weber-lind.de"],
        size=SizeEstimate(
            employees_min=23,
            employees_max=23,
            point_estimate=23,
            confidence="medium",
            evidence=[f"Text: „Unser 23-köpfiges Team betreut“ ({site3}/)"],
        ),
        call_indicators=[
            "Karriere-/Stellenseite vorhanden",
            "sucht Personal",
            "KI/Digitalisierung auf der Website erwähnt",
            "HR-/Ausbildungsverantwortliche benannt",
        ],
        pages_crawled=[f"{site3}/", f"{site3}/impressum/", f"{site3}/team/", f"{site3}/karriere/"],
    )
    site4 = "https://www.pixelwerk-digital-agentur.de"
    pixelwerk = Enrichment(
        website=site4,
        impressum_url=f"{site4}/impressum.html",
        legal_name="Pixelwerk Digital GmbH",
        rechtsform="GmbH",
        people=[
            Person(
                name="Lena Hoffmann",
                role="Geschäftsführer",
                role_category="geschaeftsfuehrung",
                source_url=f"{site4}/impressum.html",
            ),
            Person(
                name="Daniel Schuster",
                role="Geschäftsführer",
                role_category="geschaeftsfuehrung",
                source_url=f"{site4}/impressum.html",
            ),
        ],
        phones=[],
        emails=["hallo@pixelwerk-digital-agentur.de"],
        size=SizeEstimate(
            employees_min=5,
            employees_max=49,
            point_estimate=12,
            confidence="low",
            evidence=["Rechtsform GmbH (typische Größe 5–49)"],
        ),
        pages_crawled=[f"{site4}/", f"{site4}/impressum.html"],
        errors=["wenig Text (SPA oder Cookie-Wall?)"],
    )
    site5 = "https://www.pflege-am-park-koeln.de"
    pflege = Enrichment(
        website=site5,
        impressum_url=f"{site5}/impressum",
        legal_name="Pflege am Park GmbH",
        rechtsform="GmbH",
        people=[
            Person(
                name="Renate Kühn",
                role="Geschäftsführerin",
                role_category="geschaeftsfuehrung",
                source_url=f"{site5}/impressum",
            )
        ],
        phones=[_pn("0221 5550600", "+492215550600", "landline", "impressum", f"{site5}/impressum", "Tel")],
        size=SizeEstimate(
            employees_min=60,
            employees_max=90,
            point_estimate=72,
            confidence="high",
            evidence=[f"Text: „über 60 Mitarbeitende in der ambulanten Pflege“ ({site5}/ueber-uns)"],
        ),
        pages_crawled=[f"{site5}/", f"{site5}/impressum", f"{site5}/ueber-uns"],
    )
    nowebsite = Enrichment(
        phones=[_pn("0170 5550999", "+491705550999", "mobile", "places", "https://maps.google.com/?cid=1")],
        size=SizeEstimate(
            employees_min=1,
            employees_max=9,
            point_estimate=3,
            confidence="low",
            evidence=["3 Google-Bewertungen (schwaches Signal)"],
        ),
        errors=["keine Website bei Google Places"],
    )

    companies = [
        (
            Company(
                place_id="demo-1",
                name="Rheinblick Immobilien GmbH",
                street="Rheinuferstraße 12",
                plz="50667",
                city="Köln",
                bundesland="Nordrhein-Westfalen",
                phone="0221 5550000",
                website=site,
                domain="rheinblick-immobilien-koeln.de",
                primary_type="real_estate_agency",
                rating=4.9,
                user_rating_count=120,
                business_status="OPERATIONAL",
                google_maps_uri="https://maps.google.com/?cid=1001",
                query="Immobilienmakler",
            ),
            rheinblick,
        ),
        (
            Company(
                place_id="demo-2",
                name="Sonnenhof Immobilien",
                street="Poppelsdorfer Allee 8",
                plz="53115",
                city="Bonn",
                bundesland="Nordrhein-Westfalen",
                phone="0228 5550300",
                website=site2,
                domain="sonnenhof-immobilien-bonn.de",
                primary_type="real_estate_agency",
                rating=4.7,
                user_rating_count=34,
                business_status="OPERATIONAL",
                google_maps_uri="https://maps.google.com/?cid=1002",
                query="Immobilienmakler",
            ),
            sonnenhof,
        ),
        (
            Company(
                place_id="demo-3",
                name="Weber & Lind Steuerberater",
                street="Kettwiger Straße 45",
                plz="45127",
                city="Essen",
                bundesland="Nordrhein-Westfalen",
                phone="0201 5550900",
                website=site3,
                domain="weber-lind-steuerberater.de",
                primary_type="accounting",
                rating=4.8,
                user_rating_count=15,
                business_status="OPERATIONAL",
                google_maps_uri="https://maps.google.com/?cid=1003",
                query="Steuerberater",
            ),
            weber,
        ),
        (
            Company(
                place_id="demo-4",
                name="Pixelwerk Digital GmbH",
                street="Hansaring 20",
                plz="50670",
                city="Köln",
                bundesland="Nordrhein-Westfalen",
                phone="0221 5550200",
                website=site4,
                domain="pixelwerk-digital-agentur.de",
                primary_type="corporate_office",
                rating=4.6,
                user_rating_count=8,
                business_status="OPERATIONAL",
                google_maps_uri="https://maps.google.com/?cid=1004",
                query="Werbeagentur",
            ),
            pixelwerk,
        ),
        (
            Company(
                place_id="demo-5",
                name="Pflege am Park",
                street="Parkstraße 3",
                plz="50931",
                city="Köln",
                bundesland="Nordrhein-Westfalen",
                phone="0221 5550600",
                website=site5,
                domain="pflege-am-park-koeln.de",
                primary_type="home_health_care_service",
                rating=4.2,
                user_rating_count=41,
                business_status="CLOSED_TEMPORARILY",
                google_maps_uri="https://maps.google.com/?cid=1005",
                query="Pflegedienst",
            ),
            pflege,
        ),
        (
            Company(
                place_id="demo-6",
                name="Makler Müller",
                street="Venloer Straße 300",
                plz="50823",
                city="Köln",
                bundesland="Nordrhein-Westfalen",
                phone="0170 5550999",
                primary_type="real_estate_agency",
                rating=4.0,
                user_rating_count=3,
                business_status="OPERATIONAL",
                google_maps_uri="https://maps.google.com/?cid=1006",
                query="Immobilienmakler",
            ),
            nowebsite,
        ),
    ]
    leads = [_lead(c, e, spec) for c, e in companies]
    leads.sort(key=scoring.sort_key)
    return leads
