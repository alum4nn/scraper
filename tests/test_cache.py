import time

from leadscraper.cache import Cache


def test_roundtrip_and_ttl(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "c.sqlite")
    cache.set("html", "k", {"a": 1})
    assert cache.get("html", "k", ttl_days=1) == {"a": 1}
    assert cache.get("html", "missing", ttl_days=1) is None
    # Eintrag künstlich altern lassen
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 3 * 86_400)
    assert cache.get("html", "k", ttl_days=1) is None
    assert cache.purge_expired("html", ttl_days=1) == 1
    cache.close()


def test_noop_cache():
    cache = Cache(None)
    cache.set("x", "y", [1, 2])
    assert cache.get("x", "y", 30) is None
    assert cache.purge_expired("x", 1) == 0
    assert not cache.enabled


def test_pydantic_values(tmp_path):
    from leadscraper.models import Company

    cache = Cache(tmp_path / "c.sqlite")
    cache.set("places_details", "p1", Company(place_id="p1", name="Test GmbH"))
    assert cache.get("places_details", "p1", 30)["name"] == "Test GmbH"
