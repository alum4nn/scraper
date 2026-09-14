"""Tests für leadscraper.places (Google Places API New, Text Search) – komplett gemockt via pytest-httpx."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx
import pytest
from pytest_httpx import HTTPXMock
from tenacity import wait_none

from leadscraper import places
from leadscraper.models import Company
from leadscraper.places import (
    FIELD_MASK,
    GEOCODE_FIELD_MASK,
    PlacesClient,
    PlacesError,
    company_from_place,
)

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
API_KEY = "AIzaTestKey-1234567890"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries sollen in Tests nicht schlafen."""
    monkeypatch.setattr(places, "RETRY_WAIT", wait_none())


# --- Testdaten ----------------------------------------------------------------------------------------


def _component(long_text: str, short_text: str, *types: str) -> dict[str, Any]:
    return {"longText": long_text, "shortText": short_text, "types": list(types), "languageCode": "de"}


def _place(
    place_id: str = "ChIJ-koeln-mueller",
    name: str = "Immobilien Müller GmbH",
    *,
    street: str | None = "Hohenstaufenring",
    number: str | None = "57",
    plz: str | None = "50674",
    city: str | None = "Köln",
    city_type: str = "locality",
    bundesland: tuple[str, str] | None = ("Nordrhein-Westfalen", "NRW"),
    country: tuple[str, str] | None = ("Deutschland", "DE"),
    website: str | None = "https://www.immobilien-mueller.de/",
    with_components: bool = True,
) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    if number:
        components.append(_component(number, number, "street_number"))
    if street:
        components.append(_component(street, street, "route"))
    if city:
        components.append(_component(city, city, city_type, "political"))
    if bundesland:
        components.append(
            _component(bundesland[0], bundesland[1], "administrative_area_level_1", "political")
        )
    if country:
        components.append(_component(country[0], country[1], "country", "political"))
    if plz:
        components.append(_component(plz, plz, "postal_code"))
    place: dict[str, Any] = {
        "id": place_id,
        "displayName": {"text": name, "languageCode": "de"},
        "formattedAddress": f"{street} {number}, {plz} {city}, Deutschland",
        "location": {"latitude": 50.9333, "longitude": 6.9389},
        "nationalPhoneNumber": "0221 1234567",
        "internationalPhoneNumber": "+49 221 1234567",
        "primaryType": "real_estate_agency",
        "types": ["real_estate_agency", "point_of_interest", "establishment"],
        "rating": 4.6,
        "userRatingCount": 37,
        "businessStatus": "OPERATIONAL",
        "googleMapsUri": "https://maps.google.com/?cid=1234567890",
    }
    if website:
        place["websiteUri"] = website
    if with_components:
        place["addressComponents"] = components
    return place


def _page(count: int, *, prefix: str = "p", next_token: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "places": [
            _place(place_id=f"ChIJ-{prefix}-{i:02d}", name=f"Makler {prefix} {i}") for i in range(count)
        ]
    }
    if next_token:
        payload["nextPageToken"] = next_token
    return payload


def _bodies(httpx_mock: HTTPXMock) -> list[dict[str, Any]]:
    return [json.loads(r.content) for r in httpx_mock.get_requests()]


