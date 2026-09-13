from leadscraper.dedupe import dedupe_companies, normalize_domain, normalize_phone_key
from leadscraper.models import Company


def test_normalize_domain():
    assert normalize_domain("https://www.beispiel-makler.de/team/") == "beispiel-makler.de"
    assert normalize_domain("shop.beispiel.co.uk") == "beispiel.co.uk"
    assert normalize_domain("") is None
    assert normalize_domain(None) is None


def test_normalize_phone_key():
    assert normalize_phone_key("0221 123456") == "49221123456"
    assert normalize_phone_key("+49 (0) 221 123456") == "49221123456"
    assert normalize_phone_key("0049 221 123456") == "49221123456"
    assert normalize_phone_key("123") is None
    assert normalize_phone_key(None) is None


def test_dedupe_by_place_domain_phone():
    a = Company(place_id="1", name="A", website="https://www.foo.de/x", phone="0221 123456", query="q1")
    b = Company(place_id="2", name="A GmbH", website="http://foo.de", query="q2", plz="50667")
    c = Company(place_id="3", name="B", phone="+49 221 123456", query="q3")
    d = Company(place_id="1", name="A", query="q1")
    e = Company(place_id="9", name="Other", website="https://other.de", phone="0228 999999")
    out = dedupe_companies([a, b, c, d, e])
    assert [x.place_id for x in out] == ["1", "9"]
    merged = out[0]
    assert merged.query == "q1 | q2 | q3"
    assert merged.plz == "50667"  # fehlendes Feld aus Duplikat übernommen
    assert merged.domain == "foo.de"
    # Eingabe unverändert (Kopie)
    assert a.query == "q1"


def test_dedupe_keeps_order_and_companies_without_keys():
    cs = [Company(place_id=str(i), name=f"N{i}") for i in range(3)]
    assert [c.place_id for c in dedupe_companies(cs)] == ["0", "1", "2"]
