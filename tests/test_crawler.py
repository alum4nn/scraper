import asyncio

import httpx
import pytest

from leadscraper.cache import Cache
from leadscraper.crawler import SiteCrawler, classify_url
from leadscraper.settings import Settings

SITE = {
    "/": """<html><body><nav><a href="/">Home</a><a href="/team/">Unser Team</a><a href="/kontakt">Kontakt</a>
    <a href="/karriere">Karriere</a><a href="/objekte?sort=neu">Objekte</a><a href="/blog/beitrag-1">Blog</a>
    <a href="/blog/beitrag-2">Blog 2</a><a href="/expose.pdf">Exposé</a><a href="https://immoscout24.de">Portal</a>
    <a href="/en/team">English</a></nav>
    <p>Rheinblick Immobilien – Ihr Makler in Köln. Unser Team aus 9 Mitarbeitern.</p>
    <footer><a href="/impressum">Impressum</a><a href="/datenschutz">Datenschutz</a></footer>
    </body></html>""",
    "/impressum": (
        "<html><body><h1>Impressum</h1><p>Rheinblick Immobilien GmbH<br>Geschäftsführer: Thomas Berger</p>"
        "</body></html>"
    ),
    "/kontakt": "<html><body><h1>Kontakt</h1><p>Tel. 0221 5550000</p></body></html>",
    "/team/": """<html><body><h1>Team</h1><a href="/team/thomas-berger/">Thomas Berger</a>
    <a href="/team/julia-kranz/">Julia Kranz</a><a href="/vcard/berger.vcf">vCard</a></body></html>""",
    "/team/thomas-berger/": "<html><body><h1>Thomas Berger</h1><p>Mobil: 0171 5550123</p></body></html>",
    "/team/julia-kranz/": "<html><body><h1>Julia Kranz</h1><p>Mobil: 0172 5550456</p></body></html>",
    "/karriere": "<html><body>Jobs</body></html>",
    "/blog/beitrag-1": "<html><body>Blog 1</body></html>",
    "/blog/beitrag-2": "<html><body>Blog 2</body></html>",
    "/datenschutz": "<html><body>Datenschutz</body></html>",
    "/en/team": "<html><body>Team EN</body></html>",
}
VCF = "BEGIN:VCARD\nFN:Thomas Berger\nTEL;TYPE=CELL:+491715550123\nEND:VCARD\n"
ROBOTS = "User-agent: *\nDisallow: /karriere\n"


@pytest.fixture
def served(httpx_mock):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        host = request.url.host
        path = request.url.path
        if host != "rheinblick.de" and host != "www.rheinblick.de":
            return httpx.Response(404)
        if request.url.scheme == "http" and path == "/":
            return httpx.Response(301, headers={"location": "https://rheinblick.de/"})
        if path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS, headers={"content-type": "text/plain"})
        if path == "/vcard/berger.vcf":
            return httpx.Response(200, text=VCF, headers={"content-type": "text/vcard"})
        if path in SITE:
            return httpx.Response(200, text=SITE[path], headers={"content-type": "text/html; charset=utf-8"})
        return httpx.Response(404)

    httpx_mock.add_callback(handler, is_reusable=True)
    return calls


def _settings(**kw) -> Settings:
    base = dict(request_delay_seconds=0.0, max_pages_per_site=5, cache_path=None)
    base.update(kw)
    return Settings(**base)


def test_classify_url():
    assert classify_url("https://x.de/impressum") == (0, "impressum")
    assert classify_url("https://x.de/legal-notice") == (0, "impressum")
    assert classify_url("https://x.de/kontakt/") == (1, "kontakt")
    assert classify_url("https://x.de/ueber-uns") == (2, "team")
    assert classify_url("https://x.de/x", "Unser Team") == (2, "team")
    assert classify_url("https://x.de/jobs") == (3, "karriere")
    assert classify_url("https://x.de/en/team") == (3, "team")
    assert classify_url("https://x.de/blog/1") == (9, "sonstige")


