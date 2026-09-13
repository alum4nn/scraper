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
