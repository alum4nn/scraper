"""Gemeinsame Fixtures: fiktive Websites und Places-Antworten aus tests/fixtures via pytest-httpx."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SITES = FIXTURES / "sites"
HOSTS = {
    "www.rheinblick-immobilien-koeln.de": "makler",
    "rheinblick-immobilien-koeln.de": "makler",
    "www.sonnenhof-immobilien-bonn.de": "makler2",
    "sonnenhof-immobilien-bonn.de": "makler2",
    "www.weber-lind-steuerberater.de": "steuer",
    "weber-lind-steuerberater.de": "steuer",
    "www.pixelwerk-digital-agentur.de": "agentur",
    "pixelwerk-digital-agentur.de": "agentur",
}


def _serve_site(request: httpx.Request) -> httpx.Response | None:
    folder = HOSTS.get(request.url.host)
    if folder is None:
        return None
    path = request.url.path
    base = SITES / folder
    candidates = [base / path.lstrip("/")]
    if path.endswith("/") or path == "":
        candidates = [base / path.lstrip("/") / "index.html"]
    else:
        candidates.append(base / (path.lstrip("/") + "/index.html"))
    for cand in candidates:
        if cand.is_file():
            suffix = cand.suffix
            ctype = {".html": "text/html; charset=utf-8", ".vcf": "text/vcard", ".txt": "text/plain"}.get(
                suffix, "application/octet-stream"
            )
            return httpx.Response(200, content=cand.read_bytes(), headers={"content-type": ctype})
    return httpx.Response(404, text="not found")


def _serve_places(request: httpx.Request) -> httpx.Response | None:
    if request.url.host != "places.googleapis.com":
        return None
    body = json.loads(request.content or b"{}")
    mask = request.headers.get("X-Goog-FieldMask", "")
    if "nationalPhoneNumber" not in mask:
        return httpx.Response(200, json=json.loads((FIXTURES / "places" / "geocode_koeln.json").read_text()))
    page = "search_text_page2.json" if body.get("pageToken") else "search_text_page1.json"
    return httpx.Response(200, json=json.loads((FIXTURES / "places" / page).read_text()))


@pytest.fixture
def fixture_web(httpx_mock):
    """HTTP-Aufrufe gegen die fiktiven Firmen-Websites und die Places-API aus Fixture-Dateien bedienen."""
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        for serve in (_serve_site, _serve_places):
            resp = serve(request)
            if resp is not None:
                return resp
        return httpx.Response(404, text="unknown host")

    httpx_mock.add_callback(handler, is_reusable=True)
    return requests


@pytest.fixture
def fast_settings(tmp_path):
    from leadscraper.settings import Settings

    return Settings(
        google_places_api_key="test-key",
        # Ausdrücklich setzen: sonst zieht pydantic-settings den Wert aus der lokalen .env, und ein dort
        # auf 0 gesetztes Monatslimit (Kostensperre) lässt Tests ohne echte Ursache fehlschlagen.
        google_monatslimit=1000,
        request_delay_seconds=0.0,
        max_pages_per_site=8,
        cache_path=tmp_path / "cache.sqlite",
        output_dir=tmp_path / "out",
    )
