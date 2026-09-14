import asyncio
from pathlib import Path

import pytest
from openpyxl import load_workbook

from leadscraper import pipeline
from leadscraper.cache import Cache
from leadscraper.crawler import SiteCrawler
from leadscraper.excel import write_workbook
from leadscraper.funding import funding_reference_rows
from leadscraper.models import Company, SearchSpec
from leadscraper.places import PlacesClient

web = pytest.mark.usefixtures("fixture_web")


def _enrich(settings, website: str, name: str = "Test", **company_kw):
    async def go():
        crawler = SiteCrawler(settings)
        try:
            return await pipeline.enrich_company(
                Company(place_id="t", name=name, website=website, **company_kw), crawler
            )
        finally:
            await crawler.close()

    return asyncio.run(go())


@web
def test_makler_gf_mobile_found_outside_impressum(fast_settings):
    enr = _enrich(fast_settings, "https://www.rheinblick-immobilien-koeln.de/", user_rating_count=120)
    assert enr.legal_name == "Rheinblick Immobilien GmbH"
    assert enr.rechtsform == "GmbH" and enr.handelsregister == "HRB 87654" and enr.ustid == "DE298765432"
    assert (enr.impressum_street, enr.impressum_plz, enr.impressum_city) == (
        "Rheinuferstraße 12",
        "50667",
        "Köln",
    )
    gf = next(p for p in enr.people if p.name == "Thomas Berger")
    assert gf.role_category == "geschaeftsfuehrung"
    assert gf.mobile is not None and gf.mobile.e164 == "+491715550123"
    assert gf.mobile.source_url and "impressum" not in gf.mobile.source_url
    assert gf.email == "t.berger@rheinblick-immobilien-koeln.de"
    kranz = next(p for p in enr.people if p.name == "Julia Kranz")
    assert kranz.mobile is not None and kranz.mobile.e164 == "+491725550456"
    assert not any(p.name == "Lena Hoffmann" for p in enr.people)  # Web-Agentur im Impressum ignoriert
    assert "+492215550001" not in {p.e164 for p in enr.phones}  # Fax
    assert enr.size.point_estimate == 9 and enr.size.confidence == "high"
    assert enr.whatsapp_url == "https://wa.me/491715550123"
    assert enr.instagram_url and "instagram.com" in enr.instagram_url
    assert any("100 % Lehrgangskosten" in i for i in enr.call_indicators)


@web
def test_makler2_inhaberin_mobile_on_kontakt_and_whatsapp(fast_settings):
    enr = _enrich(fast_settings, "www.sonnenhof-immobilien-bonn.de")
    assert enr.rechtsform == "e.K."
    inh = next(p for p in enr.people if p.name == "Claudia Sonnenhof")
    assert inh.role_category == "inhaber"
    assert inh.mobile is not None and inh.mobile.e164 == "+491605550777"
    wa = [p for p in enr.phones if p.e164 == "+491605550777"]
    assert len(wa) == 1 and wa[0].kind == "mobile"
    brandt = next(p for p in enr.people if p.name == "Tim Brandt")
    assert brandt.mobile is not None and brandt.mobile.e164 == "+4915155507788"
    assert enr.size.point_estimate == 6


@web
def test_steuer_partner_mobile_via_tel_link_and_hr_contact(fast_settings):
    enr = _enrich(fast_settings, "https://www.weber-lind-steuerberater.de")
    assert enr.rechtsform == "PartG mbB"
    names = {p.name: p for p in enr.people}
    assert names["Markus Weber"].role_category == "geschaeftsfuehrung"
    assert names["Sonja Lind"].role_category == "geschaeftsfuehrung"
    assert names["Sonja Lind"].mobile is not None and names["Sonja Lind"].mobile.e164 == "+4915155509991"
    assert names["Anja Roth"].role_category == "hr" and names["Anja Roth"].email == "a.roth@weber-lind.de"
    assert enr.size.point_estimate == 23
    assert "HR-/Ausbildungsverantwortliche benannt" in enr.call_indicators
    assert "sucht Personal" in enr.call_indicators
    assert "KI/Digitalisierung auf der Website erwähnt" in enr.call_indicators


