"""Google Places API (New) – Text Search + Place Details.

Vertrag:
- class PlacesClient(api_key, *, cache: Cache | None = None, cache_ttl_days=30,
                     http: httpx.AsyncClient | None = None)
- async text_search(query, *, lat=None, lng=None, radius_km=25.0, included_type=None, max_results=60,
                    language="de", region="DE") -> list[Company]
    POST https://places.googleapis.com/v1/places:searchText
    Header: X-Goog-Api-Key, X-Goog-FieldMask (nur benötigte Felder – Kosten!), Content-Type: application/json.
    Body: textQuery, languageCode, regionCode, pageSize (max 20), pageToken, optional includedType,
          optional locationBias {circle:{center:{latitude,longitude},radius}} (radius in Metern, max 50000).
    Paginierung über nextPageToken bis max_results (API-Limit: 60 Ergebnisse insgesamt = 3 Seiten).
    Felder (FieldMask): places.id, places.displayName, places.formattedAddress, places.addressComponents,
          places.location, places.nationalPhoneNumber, places.internationalPhoneNumber, places.websiteUri,
          places.primaryType, places.types, places.rating, places.userRatingCount, places.businessStatus,
          places.googleMapsUri, nextPageToken
    Mapping → Company: plz/city/street/bundesland aus addressComponents (types postal_code, locality,
          route + street_number, administrative_area_level_1 → geo.normalize_bundesland, Fallback
          geo.bundesland_from_plz), domain via tldextract (registered_domain), query = Suchbegriff.
    Nur Ergebnisse mit country "DE" behalten (addressComponents type country, shortText "DE").
    Retries (tenacity): 429/5xx/Netzwerk → exponentielles Backoff, max 5 Versuche. 400/403 → PlacesError
    mit lesbarer Meldung (FieldMask/API nicht aktiviert/Key-Restriktion).
    Cache: Schlüssel = hash(query, lat, lng, radius, included_type, language, region, page_token)
          → Rohantwort.
- async geocode(query, *, language="de", region="DE") -> tuple[float, float] | None
    Ermittelt Koordinaten eines Ortes/PLZ per Text Search (FieldMask places.location, places.formattedAddress,
    pageSize 1). Ergebnis cachen.
- async close().
- class PlacesError(Exception).
- Modulkonstante FIELD_MASK (str) für Tests.
- company_from_place(place: dict, query=None) -> Company | None: Mapping eines einzelnen Place-Objekts
  (Modul-Level, testbar).
- PlacesClient ist zusätzlich ein async Context-Manager (`async with PlacesClient(...) as c:`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx
import tldextract
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from leadscraper import geo
from leadscraper.budget import RequestBudget
from leadscraper.cache import Cache
from leadscraper.models import Company

log = logging.getLogger(__name__)

PLACES_BASE = "https://places.googleapis.com/v1"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.addressComponents",
        "places.location",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.primaryType",
        "places.types",
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
        "places.googleMapsUri",
        "nextPageToken",
    ]
)
GEOCODE_FIELD_MASK = "places.location,places.formattedAddress"

CACHE_NAMESPACE = "places_search"
PAGE_SIZE = 20  # API-Maximum pro Seite
MAX_RESULTS_API = 60  # API-Maximum pro Text Search (3 Seiten)
MAX_RADIUS_M = 50_000.0
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
RETRY_ATTEMPTS = 5
# Modul-Level, damit Tests das Warten abschalten können (monkeypatch → tenacity.wait_none()).
RETRY_WAIT = wait_exponential(multiplier=1, min=1, max=20)

_HINT_400 = (
    "X-Goog-FieldMask prüfen (nur gültige Feldpfade wie 'places.id', durch Komma getrennt) "
    "und Request-Body validieren"
)
_HINT_403 = "Places API (New) im Google-Cloud-Projekt aktivieren / API-Key-Beschränkungen prüfen"
_QUOTA_HINT = (
    "Tageskontingent erschöpft. Es setzt sich um Mitternacht Pacific Time zurück; danach mit "
    "./resume.sh fortsetzen. Mehr Kontingent: Google Cloud Console → APIs & Dienste → Kontingente."
)
_QUOTA_RE = re.compile(r"quota|rate[_ ]limit|resource[_ ]exhausted", re.I)
_COUNTRY_NAMES_DE = frozenset({"deutschland", "germany"})

_extract = tldextract.TLDExtract(suffix_list_urls=())  # offline, keine Netzabfrage der Suffix-Liste


class PlacesError(Exception):
    """Lesbarer Fehler der Places API (Konfiguration, Quota, dauerhaft fehlgeschlagene Anfrage)."""


class QuotaExceededError(PlacesError):
    """Das Tages- oder Minutenkontingent ist erschöpft.

    Kein Fehler im Aufruf: weitere Versuche sind sinnlos, bis das Kontingent zurückgesetzt wird
    (Tageskontingent um Mitternacht Pacific Time). Ein bundesweiter Lauf wird deshalb geordnet beendet
    und später mit derselben Zustandsdatei fortgesetzt."""


class _RetryableStatus(Exception):
    """Interner Marker: HTTP-Status, der einen weiteren Versuch rechtfertigt (429/5xx)."""

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"HTTP {response.status_code}")
        self.response = response


@dataclass(frozen=True)
class _Address:
    plz: str | None = None
    city: str | None = None
    street: str | None = None
    bundesland: str | None = None
    country: str | None = None


# --- Hilfsfunktionen (Modul-Level) -------------------------------------------------------------------


def _component_text(component: dict[str, Any] | None, *keys: str) -> str | None:
    """Erster nicht-leerer Textwert einer Adresskomponente in Reihenfolge der angegebenen Schlüssel."""
    if not component:
        return None
    for key in keys:
        value = component.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _country_code(component: dict[str, Any] | None) -> str | None:
    """ISO-Ländercode aus der country-Komponente (shortText), Fallback über den Ländernamen."""
    short = _component_text(component, "shortText")
    if short and len(short) == 2:
        return short.upper()
    name = _component_text(component, "longText") or short
    if not name:
        return None
    return "DE" if name.lower() in _COUNTRY_NAMES_DE else name.upper()


def _parse_address(components: list[Any]) -> _Address:
    by_type: dict[str, dict[str, Any]] = {}
    for component in components:
        if not isinstance(component, dict):
            continue
        for type_name in component.get("types") or []:
            by_type.setdefault(type_name, component)

    route = _component_text(by_type.get("route"), "longText", "shortText")
    number = _component_text(by_type.get("street_number"), "longText", "shortText")
    admin_area = by_type.get("administrative_area_level_1")
    return _Address(
        plz=_component_text(by_type.get("postal_code"), "longText", "shortText"),
        city=_component_text(by_type.get("locality"), "longText", "shortText")
        or _component_text(by_type.get("postal_town"), "longText", "shortText"),
        street=f"{route} {number}" if route and number else route,
        bundesland=geo.normalize_bundesland(_component_text(admin_area, "longText"))
        or geo.normalize_bundesland(_component_text(admin_area, "shortText")),
        country=_country_code(by_type.get("country")),
    )


def _domain_from_url(url: str | None) -> str | None:
    """Registrierbare Domain (z. B. 'immobilien-mueller.de') in Kleinbuchstaben, sonst None."""
    if not url or not url.strip():
        return None
    return _extract(url.strip()).top_domain_under_public_suffix.lower() or None


def _cache_key(field_mask: str, body: dict[str, Any]) -> str:
    """SHA1 über alle Request-Parameter (inkl. pageToken und FieldMask) – stabil sortiert."""
    payload = json.dumps({"fieldMask": field_mask, **body}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _api_error_message(response: httpx.Response) -> str:
    """Fehlermeldung aus dem Google-Fehlerobjekt (error.message [error.status]), sonst Body-Auszug."""
    fallback = response.text.strip()[:300] or f"HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        return fallback
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict) or not error.get("message"):
        return fallback
    status = error.get("status")
    return f"{error['message']} [{status}]" if status else str(error["message"])


def company_from_place(place: dict[str, Any], query: str | None = None) -> Company | None:
    """Wandelt ein Place-Objekt der Text-Search-Antwort in eine Company um.

    Gibt None zurück, wenn Pflichtfelder fehlen (id, displayName.text) oder die Adresse eindeutig nicht in
    Deutschland liegt (addressComponents → country ≠ DE). Fehlen die addressComponents oder die
    country-Komponente, wird der Treffer behalten.
    """
    place_id = place.get("id")
    display_name = place.get("displayName")
    name = display_name.get("text") if isinstance(display_name, dict) else None
    if not place_id or not isinstance(name, str) or not name.strip():
        return None

    components = place.get("addressComponents")
    address = _parse_address(components) if isinstance(components, list) else _Address()
    if address.country and address.country != "DE":
        return None

    location = place.get("location") or {}
    website = place.get("websiteUri") or None
    return Company(
        place_id=str(place_id),
        name=name.strip(),
        formatted_address=place.get("formattedAddress") or None,
        street=address.street,
        plz=address.plz,
        city=address.city,
        bundesland=address.bundesland or geo.bundesland_from_plz(address.plz),
        country=address.country or "DE",
        lat=location.get("latitude"),
        lng=location.get("longitude"),
        phone=place.get("nationalPhoneNumber") or None,
        phone_international=place.get("internationalPhoneNumber") or None,
        website=website,
        domain=_domain_from_url(website),
        primary_type=place.get("primaryType") or None,
        types=list(place.get("types") or []),
        rating=place.get("rating"),
        user_rating_count=place.get("userRatingCount"),
        business_status=place.get("businessStatus") or None,
        google_maps_uri=place.get("googleMapsUri") or None,
        query=query,
    )


# --- Client ------------------------------------------------------------------------------------------


class PlacesClient:
    def __init__(
        self,
        api_key: str,
        *,
        cache: Cache | None = None,
        cache_ttl_days: int = 30,
        http: httpx.AsyncClient | None = None,
        budget: RequestBudget | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise PlacesError("Google-Places-API-Key fehlt")
        self._api_key = api_key.strip()
        self._cache = cache
        self._cache_ttl_days = cache_ttl_days
        self._budget = budget
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    async def __aenter__(self) -> PlacesClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def text_search(
        self,
        query: str,
        *,
        lat: float | None = None,
        lng: float | None = None,
        radius_km: float = 25.0,
        included_type: str | None = None,
        max_results: int = 60,
        language: str = "de",
        region: str = "DE",
    ) -> list[Company]:
        text = query.strip()
        if not text:
            raise PlacesError("Leerer Suchbegriff")
        limit = min(max_results, MAX_RESULTS_API)
        companies: list[Company] = []
        page_token: str | None = None
        page = 0
        while len(companies) < limit:
            page += 1
            body = self._search_body(
                text,
                language=language,
                region=region,
                page_size=min(PAGE_SIZE, limit - len(companies)),
                page_token=page_token,
                included_type=included_type,
                lat=lat,
                lng=lng,
                radius_km=radius_km,
            )
            log.debug("Places Text Search %r, Seite %d", text, page)
            data = await self._post_cached("places:searchText", body, FIELD_MASK)
            places = data.get("places") or []
            companies.extend(c for c in (company_from_place(p, query=query) for p in places) if c is not None)
            page_token = data.get("nextPageToken") or None
            if not page_token:
                break
        return companies[:limit]

    async def geocode(
        self, query: str, *, language: str = "de", region: str = "DE"
    ) -> tuple[float, float] | None:
        text = query.strip()
        if not text:
            return None
        body = {"textQuery": text, "languageCode": language, "regionCode": region, "pageSize": 1}
        data = await self._post_cached("places:searchText", body, GEOCODE_FIELD_MASK)
        places = data.get("places") or []
        location = places[0].get("location") if places and isinstance(places[0], dict) else None
        if not isinstance(location, dict):
            return None
        lat, lng = location.get("latitude"), location.get("longitude")
        if lat is None or lng is None:
            return None
        return float(lat), float(lng)

    async def close(self) -> None:
        if self._owns_http and not self._http.is_closed:
            await self._http.aclose()

    # --- intern ---------------------------------------------------------------------------------------

    @staticmethod
    def _search_body(
        text: str,
        *,
        language: str,
        region: str,
        page_size: int,
        page_token: str | None,
        included_type: str | None,
        lat: float | None,
        lng: float | None,
        radius_km: float,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "textQuery": text,
            "languageCode": language,
            "regionCode": region,
            "pageSize": page_size,
        }
        if page_token:
            body["pageToken"] = page_token
        if included_type:
            body["includedType"] = included_type
        if lat is not None and lng is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": min(radius_km * 1000.0, MAX_RADIUS_M),
                }
            }
        return body

    async def _post_cached(self, path: str, body: dict[str, Any], field_mask: str) -> dict[str, Any]:
        """Rohantwort aus dem Cache (Namespace places_search) oder per HTTP holen und ablegen."""
        key = _cache_key(field_mask, body)
        if self._cache is not None:
            cached = self._cache.get(CACHE_NAMESPACE, key, self._cache_ttl_days)
            if isinstance(cached, dict):
                log.debug("Places Cache-Treffer %s", key[:12])
                return cached
        data = await self._post(path, body, field_mask)
        if self._cache is not None:
            self._cache.set(CACHE_NAMESPACE, key, data)
        return data

    async def _post(self, path: str, body: dict[str, Any], field_mask: str) -> dict[str, Any]:
        # Einziger Punkt, an dem eine bezahlte Anfrage das Haus verlässt – hier greift die Ausgabenbremse.
        # Zwischenspeicher-Treffer kommen hier gar nicht an und kosten deshalb nichts.
        if self._budget is not None:
            self._budget.reservieren()
        url = f"{PLACES_BASE}/{path}"
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": field_mask,
            "Content-Type": "application/json",
        }
        retrying = AsyncRetrying(
            retry=retry_if_exception_type((httpx.TransportError, _RetryableStatus)),
            wait=RETRY_WAIT,
            stop=stop_after_attempt(RETRY_ATTEMPTS),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        )
        try:
            response = await retrying(self._send, url, body, headers)
        except _RetryableStatus as exc:
            message = _api_error_message(exc.response)
            if exc.response.status_code == 429 or _QUOTA_RE.search(message):
                raise QuotaExceededError(f"Google Places: {message} – {_QUOTA_HINT}") from exc
            raise PlacesError(
                f"Google Places antwortet nach {RETRY_ATTEMPTS} Versuchen weiterhin mit "
                f"HTTP {exc.response.status_code}: {message}"
            ) from exc
        except httpx.TransportError as exc:
            raise PlacesError(
                f"Netzwerkfehler bei Google Places nach {RETRY_ATTEMPTS} Versuchen: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        return self._parse_response(response)

    async def _send(self, url: str, body: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        response = await self._http.post(url, json=body, headers=headers)
        if response.status_code in RETRY_STATUS:
            raise _RetryableStatus(response)
        return response

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, Any]:
        status = response.status_code
        if status == 400:
            message = _api_error_message(response)
            raise PlacesError(
                f"Google Places: ungültige Anfrage (HTTP 400): {message} – Hinweis: {_HINT_400}"
            )
        if status == 403:
            message = _api_error_message(response)
            if _QUOTA_RE.search(message):
                raise QuotaExceededError(f"Google Places: {message} – {_QUOTA_HINT}")
            raise PlacesError(
                f"Google Places: Zugriff verweigert (HTTP 403): {message} – Hinweis: {_HINT_403}"
            )
        if not response.is_success:
            raise PlacesError(f"Google Places: HTTP {status}: {_api_error_message(response)}")
        try:
            data = response.json()
        except ValueError as exc:
            raise PlacesError("Google Places: Antwort ist kein gültiges JSON") from exc
        if not isinstance(data, dict):
            raise PlacesError("Google Places: unerwartetes Antwortformat (kein JSON-Objekt)")
        return data
