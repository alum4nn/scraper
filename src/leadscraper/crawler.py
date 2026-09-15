"""Website-Crawler: holt gezielt die Seiten, auf denen Entscheider und Handynummern stehen.

Ablauf: Startseite → Kandidaten-Links klassifizieren (Impressum > Kontakt > Team > Karriere > Sonstiges)
→ nach Priorität laden bis zum Seitenbudget → zweite Ebene (Personen-Unterseiten, Seiten mit bekannten
Nachnamen) → vCards. robots.txt wird beachtet, pro Domain gilt eine Wartezeit zwischen Requests.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Literal
from urllib import robotparser
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

import httpx

from leadscraper.cache import Cache
from leadscraper.dedupe import normalize_domain
from leadscraper.extract.htmlutil import (
    Link,
    extract_lines,
    extract_links,
    extract_text,
    image_alt_texts,
)
from leadscraper.extract.names import is_probable_person_name
from leadscraper.settings import Settings

log = logging.getLogger(__name__)

PageKind = Literal["startseite", "impressum", "kontakt", "team", "karriere", "sonstige"]

_KIND_PATTERNS: list[tuple[int, PageKind, re.Pattern[str]]] = [
    (
        0,
        "impressum",
        re.compile(
            r"impressum|imprint|legal[-_ ]?notice|anbieterkennzeichnung|rechtliche[-_ ]hinweise", re.I
        ),
    ),
    (1, "kontakt", re.compile(r"kontakt|contact|ansprechpartner|standort|anfahrt|erreichen", re.I)),
    (
        2,
        "team",
        re.compile(
            r"team|ueber[-_]?uns|uber[-_]?uns|über[-_ ]?uns|about|unternehmen|wir[-_ ]?(?:ueber|über|sind)|"
            r"mitarbeiter|geschaeftsfuehrung|geschäftsführung|management|leitung|partner|makler|berater|"
            r"anwaelte|anwälte|aerzte|ärzte|praxisteam|inhaber|gesch(?:ae|ä)ftsleitung|"
            r"unsere[-_ ]?(?:makler|berater|experten|mitarbeiter|leute)|koepfe|köpfe|menschen|profil|firma|"
            r"philosophie|historie|geschichte",
            re.I,
        ),
    ),
    (3, "karriere", re.compile(r"karriere|jobs|stellen|ausbildung|career|bewerb", re.I)),
    # Objekt-/Angebotsseiten: bei Maklern steht dort die "Ihr Ansprechpartner"-Box mit Handynummer
    (
        4,
        "sonstige",
        re.compile(r"immobilien|objekt|angebot|expos[eé]|referenz|leistung|verkauf|vermiet", re.I),
    ),
]
_SKIP_EXT_RE = re.compile(
    r"\.(?:pdf|jpe?g|png|gif|svg|webp|avif|bmp|ico|zip|rar|7z|docx?|xlsx?|pptx?|mp[34]|m4a|mov|avi|wmv|css|js|json|xml|rss|"
    r"atom|txt|csv|woff2?|ttf|eot)(?:$|\?)",
    re.I,
)
_SKIP_PATH_RE = re.compile(
    r"/(?:login|logout|anmelden|warenkorb|cart|checkout|wp-admin|wp-login|wp-json|feed|tag|tags|category|kategorie|"
    r"page/\d+|seite/\d+|search|suche|print|drucken|share|cdn-cgi|xmlrpc|\?s=)|/wp-content/",
    re.I,
)
_LANG_PREFIX_RE = re.compile(r"^/(?:en|fr|nl|es|it|pl|tr|ru|cs|da|sv|pt)(?:/|$)", re.I)
# Seiten ohne Ansprechpartner-Nutzen, die sonst das Budget fressen (Bewertungen, Blog, Lexikon, News)
_LOW_VALUE_RE = re.compile(
    r"bewertung|kundenstimmen|testimonial|rezension|lexikon|glossar|ratgeber|blog|news|aktuelles|presse|"
    r"faq|magazin|tagebuch|checkliste|datenschutz|agb|cookie|sitemap|newsletter|download|"
    r"partner|netzwerk|kooperation|empfehlung|handwerker|dienstleister",
    re.I,
)
_MAX_SONSTIGE_PAGES = 3
# Eine Team-Seite erkennt man am Pfadabschnitt, nicht an einem Wort irgendwo im Slug:
# „/team/“ und „/ueber-uns/“ ja, „/immobilienmakler-essen-borbeck/“ nein. Solche SEO-Ortsseiten tragen
# Kundenstimmen, die sonst als Belegschaft gezählt werden.
_TEAM_SEGMENT_RE = re.compile(
    r"^(?:(?:unser|das|unsere|mein)[-_])?(?:team|teams)$|"
    r"^(?:ueber|uber|über)[-_ ]?uns(?:[-_]\w+)?$|^about(?:[-_]us)?$|^wir(?:[-_](?:ueber|über)[-_]uns)?$|"
    r"^(?:unsere[-_])?(?:mitarbeiter|mitarbeitende|makler|berater|experten|koepfe|köpfe|menschen)(?:innen)?$|"
    r"^(?:geschaeftsfuehrung|geschäftsführung|geschaeftsleitung|geschäftsleitung|management|leitung|"
    r"inhaber|partner|ansprechpartner|praxisteam|anwaelte|anwälte|aerzte|ärzte)$|"
    r"^(?:unternehmen|firma|philosophie|historie|geschichte|profil|karriere|jobs|stellen|ausbildung)$",
    re.I,
)
_PERSON_PATH_RE = re.compile(
    r"/(?:team|mitarbeiter|makler|berater|ansprechpartner|ueber-uns|about)/[a-z]+-[a-z-]+/?$", re.I
)
_HTML_TYPES = ("text/html", "application/xhtml+xml")
_VCARD_TYPES = ("text/vcard", "text/x-vcard", "text/directory", "application/octet-stream", "text/plain")
_MAX_VCARDS = 10
_EXTRA_PAGES_FOR_HINTS = 4
# Frames statt Navigation (ältere Seiten): Inhalte hängen in <frame>/<iframe src=…>
_FRAME_SRC_RE = re.compile(r"<i?frame[^>]+src=[\"\']([^\"\'>]+)", re.I)
# Übliche Impressum-Adressen, falls kein Link darauf zeigt (JavaScript-Menü, fremde Domain im Menü)
_IMPRESSUM_GUESSES = ("/impressum", "/impressum.html", "/impressum.php", "/impressum/index.html")
_IMPRESSUM_CONTENT_RE = re.compile(
    r"impressum|anbieterkennzeichnung|angaben\s+gemäß|vertreten\s+durch|geschäftsführ|inhaber|"
    r"umsatzsteuer|ust[\s.-]*id|handelsregister|\bHR[AB]\b|verantwortlich",
    re.I,
)


@dataclass
class Page:
    url: str
    final_url: str
    kind: PageKind
    html: str
    text: str
    lines: list[str]
    links: list[Link]
    status: int = 200
    image_alts: list[str] = field(default_factory=list)


@dataclass
class VCard:
    url: str
    text: str


@dataclass
class CrawlResult:
    website: str
    pages: list[Page] = field(default_factory=list)
    vcards: list[VCard] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    robots_blocked: bool = False
    pending: list[tuple[int, str, str]] = field(
        default_factory=list
    )  # (prio, url, anchor_text) – noch nicht geladen
    loaded: set[str] = field(default_factory=set)
    vcard_urls: list[str] = field(default_factory=list)


def _split(url: str) -> SplitResult:
    """urlsplit, das an kaputten Links auf fremden Seiten nicht die ganze Firma scheitern lässt."""
    try:
        return urlsplit(url)
    except ValueError:
        return SplitResult("", "", "", "", "")


def _norm_key(url: str) -> str:
    parts = _split(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    return f"{host}{path}{'?' + parts.query if parts.query else ''}"


def _is_team_page(segmente: list[str], anchor_text: str) -> bool:
    """Team-Seite? Entweder ein passender Pfadabschnitt oder ein eindeutiger Linktext („Unser Team“)."""
    if any(_TEAM_SEGMENT_RE.match(seg.rsplit(".", 1)[0]) for seg in segmente):
        return True
    text = re.sub(r"\s+", "-", (anchor_text or "").strip().lower())
    return bool(text and _TEAM_SEGMENT_RE.match(text))


def classify_url(url: str, anchor_text: str = "") -> tuple[int, PageKind]:
    parts = _split(url)
    path = parts.path or "/"
    haystack = f"{path} {anchor_text}"
    penalty = 1 if _LANG_PREFIX_RE.match(path) else 0
    segmente = [seg for seg in path.split("/") if seg]
    for prio, kind, pat in _KIND_PATTERNS:
        if pat.search(haystack):
            if kind in ("team", "karriere", "sonstige") and _LOW_VALUE_RE.search(path):
                return 9, "sonstige"  # /ueber-uns/kundenbewertungen/, /news/, /immobilienlexikon/
            if kind == "team" and not _is_team_page(segmente, anchor_text):
                # „/immobilienmakler-essen-borbeck/“ ist eine Ortsseite, keine Team-Seite
                return 4, "sonstige"
            return prio + penalty, kind
    return 9, "sonstige"


def _normalize_start(website: str) -> str:
    site = website.strip()
    if not site:
        return site
    if "://" not in site:
        site = "https://" + site
    parts = _split(site)
    if not parts.netloc:
        return ""
    return urlunsplit(
        (parts.scheme.lower(), (parts.netloc or "").lower(), parts.path or "/", parts.query, "")
    )


# Serverseitige Aussetzer, die beim nächsten Versuch oft weg sind. Alles andere (404, 403, 410) ist
# eine dauerhafte Absage und wird gemerkt.
_VORUEBERGEHEND = frozenset({408, 425, 429, 500, 502, 503, 504})
_WARTEN_VOR_WIEDERHOLUNG = (1.0, 3.0)
_MAX_VERSUCHE = len(_WARTEN_VOR_WIEDERHOLUNG) + 1


class SiteCrawler:
    def __init__(
        self, settings: Settings, *, cache: Cache | None = None, http: httpx.AsyncClient | None = None
    ) -> None:
        self.settings = settings
        self.cache = cache
        self._own_client = http is None
        self.http = http or httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            headers={"User-Agent": settings.user_agent, "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"},
            max_redirects=8,
        )
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self.last_error: str | None = None  # letzter Netzwerk-/HTTP-Fehler (für Diagnose)

    async def close(self) -> None:
        if self._own_client:
            await self.http.aclose()

    # --- HTTP -------------------------------------------------------------------------------------

    async def _throttle(self, url: str) -> None:
        host = _split(url).hostname or ""
        delay = self.settings.request_delay_seconds
        if delay <= 0:
            return
        last = self._last_request.get(host)
        now = time.monotonic()
        if last is not None and now - last < delay:
            await asyncio.sleep(delay - (now - last))
        self._last_request[host] = time.monotonic()

    async def _robots_for(self, url: str) -> robotparser.RobotFileParser | None:
        parts = _split(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base in self._robots:
            return self._robots[base]
        rp: robotparser.RobotFileParser | None = None
        try:
            await self._throttle(url)
            resp = await self.http.get(base + "/robots.txt")
            if resp.status_code == 200 and "html" not in resp.headers.get("content-type", ""):
                rp = robotparser.RobotFileParser()
                rp.parse(resp.text.splitlines())
        except (httpx.HTTPError, ValueError) as exc:
            log.debug("robots.txt nicht lesbar für %s: %s", base, exc)
        self._robots[base] = rp
        return rp

    async def _allowed(self, url: str) -> bool:
        if not self.settings.respect_robots_txt:
            return True
        rp = await self._robots_for(url)
        if rp is None:
            return True
        try:
            return rp.can_fetch(self.settings.user_agent, url) and rp.can_fetch("*", url)
        except Exception:  # noqa: BLE001 – kaputte robots.txt = erlaubt
            return True

    async def _fetch(self, url: str, *, accept: tuple[str, ...]) -> tuple[str, int, str] | None:
        """(final_url, status, text) oder None. Nutzt den HTML-Cache, wenn vorhanden."""
        key = _norm_key(url)
        if self.cache is not None:
            hit = self.cache.get("html", key, self.settings.html_cache_ttl_days)
            if hit is not None:
                return None if hit.get("skip") else (hit["final_url"], hit["status"], hit["text"])
        resp = None
        for versuch in range(_MAX_VERSUCHE):
            await self._throttle(url)
            try:
                resp = await self.http.get(url)
            except httpx.HTTPError as exc:
                self.last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
                log.debug("Fehler beim Laden von %s: %s", url, exc)
                resp = None
            if resp is not None and resp.status_code not in _VORUEBERGEHEND:
                break
            if versuch < _MAX_VERSUCHE - 1:
                if resp is not None:
                    self.last_error = f"HTTP {resp.status_code}"
                await asyncio.sleep(_WARTEN_VOR_WIEDERHOLUNG[versuch])
        if resp is None:
            # Netzwerkfehler werden NICHT als „übersprungen“ gemerkt: Sonst bleibt der Betrieb
            # vierzehn Tage lang unsichtbar, auch beim erneuten Auswerten aus dem Zwischenspeicher.
            return None
        ctype = resp.headers.get("content-type", "").lower()
        if resp.status_code >= 400 or not any(t in ctype for t in accept):
            self.last_error = f"HTTP {resp.status_code} ({ctype.split(';')[0] or 'ohne Content-Type'})"
            # Eine Stichprobe über 66 Handwerkerwebsites fand 19 Ausfälle, fast alle mit demselben
            # Serverfehler desselben Massenhosters. Ein vorübergehender Fehler darf den Betrieb nicht
            # für die Dauer des Zwischenspeichers aussortieren.
            if self.cache is not None and resp.status_code not in _VORUEBERGEHEND:
                self.cache.set("html", key, {"skip": True})
            return None
        raw = resp.content[: self.settings.max_html_bytes]
        try:
            text = raw.decode(resp.encoding or "utf-8", errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        result = (str(resp.url), resp.status_code, text)
        if self.cache is not None:
            self.cache.set("html", key, {"final_url": result[0], "status": result[1], "text": text})
        return result

    async def _load_page(self, url: str, kind: PageKind, result: CrawlResult) -> Page | None:
        key = _norm_key(url)
        if key in result.loaded:
            return None
        result.loaded.add(key)
        if not await self._allowed(url):
            result.robots_blocked = True
            result.errors.append(f"robots.txt verbietet {url}")
            return None
        fetched = await self._fetch(url, accept=_HTML_TYPES)
        if fetched is None:
            return None
        final_url, status, html = fetched
        final_key = _norm_key(final_url)
        if final_key != key and final_key in result.loaded:
            return None  # Redirect auf eine schon geladene Seite (Groß-/Kleinschreibung, Parameter)
        result.loaded.add(final_key)
        if kind == "sonstige":
            kind = classify_url(final_url)[1]
        page = Page(
            url=url,
            final_url=final_url,
            kind=kind,
            html=html,
            text=extract_text(html),
            lines=extract_lines(html),
            links=extract_links(html, final_url),
            status=status,
            image_alts=image_alt_texts(html),
        )
        result.pages.append(page)
        self._collect_candidates(page, result)
        return page

    # --- Kandidaten ---------------------------------------------------------------------------

    def _collect_candidates(self, page: Page, result: CrawlResult) -> None:
        base_domain = normalize_domain(result.website)
        known = {u for _, u, _ in result.pending} | result.loaded
        for link in page.links:
            if link.kind == "vcard":
                if link.href not in result.vcard_urls and len(result.vcard_urls) < _MAX_VCARDS * 2:
                    result.vcard_urls.append(link.href)
                continue
            if link.kind != "internal":
                continue
            href = link.href
            if normalize_domain(href) != base_domain:
                continue
            parts = _split(href)
            if _SKIP_EXT_RE.search(href) or _SKIP_PATH_RE.search(f"{parts.path}?{parts.query}"):
                continue
            key = _norm_key(href)
            if key in known:
                continue
            prio, _kind = classify_url(href, link.text)
            if parts.query and prio > 3:
                continue
            # Personen-Unterseiten (/team/max-mustermann/) nachrangig, damit sie nicht das Budget fressen –
            # crawl_more() holt gezielt die, deren Name aus dem Impressum bekannt ist (Prio 4).
            if _PERSON_PATH_RE.search(parts.path) or is_probable_person_name(link.text):
                prio = 5
            if prio == 9 and re.search(r"whatsapp|mobil|handy", link.text, re.I):
                prio = 5
            known.add(key)
            result.pending.append((prio, href, link.text))
        result.pending.sort(key=lambda t: t[0])

    @staticmethod
    def _matches_hint(entry: tuple[int, str, str], hints: list[str]) -> bool:
        _, url, text = entry
        hay = f"{url} {text}".lower()
        return any(h.lower() in hay for h in hints if len(h) >= 3)

    # --- Öffentliche API ------------------------------------------------------------------------

    async def crawl(self, website: str, *, name_hints: list[str] | None = None) -> CrawlResult:
        start = _normalize_start(website)
        result = CrawlResult(website=start)
        if not start:
            result.errors.append("keine Website")
            return result
        self.last_error = None
        home = await self._load_page(start, "startseite", result)
        if home is None and start.startswith("https://"):
            alt = "http://" + start[len("https://") :]
            result.loaded.discard(_norm_key(start))
            home = await self._load_page(alt, "startseite", result)
        if home is None:
            detail = f" ({self.last_error})" if self.last_error else ""
            result.errors.append(f"Startseite nicht erreichbar{detail}")
            return result
        if normalize_domain(home.final_url) != normalize_domain(result.website):
            # Weiterleitung auf eine andere Domain (Umfirmierung, Projektseite): Links gehören zur
            # Zieldomain, sonst verwirft _collect_candidates die gesamte Navigation.
            result.website = home.final_url
            result.pending.clear()
            self._collect_candidates(home, result)
        result.website = home.final_url
        self._collect_frames(home, result)
        if name_hints:
            for entry in list(result.pending):
                if entry[0] > 4 and self._matches_hint(entry, name_hints):
                    result.pending.remove(entry)
                    result.pending.append((4, entry[1], entry[2]))
            result.pending.sort(key=lambda t: t[0])
        await self._drain(result, budget=self.settings.max_pages_per_site, name_hints=name_hints or [])
        await self._guess_impressum(result)
        await self._load_vcards(result)
        if len(result.pages) == 1 and len(home.lines) < 15:
            result.errors.append("wenig Text (SPA oder Cookie-Wall?)")
        return result

    async def _drain(
        self, result: CrawlResult, *, budget: int, name_hints: list[str], only_hints: bool = False
    ) -> None:
        while result.pending and len(result.pages) < budget:
            prio, url, text = result.pending.pop(0)
            if only_hints and not (prio <= 2 or self._matches_hint((prio, url, text), name_hints)):
                continue
            if prio >= 9 and not only_hints and len(result.pages) >= max(3, budget - 2):
                continue  # Restbudget für gezielte Seiten aufheben
            kind = classify_url(url, text)[1]
            if (
                kind == "sonstige"
                and not only_hints
                and not self._matches_hint((prio, url, text), name_hints)
                and sum(1 for p in result.pages if p.kind == "sonstige") >= _MAX_SONSTIGE_PAGES
            ):
                continue  # Objekt-/Stadtteilseiten begrenzen, sonst 8 von 12 Seiten „Immobilienmakler Hürth“
            await self._load_page(url, kind, result)
            if name_hints:
                for entry in list(result.pending):
                    if entry[0] > 4 and self._matches_hint(entry, name_hints):
                        result.pending.remove(entry)
                        result.pending.append((4, entry[1], entry[2]))
                result.pending.sort(key=lambda t: t[0])

    async def crawl_more(self, result: CrawlResult, name_hints: list[str]) -> CrawlResult:
        for entry in list(result.pending):
            if entry[0] > 4 and self._matches_hint(entry, name_hints):
                result.pending.remove(entry)
                result.pending.append((4, entry[1], entry[2]))
        result.pending.sort(key=lambda t: t[0])
        budget = max(len(result.pages), self.settings.max_pages_per_site) + _EXTRA_PAGES_FOR_HINTS
        await self._drain(result, budget=budget, name_hints=name_hints, only_hints=True)
        await self._load_vcards(result)
        return result

    def _collect_frames(self, page: Page, result: CrawlResult) -> None:
        """Frameset-Seiten haben keine Links – die Unterseiten hängen in <frame src=…>."""
        base_domain = normalize_domain(result.website)
        for m in _FRAME_SRC_RE.finditer(page.html):
            href = urljoin(page.final_url, m.group(1).strip())
            if normalize_domain(href) != base_domain or _SKIP_EXT_RE.search(href):
                continue
            key = _norm_key(href)
            if key in result.loaded or any(key == _norm_key(u) for _, u, _ in result.pending):
                continue
            prio, _kind = classify_url(href)
            result.pending.append((min(prio, 5), href, ""))
        result.pending.sort(key=lambda t: t[0])

    async def _guess_impressum(self, result: CrawlResult) -> None:
        """Kein Impressum verlinkt (JavaScript-Menü, Menü zeigt auf eine andere Domain)? Übliche
        Adressen direkt probieren – § 5 DDG verlangt eine leicht erkennbare Anbieterkennzeichnung."""
        if any(p.kind == "impressum" for p in result.pages) or not result.pages:
            return
        parts = _split(result.website)
        base = f"{parts.scheme}://{parts.netloc}"
        for path in _IMPRESSUM_GUESSES:
            url = base + path
            if _norm_key(url) in result.loaded:
                continue
            page = await self._load_page(url, "impressum", result)
            if page is None:
                continue
            if _IMPRESSUM_CONTENT_RE.search("\n".join(page.lines[:80])):
                return
            result.pages.remove(page)  # Server antwortet auf alles mit 200 (Soft-404)

    async def _load_vcards(self, result: CrawlResult) -> None:
        have = {v.url for v in result.vcards}
        for url in result.vcard_urls:
            if len(result.vcards) >= _MAX_VCARDS:
                break
            if url in have:
                continue
            have.add(url)
            if not await self._allowed(url):
                continue
            fetched = await self._fetch(url, accept=_VCARD_TYPES)
            if fetched and "BEGIN:VCARD" in fetched[2].upper():
                result.vcards.append(VCard(url=url, text=fetched[2]))
