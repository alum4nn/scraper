from leadscraper.exclusions import exclusion_reason, filter_chains
from leadscraper.models import Company


def test_domain_and_name_matching():
    ev = Company(place_id="1", name="Engel & Völkers Köln", website="https://www.engelvoelkers.com/de/koeln")
    remax = Company(place_id="2", name="RE/MAX Rheinland", website="https://remax-rheinland.de")
    small = Company(place_id="3", name="Berger Immobilien GmbH", website="https://berger-immobilien.example")
    allianz = Company(
        place_id="4", name="Allianz Generalvertretung Müller", website="https://vertretung.allianz.de/mueller"
    )
    assert "Domain" in exclusion_reason(ev)
    assert "Name" in exclusion_reason(remax)
    assert exclusion_reason(small) is None
    assert exclusion_reason(allianz) is not None
    kept, dropped = filter_chains([ev, remax, small, allianz])
    assert [c.place_id for c in kept] == ["3"]
    assert len(dropped) == 3


def test_name_match_is_substring_case_insensitive():
    c = Company(place_id="5", name="mcmakler gmbh", website=None)
    assert exclusion_reason(c) is not None


def test_real_estate_chains_and_portals_are_dropped():
    """Im Lauf aufgetauchte Ketten/Franchise/Portale (Impressum zeigt die Zentrale, nicht den Betrieb)."""
    from leadscraper.exclusions import filter_chains
    from leadscraper.models import Company

    chains = [
        Company(
            place_id="1",
            name="Deutsche Bank Immobilien Simon Palme",
            domain="deutsche-bank-immobilien.de",
        ),
        Company(place_id="2", name="PlanetHome AG Immobilien", domain="planethome.de"),
        Company(place_id="3", name="Evernest Köln", domain="evernest.com"),
        Company(place_id="4", name="CENTURY 21 Musterstadt", domain="century21.de"),
        Company(place_id="5", name="Dahler & Company Bonn", domain="dahler.com"),
    ]
    eigen = Company(place_id="9", name="Müller Immobilien GmbH", domain="mueller-immobilien.de")
    keep, dropped = filter_chains([*chains, eigen])
    assert [c.name for c in keep] == ["Müller Immobilien GmbH"]
    assert len(dropped) == len(chains)


def test_pflege_und_steuer_ketten_werden_aussortiert():
    """Neue Zielbranchen: Trägerkonzerne, Kanzleiverbünde und Versender sind keine Einzelbetriebe."""
    from leadscraper.exclusions import exclusion_reason
    from leadscraper.models import Company

    korian = Company(
        place_id="k1", name="Korian Seniorenzentrum Lindenhof", website="https://www.korian.de/x"
    )
    caritas = Company(place_id="k2", name="Caritas Sozialstation St. Martin", website=None)
    lohi = Company(place_id="k3", name="Lohnsteuerhilfeverein Beratungsstelle Bonn", website=None)
    etl = Company(place_id="k4", name="ETL Steuerberatung Nord GmbH", website="https://www.etl.de/nord")
    docmorris = Company(place_id="k5", name="DocMorris Apotheke", website="https://www.docmorris.de")
    eigen = Company(
        place_id="k6", name="Pflegedienst Sonnenschein GmbH", website="https://pflege-sonnenschein.example"
    )
    for kette in (korian, caritas, lohi, etl, docmorris):
        assert exclusion_reason(kette) is not None, kette.name
    assert exclusion_reason(eigen) is None
