"""Orchestrierung: Suche → Dedupe → Enrichment (Entscheider + Handy) → Größe → Förderung → Score → Filter."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from datetime import datetime

from leadscraper import funding, scoring
from leadscraper.cache import Cache
from leadscraper.crawler import CrawlResult, Page, SiteCrawler
from leadscraper.dedupe import dedupe_companies
from leadscraper.exclusions import filter_chains
from leadscraper.extract import impressum as impressum_mod
from leadscraper.extract import people as people_mod
from leadscraper.extract import phones as phones_mod
from leadscraper.extract.htmlutil import decode_cloudflare_email
from leadscraper.extract.names import surname
from leadscraper.extract.size import estimate_size
from leadscraper.models import Company, Enrichment, Lead, Person, PhoneNumber, PhoneSource, SearchSpec
from leadscraper.places import PlacesClient
from leadscraper.settings import Settings

log = logging.getLogger(__name__)

ProgressFn = Callable[[str], None]

_PAGE_KIND_TO_SOURCE: dict[str, PhoneSource] = {
    "impressum": "impressum",
    "kontakt": "kontakt",
    "team": "team",
    "karriere": "karriere",
    "startseite": "startseite",
    "sonstige": "sonstige",
}

_SOCIAL = {
    "linkedin_url": ("linkedin.com/company", "linkedin.com/in/"),
    "xing_url": ("xing.com/",),
    "instagram_url": ("instagram.com/",),
    "facebook_url": ("facebook.com/",),
}


def _dedupe_phones(phones: list[PhoneNumber]) -> list[PhoneNumber]:
    """Pro e164 eine Nummer behalten – Vorrang: mit Person > mit Label > Rest; Impressum/Kontakt zuerst."""
    rank_src = {
        "impressum": 0,
        "kontakt": 1,
        "team": 2,
        "vcard": 2,
        "whatsapp": 3,
        "tel-link": 4,
        "places": 5,
    }
    best: dict[str, PhoneNumber] = {}
    for p in phones:
        cur = best.get(p.e164)
        if cur is None:
            best[p.e164] = p
            continue
        key_new = (0 if p.person else 1, 0 if p.label else 1, rank_src.get(p.source, 9))
        key_cur = (0 if cur.person else 1, 0 if cur.label else 1, rank_src.get(cur.source, 9))
        if key_new < key_cur:
            # Person/Label vom bisherigen Eintrag übernehmen, falls der neue sie nicht hat
            if not p.person and cur.person:
                p = p.model_copy(update={"person": cur.person})
            best[p.e164] = p
        elif cur.person is None and p.person:
            best[p.e164] = cur.model_copy(update={"person": p.person})
    return list(best.values())


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)
_OBFUSCATED_RE = re.compile(
    r"([\w.+-]+)\s*(?:\[at\]|\(at\)|\{at\}|\s@\s|\sat\s|\[ät\])\s*([\w-]+(?:\s*(?:\[dot\]|\(dot\)|\[punkt\]|\(punkt\)|\.)\s*[\w-]+)+)",
    re.I,
)


def _emails_in_text(text: str) -> list[str]:
    found = [m.group(0).lower() for m in _EMAIL_RE.finditer(text)]
    for m in _OBFUSCATED_RE.finditer(text):
        domain = re.sub(r"\s*(?:\[dot\]|\(dot\)|\[punkt\]|\(punkt\))\s*", ".", m.group(2), flags=re.I)
        found.append(f"{m.group(1)}@{domain}".lower().replace(" ", ""))
    return [e for e in found if not e.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"))]


def _collect_emails(pages: list[Page]) -> list[str]:
    seen: dict[str, None] = {}
    for page in pages:
        for addr in _emails_in_text(page.text):
            seen.setdefault(addr, None)
        for link in page.links:
            if link.kind == "mailto":
                addr = link.href.split(":", 1)[1].split("?", 1)[0].strip().lower()
                if addr and "@" in addr:
                    seen.setdefault(addr, None)
            cf = link.attrs.get("data-cfemail")
            if cf:
                dec = decode_cloudflare_email(cf)
                if dec:
                    seen.setdefault(dec.lower(), None)
    return list(seen)


def _collect_social(pages: list[Page]) -> dict[str, str | None]:
    out: dict[str, str | None] = {k: None for k in _SOCIAL}
    for page in pages:
        for link in page.links:
            href = link.href.lower()
            for key, needles in _SOCIAL.items():
                if out[key] is None and any(n in href for n in needles):
                    out[key] = link.href
    return out


def build_enrichment(company: Company, crawl: CrawlResult) -> Enrichment:
    """Aus dem Crawl-Ergebnis alle Informationen extrahieren. Rein, testbar, ohne I/O."""
    enr = Enrichment(website=crawl.website, errors=list(crawl.errors))
    enr.pages_crawled = [p.final_url for p in crawl.pages]

    # 1) Impressum → Entscheider + Firmendaten
    imp_people: list[Person] = []
    impressum_pages = [p for p in crawl.pages if p.kind == "impressum"] or [
        p for p in crawl.pages if impressum_mod.is_impressum_page(p.final_url, p.lines)
    ]
    for page in impressum_pages[:2]:
        data = impressum_mod.parse_impressum(page.lines, page.final_url)
        enr.impressum_url = enr.impressum_url or page.final_url
        enr.legal_name = enr.legal_name or data.legal_name
        enr.rechtsform = enr.rechtsform or data.rechtsform
        enr.handelsregister = enr.handelsregister or data.register
        enr.amtsgericht = enr.amtsgericht or data.amtsgericht
        enr.ustid = enr.ustid or data.ustid
        if data.plz and not enr.impressum_plz:
            enr.impressum_street, enr.impressum_plz, enr.impressum_city = data.street, data.plz, data.city
        imp_people.extend(data.people)

    # 2) Personen von Team-/Kontakt-/sonstigen Seiten
    page_people: list[Person] = []
    for page in crawl.pages:
        if page.kind == "impressum":
            continue
        page_people.extend(
            people_mod.find_people(page.lines, page.links, source_url=page.final_url, page_kind=page.kind)
        )

    # 3) vCards
    vcard_people: list[Person] = []
    for vc in crawl.vcards:
        vcard_people.extend(phones_mod.parse_vcard(vc.text, vc.url))

    people = people_mod.merge_people(imp_people, vcard_people, page_people)

    # 4) Telefonnummern aller Seiten, Personen zuordnen (bekannte Namen zuerst)
    phones: list[PhoneNumber] = []
    for page in crawl.pages:
        phones.extend(
            phones_mod.find_phones(
                page.lines,
                page.links,
                source=_PAGE_KIND_TO_SOURCE.get(page.kind, "sonstige"),
                source_url=page.final_url,
                known_people=people,
            )
        )
    for person in vcard_people:
        phones.extend(person.phones)
    if company.phone:
        pn = phones_mod.classify_number(company.phone, source="places", source_url=company.google_maps_uri)
        if pn:
            phones.append(pn)
    enr.phones = _dedupe_phones(phones)
    people_mod.attach_phones(people, enr.phones)
    enr.people = people

    # 5) E-Mails, Social, WhatsApp
    enr.emails = _collect_emails(crawl.pages)
    for key, val in _collect_social(crawl.pages).items():
        setattr(enr, key, val)
    for page in crawl.pages:
        for link in page.links:
            if link.kind == "whatsapp" and (num := phones_mod.parse_whatsapp_link(link.href)):
                enr.whatsapp_url = f"https://wa.me/{num.lstrip('+')}"
                break
        if enr.whatsapp_url:
            break

    # 6) Größe
    team_pages = [p for p in crawl.pages if p.kind == "team"]
    team_count = (
        len({p.name for p in page_people if p.source_url in {tp.final_url for tp in team_pages}}) or None
    )
    enr.size = estimate_size(
        [(p.final_url, p.text) for p in crawl.pages],
        team_member_count=team_count,
        rechtsform=enr.rechtsform,
        user_rating_count=company.user_rating_count,
    )
    enr.call_indicators = call_indicators(crawl, enr)
    if len(crawl.pages) == 1 and len(crawl.pages[0].lines) < 15 and "wenig Text" not in " ".join(enr.errors):
        enr.errors.append("wenig Text (SPA oder Cookie-Wall?)")
    return enr


_KI_RE = re.compile(
    r"\bKI\b|künstliche[nr]? intelligenz|artificial intelligence|\bAI\b|chatgpt|digitalisierung|"
    r"automatisierung",
    re.I,
)
_WEITERBILDUNG_RE = re.compile(r"weiterbildung|fortbildung|schulung|qualifizierung|seminar", re.I)
_JOBS_RE = re.compile(
    r"stellenangebot|stellenanzeige|wir suchen|bewirb|bewerbung|job|offene stellen|verstärkung", re.I
)


def call_indicators(crawl: CrawlResult, enr: Enrichment) -> list[str]:
    """Anhaltspunkte für sachliches Interesse an KI-Weiterbildung (Doku für § 7 Abs. 2 Nr. 1 UWG)."""
    out: list[str] = []
    texts = [(p.kind, p.text) for p in crawl.pages]
    if any(k == "karriere" for k, _ in texts):
        out.append("Karriere-/Stellenseite vorhanden")
    if any(_JOBS_RE.search(t) for k, t in texts if k == "karriere"):
        out.append("sucht Personal")
    if any(_KI_RE.search(t) for _, t in texts):
        out.append("KI/Digitalisierung auf der Website erwähnt")
    if any(_WEITERBILDUNG_RE.search(t) for _, t in texts):
        out.append("Weiterbildung auf der Website erwähnt")
    if any(p.role_category in ("hr", "ausbildung") for p in enr.people):
        out.append("HR-/Ausbildungsverantwortliche benannt")
    if enr.size.employees_max is not None and enr.size.employees_max <= 49:
        out.append("Betriebsgröße < 50 → 100 % Lehrgangskosten möglich (§ 82 SGB III)")
    return out


async def enrich_company(company: Company, crawler: SiteCrawler) -> Enrichment:
    """Zweistufiger Crawl: erst Impressum (Namen), dann gezielt Seiten mit diesen Namen."""
    if not company.website:
        enr = Enrichment(errors=["keine Website bei Google Places"])
        if company.phone:
            pn = phones_mod.classify_number(
                company.phone, source="places", source_url=company.google_maps_uri
            )
            if pn:
                enr.phones = [pn]
        enr.size = estimate_size([], user_rating_count=company.user_rating_count)
        return enr

    crawl = await crawler.crawl(company.website)
    # Namen aus dem Impressum → zweite, gezielte Runde (Team-/Objekt-/Ansprechpartner-Seiten)
    hints: list[str] = []
    for page in crawl.pages:
        if page.kind == "impressum":
            data = impressum_mod.parse_impressum(page.lines, page.final_url)
            hints.extend(surname(p.name) for p in data.people if p.name)
    hints = [h for h in dict.fromkeys(hints) if len(h) >= 3]
    if hints or crawl.pending:
        crawl = await crawler.crawl_more(crawl, hints)
    return build_enrichment(company, crawl)


def finalize_lead(
    company: Company, enrichment: Enrichment | None, spec: SearchSpec, funding_cfg: dict
) -> Lead:
    lead = Lead(company=company, enrichment=enrichment, scraped_at=datetime.now())
    size = enrichment.size if enrichment else None
    lead.funding = funding.assess(size, company.bundesland, config=funding_cfg) if size else None
    lead.in_target_size = scoring.in_target_size(lead, spec)
    lead.score, lead.score_reasons = scoring.score_lead(lead, spec)
    lead.premium_missing = scoring.premium_check(lead, spec)
    lead.premium = not lead.premium_missing
    return lead


def passes_filters(lead: Lead, spec: SearchSpec) -> bool:
    if spec.premium and not lead.premium:
        return False
    if spec.require_mobile and lead.best_mobile is None:
        return False
    # Größe: nur sicher Unpassende aussortieren; Unbekannte bleiben drin (werden im Score abgewertet)
    if lead.in_target_size is False and lead.enrichment and lead.enrichment.size.confidence == "high":
        return False
    return True


async def search_companies(
    spec: SearchSpec, places: PlacesClient, progress: ProgressFn | None = None
) -> list[Company]:
    cities: list[str | None] = list(dict.fromkeys([spec.city, *spec.cities])) or [None]
    companies: list[Company] = []
    for city in cities:
        lat, lng = (spec.lat, spec.lng) if city == spec.city else (None, None)
        if (lat is None or lng is None) and city:
            coords = await places.geocode(city, language=spec.language, region=spec.region)
            if coords:
                lat, lng = coords
                if city == spec.city:
                    spec.lat, spec.lng = lat, lng
        for q in spec.queries:
            text = f"{q} {city}" if city and city.lower() not in q.lower() else q
            found = await places.text_search(
                text,
                lat=lat,
                lng=lng,
                radius_km=spec.radius_km,
                included_type=spec.included_type,
                max_results=spec.max_results_per_query,
                language=spec.language,
                region=spec.region,
            )
            for c in found:
                c.query = q
            companies.extend(found)
            if progress:
                progress(f"Suche „{text}“: {len(found)} Treffer")
    deduped = dedupe_companies(companies)
    dropped: list = []
    if spec.exclude_chains:
        deduped, dropped = filter_chains(deduped)
    if progress:
        msg = f"{len(companies)} Treffer, {len(deduped)} nach Deduplizierung"
        if dropped:
            msg += f", {len(dropped)} Ketten/Franchise ausgeschlossen"
        progress(msg)
    return deduped


async def enrich_all(
    companies: list[Company],
    settings: Settings,
    cache: Cache | None,
    progress: ProgressFn | None = None,
) -> list[Enrichment | None]:
    crawler = SiteCrawler(settings, cache=cache)
    sem = asyncio.Semaphore(settings.concurrency)
    results: list[Enrichment | None] = [None] * len(companies)
    done = 0

    async def one(i: int, c: Company) -> None:
        nonlocal done
        async with sem:
            try:
                results[i] = await enrich_company(c, crawler)
            except Exception as exc:  # noqa: BLE001 – ein kaputter Shop darf den Lauf nicht abbrechen
                log.warning("Enrichment fehlgeschlagen für %s (%s): %s", c.name, c.website, exc)
                results[i] = Enrichment(website=c.website, errors=[f"{type(exc).__name__}: {exc}"])
            done += 1
            if progress:
                enr = results[i]
                dm = next((p for p in enr.decision_makers if p.mobile), None) if enr else None
                info = (
                    f"Entscheider-Handy: {dm.name}"
                    if dm
                    else f"{len(enr.mobiles) if enr else 0} Handynummer(n)"
                )
                progress(f"[{done}/{len(companies)}] {c.name} – {info}")

    try:
        await asyncio.gather(*(one(i, c) for i, c in enumerate(companies)))
    finally:
        await crawler.close()
    return results


def warn_unreachable(
    companies: list[Company], enrichments: list[Enrichment | None], progress: ProgressFn | None
) -> None:
    """Fast keine Website erreichbar → meist Netzwerk/Proxy/Firewall – deutlich sagen."""
    with_site = [(c, e) for c, e in zip(companies, enrichments, strict=True) if c.website]
    if len(with_site) < 5 or progress is None:
        return
    failed = [(c, e) for c, e in with_site if e is None or not e.pages_crawled]
    if len(failed) / len(with_site) >= 0.8:
        first = next((err for _, e in failed if e for err in e.errors), "")
        progress(
            f"⚠ {len(failed)} von {len(with_site)} Websites nicht erreichbar – Netzwerk/Proxy/Firewall "
            f"prüfen. Erster Fehler: {first}"
        )


async def run(spec: SearchSpec, settings: Settings, progress: ProgressFn | None = None) -> list[Lead]:
    if not settings.google_places_api_key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY fehlt (.env anlegen, siehe .env.example)")
    cache = Cache(settings.cache_path)
    places = PlacesClient(
        settings.google_places_api_key, cache=cache, cache_ttl_days=settings.places_cache_ttl_days
    )
    try:
        companies = await search_companies(spec, places, progress)
    finally:
        await places.close()
    leads = await build_leads(companies, spec, settings, cache, progress)
    cache.close()
    return leads


async def build_leads(
    companies: list[Company],
    spec: SearchSpec,
    settings: Settings,
    cache: Cache | None,
    progress: ProgressFn | None = None,
) -> list[Lead]:
    enrichments = await enrich_all(companies, settings, cache, progress)
    warn_unreachable(companies, enrichments, progress)
    cfg = funding.load_funding_config()
    leads = [finalize_lead(c, e, spec, cfg) for c, e in zip(companies, enrichments, strict=True)]
    leads = [ld for ld in leads if passes_filters(ld, spec)]
    leads.sort(key=scoring.sort_key)
    if progress:
        with_mobile = sum(1 for ld in leads if ld.best_mobile)
        dm_mobile = sum(1 for ld in leads if ld.best_contact and ld.best_contact.mobile)
        progress(
            f"{len(leads)} Leads, davon {with_mobile} mit Handynummer, {dm_mobile} Entscheider mit Handy"
        )
    return leads