class FakeCache:
    """Winziger In-Memory-Ersatz für leadscraper.cache.Cache (gleiche get/set-Signatur)."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], Any] = {}
        self.gets = 0

    def get(self, namespace: str, key: str, ttl_days: int) -> Any | None:
        self.gets += 1
        return self.store.get((namespace, key))

    def set(self, namespace: str, key: str, value: Any) -> None:
        self.store[(namespace, key)] = value


# --- company_from_place -------------------------------------------------------------------------------


class TestCompanyFromPlace:
    def test_vollstaendiges_mapping(self) -> None:
        company = company_from_place(_place(), query="Immobilienmakler Köln")
        assert isinstance(company, Company)
        assert company.place_id == "ChIJ-koeln-mueller"
        assert company.name == "Immobilien Müller GmbH"
        assert company.formatted_address == "Hohenstaufenring 57, 50674 Köln, Deutschland"
        assert company.street == "Hohenstaufenring 57"
        assert company.plz == "50674"
        assert company.city == "Köln"
        assert company.bundesland == "Nordrhein-Westfalen"
        assert company.country == "DE"
        assert company.lat == pytest.approx(50.9333)
        assert company.lng == pytest.approx(6.9389)
        assert company.phone == "0221 1234567"
        assert company.phone_international == "+49 221 1234567"
        assert company.website == "https://www.immobilien-mueller.de/"
        assert company.domain == "immobilien-mueller.de"
        assert company.primary_type == "real_estate_agency"
        assert company.types == ["real_estate_agency", "point_of_interest", "establishment"]
        assert company.rating == 4.6
        assert company.user_rating_count == 37
        assert company.business_status == "OPERATIONAL"
        assert company.google_maps_uri == "https://maps.google.com/?cid=1234567890"
        assert company.query == "Immobilienmakler Köln"

    def test_bundesland_englischer_alias(self) -> None:
        company = company_from_place(_place(bundesland=("Bavaria", "BY"), plz="80331", city="München"))
        assert company is not None
        assert company.bundesland == "Bayern"

    def test_bundesland_fallback_ueber_plz(self) -> None:
        company = company_from_place(_place(bundesland=None, plz="22767", city="Hamburg"))
        assert company is not None
        assert company.bundesland == "Hamburg"

    def test_bundesland_unbekannt_ohne_plz(self) -> None:
        company = company_from_place(_place(bundesland=None, plz=None))
        assert company is not None
        assert company.bundesland is None

    def test_city_fallback_postal_town(self) -> None:
        company = company_from_place(
            _place(city="Lübeck", city_type="postal_town", plz="23552", bundesland=None)
        )
        assert company is not None
        assert company.city == "Lübeck"
        assert company.bundesland == "Schleswig-Holstein"

    def test_strasse_ohne_hausnummer(self) -> None:
        company = company_from_place(_place(street="Am Markt", number=None))
        assert company is not None
        assert company.street == "Am Markt"

    def test_ohne_strasse(self) -> None:
        company = company_from_place(_place(street=None, number=None))
        assert company is not None
        assert company.street is None

    def test_nicht_de_wird_verworfen(self) -> None:
        place = _place(
            place_id="ChIJ-salzburg",
            name="Immobilien Huber KG",
            plz="5020",
            city="Salzburg",
            bundesland=("Salzburg", "S"),
            country=("Österreich", "AT"),
        )
        assert company_from_place(place) is None

    def test_land_ohne_shorttext_ueber_namen(self) -> None:
        place = _place()
        for comp in place["addressComponents"]:
            if "country" in comp["types"]:
                comp["shortText"] = ""
        company = company_from_place(place)
        assert company is not None
        assert company.country == "DE"

    def test_ohne_address_components_wird_behalten(self) -> None:
        company = company_from_place(_place(with_components=False))
        assert company is not None
        assert company.country == "DE"
        assert company.plz is None
        assert company.city is None
        assert company.street is None

    def test_ohne_country_komponente_wird_behalten(self) -> None:
        company = company_from_place(_place(country=None))
        assert company is not None
        assert company.country == "DE"
        assert company.city == "Köln"

    def test_domain_kleingeschrieben_und_ohne_www(self) -> None:
        company = company_from_place(_place(website="HTTPS://WWW.Schreinerei-Hansen.DE/team/index.html"))
        assert company is not None
        assert company.domain == "schreinerei-hansen.de"

    def test_domain_zweistufige_endung(self) -> None:
        company = company_from_place(_place(website="https://shop.example.co.uk/"))
        assert company is not None
        assert company.domain == "example.co.uk"

    def test_ohne_website_keine_domain(self) -> None:
        company = company_from_place(_place(website=None))
        assert company is not None
        assert company.website is None
        assert company.domain is None

    def test_fehlende_pflichtfelder(self) -> None:
        place = _place()
        del place["id"]
        assert company_from_place(place) is None
        place = _place()
        place["displayName"] = {"languageCode": "de"}
        assert company_from_place(place) is None
        place = _place()
        del place["displayName"]
        assert company_from_place(place) is None

    def test_minimales_place_objekt(self) -> None:
        company = company_from_place({"id": "ChIJ-min", "displayName": {"text": "  Bäckerei Schmidt  "}})
        assert company is not None
        assert company.name == "Bäckerei Schmidt"
        assert company.types == []
        assert company.phone is None
        assert company.lat is None


# --- PlacesClient: Request-Aufbau ---------------------------------------------------------------------


@pytest.mark.anyio
async def test_header_und_body_basis(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(2))
    client = PlacesClient(API_KEY)
    result = await client.text_search("Immobilienmakler Köln")
    await client.close()

    assert [c.place_id for c in result] == ["ChIJ-p-00", "ChIJ-p-01"]
    assert all(c.query == "Immobilienmakler Köln" for c in result)
    request = httpx_mock.get_requests()[0]
    assert request.headers["X-Goog-Api-Key"] == API_KEY
    assert request.headers["X-Goog-FieldMask"] == FIELD_MASK
    assert request.headers["Content-Type"] == "application/json"
    body = json.loads(request.content)
    assert body == {
        "textQuery": "Immobilienmakler Köln",
        "languageCode": "de",
        "regionCode": "DE",
        "pageSize": 20,
    }
    assert "locationBias" not in body
    assert "includedType" not in body
    assert "pageToken" not in body


def test_field_mask_enthaelt_alle_benoetigten_felder() -> None:
    fields = FIELD_MASK.split(",")
    assert "places.id" in fields
    assert "places.addressComponents" in fields
    assert "places.websiteUri" in fields
    assert "places.nationalPhoneNumber" in fields
    assert "nextPageToken" in fields
    assert " " not in FIELD_MASK


@pytest.mark.anyio
async def test_included_type_und_location_bias(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1))
    async with PlacesClient(API_KEY) as client:
        await client.text_search(
            "Makler",
            lat=50.9375,
            lng=6.9603,
            radius_km=25.0,
            included_type="real_estate_agency",
            language="de",
            region="DE",
        )
    body = _bodies(httpx_mock)[0]
    assert body["includedType"] == "real_estate_agency"
    assert body["locationBias"] == {
        "circle": {"center": {"latitude": 50.9375, "longitude": 6.9603}, "radius": 25000}
    }


@pytest.mark.anyio
async def test_radius_wird_auf_50km_begrenzt(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1))
    async with PlacesClient(API_KEY) as client:
        await client.text_search("Makler", lat=52.52, lng=13.405, radius_km=120)
    assert _bodies(httpx_mock)[0]["locationBias"]["circle"]["radius"] == 50000


@pytest.mark.anyio
async def test_location_bias_nur_mit_beiden_koordinaten(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1))
    async with PlacesClient(API_KEY) as client:
        await client.text_search("Makler", lat=52.52, lng=None)
    assert "locationBias" not in _bodies(httpx_mock)[0]


@pytest.mark.anyio
async def test_sprache_und_region_durchgereicht(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1))
    async with PlacesClient(API_KEY) as client:
        await client.text_search("Steuerberater Wien", language="de", region="AT")
    body = _bodies(httpx_mock)[0]
    assert body["languageCode"] == "de"
    assert body["regionCode"] == "AT"


@pytest.mark.anyio
async def test_leerer_suchbegriff(httpx_mock: HTTPXMock) -> None:
    async with PlacesClient(API_KEY) as client:
        with pytest.raises(PlacesError, match="Suchbegriff"):
            await client.text_search("   ")
    assert httpx_mock.get_requests() == []


def test_api_key_fehlt() -> None:
    with pytest.raises(PlacesError, match="API-Key"):
        PlacesClient("")


# --- Paginierung / max_results ------------------------------------------------------------------------


@pytest.mark.anyio
async def test_zwei_seiten_paginierung(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(20, prefix="a", next_token="TOKEN-2"))
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(3, prefix="b"))
    async with PlacesClient(API_KEY) as client:
        result = await client.text_search("Schreinerei Hamburg", max_results=60)

    assert len(result) == 23
    assert result[0].place_id == "ChIJ-a-00"
    assert result[-1].place_id == "ChIJ-b-02"
    bodies = _bodies(httpx_mock)
    assert len(bodies) == 2
    assert "pageToken" not in bodies[0]
    assert bodies[1]["pageToken"] == "TOKEN-2"
    assert bodies[1]["textQuery"] == "Schreinerei Hamburg"
    assert bodies[1]["pageSize"] == 20


@pytest.mark.anyio
async def test_max_results_begrenzt_seiten_und_page_size(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(20, prefix="a", next_token="TOKEN-2"))
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(5, prefix="b", next_token="TOKEN-3"))
    async with PlacesClient(API_KEY) as client:
        result = await client.text_search("Steuerberater München", max_results=25)

    assert len(result) == 25
    bodies = _bodies(httpx_mock)
    assert len(bodies) == 2  # TOKEN-3 wird nicht mehr abgerufen
    assert bodies[0]["pageSize"] == 20
    assert bodies[1]["pageSize"] == 5


@pytest.mark.anyio
async def test_max_results_kleiner_als_seite(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(7, prefix="a", next_token="TOKEN-2"))
    async with PlacesClient(API_KEY) as client:
        result = await client.text_search("Zahnarzt Bonn", max_results=7)
    assert len(result) == 7
    assert _bodies(httpx_mock)[0]["pageSize"] == 7


@pytest.mark.anyio
async def test_mehr_treffer_als_max_results_werden_abgeschnitten(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(20, prefix="a"))
    async with PlacesClient(API_KEY) as client:
        result = await client.text_search("Zahnarzt Bonn", max_results=3)
    assert len(result) == 3


@pytest.mark.anyio
async def test_max_results_ueber_api_limit(httpx_mock: HTTPXMock) -> None:
    for prefix, token in (("a", "T2"), ("b", "T3"), ("c", None)):
        httpx_mock.add_response(
            url=SEARCH_URL, method="POST", json=_page(20, prefix=prefix, next_token=token)
        )
    async with PlacesClient(API_KEY) as client:
        result = await client.text_search("Handwerker Berlin", max_results=200)
    assert len(result) == 60
    assert len(httpx_mock.get_requests()) == 3


@pytest.mark.anyio
async def test_max_results_null(httpx_mock: HTTPXMock) -> None:
    async with PlacesClient(API_KEY) as client:
        assert await client.text_search("Makler", max_results=0) == []
    assert httpx_mock.get_requests() == []


@pytest.mark.anyio
async def test_leere_antwort(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json={})
    async with PlacesClient(API_KEY) as client:
        assert await client.text_search("Gibt es nicht") == []


@pytest.mark.anyio
async def test_nicht_de_treffer_werden_gefiltert(httpx_mock: HTTPXMock) -> None:
    payload = {
        "places": [
            _place(place_id="ChIJ-de", name="Immobilien Müller GmbH"),
            _place(
                place_id="ChIJ-at",
                name="Immobilien Huber KG",
                plz="5020",
                city="Salzburg",
                bundesland=("Salzburg", "S"),
                country=("Österreich", "AT"),
            ),
            _place(
                place_id="ChIJ-ch",
                name="Immo Meier AG",
                plz="8001",
                city="Zürich",
                bundesland=("Zürich", "ZH"),
                country=("Schweiz", "CH"),
            ),
            _place(place_id="ChIJ-unbekannt", name="Ohne Adresse", with_components=False),
        ]
    }
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=payload)
    async with PlacesClient(API_KEY) as client:
        result = await client.text_search("Immobilienmakler")
    assert [c.place_id for c in result] == ["ChIJ-de", "ChIJ-unbekannt"]


@pytest.mark.anyio
async def test_mapping_im_suchergebnis_mit_plz_fallback(httpx_mock: HTTPXMock) -> None:
    payload = {
        "places": [
            _place(place_id="ChIJ-1", bundesland=("Nordrhein-Westfalen", "NRW")),
            _place(
                place_id="ChIJ-2",
                name="Schreinerei Hansen & Söhne",
                bundesland=None,
                plz="22767",
                city="Hamburg",
            ),
            _place(
                place_id="ChIJ-3",
                name="Steuerberatung Dr. Weber",
                bundesland=("Bavaria", "BY"),
                plz="80331",
                city="München",
                street="Marienplatz",
                number="8",
            ),
        ]
    }
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=payload)
    async with PlacesClient(API_KEY) as client:
        c1, c2, c3 = await client.text_search("Firmen")
    assert (c1.plz, c1.city, c1.street, c1.bundesland) == (
        "50674",
        "Köln",
        "Hohenstaufenring 57",
        "Nordrhein-Westfalen",
    )
    assert (c2.plz, c2.city, c2.bundesland) == ("22767", "Hamburg", "Hamburg")
    assert (c3.plz, c3.city, c3.street, c3.bundesland) == ("80331", "München", "Marienplatz 8", "Bayern")


# --- Fehler & Retries ---------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_400_liefert_api_meldung_und_fieldmask_hinweis(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=SEARCH_URL,
        method="POST",
        status_code=400,
        json={
            "error": {
                "code": 400,
                "message": "Invalid field mask: 'places.foo' is not a valid field.",
                "status": "INVALID_ARGUMENT",
            }
        },
    )
    async with PlacesClient(API_KEY) as client:
        with pytest.raises(PlacesError) as excinfo:
            await client.text_search("Makler")
    message = str(excinfo.value)
    assert "Invalid field mask: 'places.foo' is not a valid field." in message
    assert "FieldMask" in message
    assert "400" in message
    assert len(httpx_mock.get_requests()) == 1  # kein Retry bei 400


@pytest.mark.anyio
async def test_403_liefert_aktivierungs_hinweis(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=SEARCH_URL,
        method="POST",
        status_code=403,
        json={
            "error": {
                "code": 403,
                "message": "Places API (New) has not been used in project 123 before or it is disabled.",
                "status": "PERMISSION_DENIED",
            }
        },
    )
    async with PlacesClient(API_KEY) as client:
        with pytest.raises(PlacesError) as excinfo:
            await client.text_search("Makler")
    message = str(excinfo.value)
    assert "Places API (New) im Google-Cloud-Projekt aktivieren / API-Key-Beschränkungen prüfen" in message
    assert "has not been used in project 123" in message
    assert len(httpx_mock.get_requests()) == 1


@pytest.mark.anyio
async def test_fehler_ohne_json_body(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", status_code=404, text="Not Found")
    async with PlacesClient(API_KEY) as client:
        with pytest.raises(PlacesError, match="404.*Not Found"):
            await client.text_search("Makler")


@pytest.mark.anyio
async def test_ungueltiges_json_bei_200(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", text="<html>Wartungsarbeiten</html>")
    async with PlacesClient(API_KEY) as client:
        with pytest.raises(PlacesError, match="JSON"):
            await client.text_search("Makler")


@pytest.mark.anyio
async def test_429_dann_200_wird_wiederholt(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=SEARCH_URL,
        method="POST",
        status_code=429,
        json={"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}},
    )
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(2))
    async with PlacesClient(API_KEY) as client:
        result = await client.text_search("Makler")
    assert len(result) == 2
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("status", [500, 502, 503, 504])
async def test_5xx_dann_200_wird_wiederholt(httpx_mock: HTTPXMock, status: int) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", status_code=status, text="upstream error")
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1))
    async with PlacesClient(API_KEY) as client:
        result = await client.text_search("Makler")
    assert len(result) == 1
    assert len(httpx_mock.get_requests()) == 2


@pytest.mark.anyio
async def test_netzwerkfehler_wird_wiederholt(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("Verbindung abgelehnt"), url=SEARCH_URL, method="POST")
    httpx_mock.add_exception(httpx.ReadTimeout("Zeitüberschreitung"), url=SEARCH_URL, method="POST")
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1))
    async with PlacesClient(API_KEY) as client:
        result = await client.text_search("Makler")
    assert len(result) == 1
    assert len(httpx_mock.get_requests()) == 3


@pytest.mark.anyio
async def test_dauerhaft_503_nach_fuenf_versuchen_fehler(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=SEARCH_URL,
        method="POST",
        status_code=503,
        json={"error": {"code": 503, "message": "Service Unavailable", "status": "UNAVAILABLE"}},
        is_reusable=True,
    )
    async with PlacesClient(API_KEY) as client:
        with pytest.raises(PlacesError, match="503.*Service Unavailable"):
            await client.text_search("Makler")
    assert len(httpx_mock.get_requests()) == places.RETRY_ATTEMPTS == 5


@pytest.mark.anyio
async def test_dauerhafter_netzwerkfehler(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(
        httpx.ConnectError("DNS-Fehler"), url=SEARCH_URL, method="POST", is_reusable=True
    )
    async with PlacesClient(API_KEY) as client:
        with pytest.raises(PlacesError, match="Netzwerkfehler.*DNS-Fehler"):
            await client.text_search("Makler")
    assert len(httpx_mock.get_requests()) == 5


# --- Cache --------------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cache_treffer_vermeidet_zweiten_http_aufruf(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(2))
    cache = FakeCache()
    async with PlacesClient(API_KEY, cache=cache, cache_ttl_days=7) as client:
        first = await client.text_search("Immobilienmakler Köln", lat=50.9, lng=6.9)
        second = await client.text_search("Immobilienmakler Köln", lat=50.9, lng=6.9)

    assert len(httpx_mock.get_requests()) == 1
    assert [c.place_id for c in first] == [c.place_id for c in second]
    assert cache.gets == 2
    assert len(cache.store) == 1
    (namespace, key), value = next(iter(cache.store.items()))
    assert namespace == "places_search"
    assert len(key) == 40 and all(ch in "0123456789abcdef" for ch in key)
    assert value == _page(2)  # Rohantwort, unverändert


@pytest.mark.anyio
async def test_cache_schluessel_enthaelt_parameter(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1, prefix="a"))
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1, prefix="b"))
    cache = FakeCache()
    async with PlacesClient(API_KEY, cache=cache) as client:
        a = await client.text_search("Makler", lat=50.9, lng=6.9, radius_km=10)
        b = await client.text_search("Makler", lat=50.9, lng=6.9, radius_km=20)
    assert len(httpx_mock.get_requests()) == 2
    assert len(cache.store) == 2
    assert a[0].place_id == "ChIJ-a-00"
    assert b[0].place_id == "ChIJ-b-00"


@pytest.mark.anyio
async def test_cache_schluessel_pro_seite(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(20, prefix="a", next_token="T2"))
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(4, prefix="b"))
    cache = FakeCache()
    async with PlacesClient(API_KEY, cache=cache) as client:
        first = await client.text_search("Makler")
        second = await client.text_search("Makler")
    assert len(first) == len(second) == 24
    assert len(httpx_mock.get_requests()) == 2
    assert len(cache.store) == 2
    expected_key = hashlib.sha1(
        json.dumps(
            {
                "fieldMask": FIELD_MASK,
                "textQuery": "Makler",
                "languageCode": "de",
                "regionCode": "DE",
                "pageSize": 20,
                "pageToken": "T2",
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert ("places_search", expected_key) in cache.store


@pytest.mark.anyio
async def test_abgelaufener_cache_wird_ignoriert(httpx_mock: HTTPXMock) -> None:
    class ExpiredCache(FakeCache):
        def get(self, namespace: str, key: str, ttl_days: int) -> Any | None:
            self.gets += 1
            return None  # Cache.get liefert bei abgelaufenem TTL None

    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1), is_reusable=True)
    cache = ExpiredCache()
    async with PlacesClient(API_KEY, cache=cache) as client:
        await client.text_search("Makler")
        await client.text_search("Makler")
    assert len(httpx_mock.get_requests()) == 2


# --- geocode ------------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_geocode(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=SEARCH_URL,
        method="POST",
        json={
            "places": [
                {
                    "formattedAddress": "Köln, Deutschland",
                    "location": {"latitude": 50.937531, "longitude": 6.960279},
                }
            ]
        },
    )
    async with PlacesClient(API_KEY) as client:
        coords = await client.geocode("Köln")
    assert coords == pytest.approx((50.937531, 6.960279))
    request = httpx_mock.get_requests()[0]
    assert request.headers["X-Goog-FieldMask"] == GEOCODE_FIELD_MASK
    assert request.headers["X-Goog-Api-Key"] == API_KEY
    assert json.loads(request.content) == {
        "textQuery": "Köln",
        "languageCode": "de",
        "regionCode": "DE",
        "pageSize": 1,
    }


@pytest.mark.anyio
async def test_geocode_plz(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=SEARCH_URL,
        method="POST",
        json={
            "places": [{"formattedAddress": "50674 Köln", "location": {"latitude": 50.93, "longitude": 6.93}}]
        },
    )
    async with PlacesClient(API_KEY) as client:
        assert await client.geocode("50674") == (50.93, 6.93)


@pytest.mark.anyio
async def test_geocode_ohne_treffer(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json={})
    async with PlacesClient(API_KEY) as client:
        assert await client.geocode("Nirgendwo-Hausen") is None


@pytest.mark.anyio
async def test_geocode_ohne_location(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=SEARCH_URL, method="POST", json={"places": [{"formattedAddress": "Irgendwo"}]}
    )
    async with PlacesClient(API_KEY) as client:
        assert await client.geocode("Irgendwo") is None


@pytest.mark.anyio
async def test_geocode_leer(httpx_mock: HTTPXMock) -> None:
    async with PlacesClient(API_KEY) as client:
        assert await client.geocode("  ") is None
    assert httpx_mock.get_requests() == []


@pytest.mark.anyio
async def test_geocode_wird_gecacht(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=SEARCH_URL,
        method="POST",
        json={"places": [{"location": {"latitude": 53.55, "longitude": 9.99}}]},
    )
    cache = FakeCache()
    async with PlacesClient(API_KEY, cache=cache) as client:
        assert await client.geocode("Hamburg") == (53.55, 9.99)
        assert await client.geocode("Hamburg") == (53.55, 9.99)
    assert len(httpx_mock.get_requests()) == 1
    assert len(cache.store) == 1


@pytest.mark.anyio
async def test_geocode_und_text_search_teilen_keinen_cache_eintrag(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=SEARCH_URL, method="POST", json={"places": [{"location": {"latitude": 53.55, "longitude": 9.99}}]}
    )
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1))
    cache = FakeCache()
    async with PlacesClient(API_KEY, cache=cache) as client:
        await client.geocode("Hamburg")
        result = await client.text_search("Hamburg")
    assert len(result) == 1
    assert len(httpx_mock.get_requests()) == 2
    assert len(cache.store) == 2


# --- Lebenszyklus -------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_context_manager_schliesst_eigenen_client(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1))
    async with PlacesClient(API_KEY) as client:
        assert isinstance(client, PlacesClient)
        await client.text_search("Makler")
        assert not client._http.is_closed
    assert client._http.is_closed
    await client.close()  # idempotent


@pytest.mark.anyio
async def test_injizierter_http_client_bleibt_offen(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=SEARCH_URL, method="POST", json=_page(1))
    async with httpx.AsyncClient() as http:
        client = PlacesClient(API_KEY, http=http)
        await client.text_search("Makler")
        await client.close()
        assert not http.is_closed