@web
def test_agentur_spa_no_mobile_and_no_fax(fast_settings):
    enr = _enrich(fast_settings, "https://www.pixelwerk-digital-agentur.de")
    assert {p.name for p in enr.people} == {"Lena Hoffmann", "Daniel Schuster"}
    assert all(p.role_category == "geschaeftsfuehrung" for p in enr.people)
    assert enr.mobiles == []
    assert enr.phones == []  # Fax verworfen, sonst nichts
    assert "hallo@pixelwerk-digital-agentur.de" in enr.emails


def test_no_website_uses_places_phone(fast_settings):
    company = Company(place_id="x", name="Makler Müller", phone="0170 5550999", user_rating_count=3)

    async def go():
        crawler = SiteCrawler(fast_settings)
        try:
            return await pipeline.enrich_company(company, crawler)
        finally:
            await crawler.close()

    enr = asyncio.run(go())
    assert enr.mobiles and enr.mobiles[0].source == "places"
    assert enr.size.confidence == "low"


@web
def test_search_dedupes_and_filters_chains(fast_settings):
    spec = SearchSpec(queries=["Immobilienmakler"], city="Köln", max_results_per_query=10)

    async def go():
        client = PlacesClient(fast_settings.google_places_api_key)
        try:
            return await pipeline.search_companies(spec, client)
        finally:
            await client.close()

    companies = asyncio.run(go())
    ids = [c.place_id for c in companies]
    assert ids == ["ChIJ-rheinblick", "ChIJ-sonnenhof", "ChIJ-weber", "ChIJ-pixelwerk", "ChIJ-nowebsite"]
    assert spec.lat is not None  # geocodiert
    assert companies[0].bundesland == "Nordrhein-Westfalen" and companies[0].plz == "50667"


@web
def test_end_to_end_build_leads_and_excel(fast_settings, tmp_path: Path):
    spec = SearchSpec(queries=["Immobilienmakler"], city="Köln", min_employees=5, max_employees=50)

    async def go():
        client = PlacesClient(fast_settings.google_places_api_key)
        try:
            companies = await pipeline.search_companies(spec, client)
        finally:
            await client.close()
        cache = Cache(fast_settings.cache_path)
        try:
            return await pipeline.build_leads(companies, spec, fast_settings, cache)
        finally:
            cache.close()

    leads = asyncio.run(go())
    names = [ld.display_name for ld in leads]
    # Die drei Firmen mit Entscheider-Handy stehen oben, SPA-Agentur und Firma ohne Website unten
    assert set(names[:3]) == {
        "Rheinblick Immobilien GmbH",
        "Sonnenhof Immobilien e.K.",
        "Weber & Lind Steuerberater PartG mbB",
    }
    assert all(ld.best_contact and ld.best_contact.mobile for ld in leads[:3])
    assert names[3:] == ["Pixelwerk Digital GmbH", "Makler Müller"]
    assert [ld.score for ld in leads] == sorted((ld.score for ld in leads), reverse=True)
    rb = next(ld for ld in leads if ld.display_name == "Rheinblick Immobilien GmbH")
    assert rb.best_contact.name == "Thomas Berger" and rb.best_mobile.e164 == "+491715550123"
    assert rb.funding.size_band == "<50" and rb.funding.lehrgangskosten_pct == 100
    assert rb.funding.landesprogramm == "Bildungsscheck NRW 2.0"
    assert rb.in_target_size is True
    px = next(ld for ld in leads if ld.display_name == "Pixelwerk Digital GmbH")
    assert px.best_mobile is None

    mobile_only = [
        ld for ld in leads if pipeline.passes_filters(ld, SearchSpec(queries=["x"], require_mobile=True))
    ]
    assert {ld.display_name for ld in mobile_only} >= {
        "Rheinblick Immobilien GmbH",
        "Sonnenhof Immobilien e.K.",
    }
    assert all(ld.best_mobile for ld in mobile_only)

    out = write_workbook(leads, spec, tmp_path / "leads.xlsx", funding_rows=funding_reference_rows())
    wb = load_workbook(out)
    ws = wb["Leads"]
    headers = [c.value for c in ws[1]]
    row = dict(zip(headers, [c.value for c in ws[2]], strict=False))
    assert row["Firma"] == leads[0].display_name
    assert row["Handy Entscheider"] == leads[0].best_contact.mobile.national
    assert row["Firmenname Quelle"] == "Impressum"
    assert row["Straße"] == leads[0].address[0]
    assert wb["Entscheider"].max_row >= 4