def test_crawl_prioritises_and_respects_budget_and_robots(served):
    crawler = SiteCrawler(_settings(max_pages_per_site=4))
    result = asyncio.run(crawler.crawl("rheinblick.de"))
    asyncio.run(crawler.close())
    kinds = [p.kind for p in result.pages]
    paths = [httpx.URL(p.final_url).path for p in result.pages]
    assert paths[0] == "/" and kinds[0] == "startseite"
    assert paths[1] == "/impressum" and kinds[1] == "impressum"
    assert paths[2] == "/kontakt"
    assert paths[3] == "/team/"
    assert len(result.pages) == 4
    assert not any("/karriere" in c for c in served if "robots" not in c)  # robots.txt verbietet
    assert not any(c.endswith(".pdf") for c in served)
    assert not any("immoscout24" in c for c in served)
    assert result.website == "https://rheinblick.de/"
    # Personen-Unterseiten stehen als nachrangige Kandidaten (prio 5) bereit
    assert any(u.endswith("/team/thomas-berger/") and p == 5 for p, u, _ in result.pending)
    assert result.vcards and "BEGIN:VCARD" in result.vcards[0].text


def test_crawl_more_loads_pages_matching_name_hints(served):
    crawler = SiteCrawler(_settings(max_pages_per_site=4))
    result = asyncio.run(crawler.crawl("https://rheinblick.de"))
    assert not any("thomas-berger" in p.final_url for p in result.pages)
    result = asyncio.run(crawler.crawl_more(result, ["Berger"]))
    asyncio.run(crawler.close())
    urls = [p.final_url for p in result.pages]
    assert any(u.endswith("/team/thomas-berger/") for u in urls)
    assert not any(u.endswith("/team/julia-kranz/") for u in urls)  # kein Hinweis auf Kranz
    assert not any("/blog/" in u for u in urls)


def test_karriere_allowed_when_robots_ignored(served):
    crawler = SiteCrawler(_settings(max_pages_per_site=6, respect_robots_txt=False))
    result = asyncio.run(crawler.crawl("https://rheinblick.de"))
    asyncio.run(crawler.close())
    assert any(p.kind == "karriere" for p in result.pages)
    assert not result.robots_blocked


def test_http_fallback_and_unreachable(httpx_mock):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.scheme == "https":
            raise httpx.ConnectError("tls failed")
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            200, text="<html><body><p>Nur http</p></body></html>", headers={"content-type": "text/html"}
        )

    httpx_mock.add_callback(handler, is_reusable=True)
    crawler = SiteCrawler(_settings())
    result = asyncio.run(crawler.crawl("https://only-http.de"))
    assert result.pages and result.pages[0].final_url.startswith("http://")
    assert "wenig Text" in " ".join(result.errors)

    httpx_mock.add_callback(lambda r: httpx.Response(500), is_reusable=True)
    dead = asyncio.run(crawler.crawl("https://dead.de"))
    asyncio.run(crawler.close())
    assert dead.pages == [] and "nicht erreichbar" in dead.errors[0]


def test_non_html_skipped_and_cache_used(httpx_mock, tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/":
            return httpx.Response(
                200,
                text='<html><body><a href="/bild">Bild</a><p>Hallo Welt und mehr Text</p></body></html>',
                headers={"content-type": "text/html"},
            )
        return httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})

    httpx_mock.add_callback(handler, is_reusable=True)
    cache = Cache(tmp_path / "c.sqlite")
    crawler = SiteCrawler(_settings(), cache=cache)
    r1 = asyncio.run(crawler.crawl("https://cached.de"))
    assert [p.kind for p in r1.pages] == ["startseite"]
    n = len(calls)
    r2 = asyncio.run(crawler.crawl("https://cached.de"))
    asyncio.run(crawler.close())
    assert len(r2.pages) == 1
    assert len(calls) == n  # zweiter Lauf komplett aus dem Cache (auch /bild-Versuch)


def test_throttle_waits_between_requests(monkeypatch, served):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("leadscraper.crawler.asyncio.sleep", fake_sleep)
    crawler = SiteCrawler(_settings(request_delay_seconds=0.5, max_pages_per_site=2))
    asyncio.run(crawler.crawl("https://rheinblick.de"))
    asyncio.run(crawler.close())
    assert sleeps and all(0 < s <= 0.5 for s in sleeps)
