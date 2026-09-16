"""Orchestrierung: Suche → Dedupe → Enrichment (Entscheider + Handy) → Größe → Förderung → Score → Filter."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError

from leadscraper import funding, scoring
from leadscraper.budget import request_budget
from leadscraper.cache import Cache
from leadscraper.crawler import CrawlResult, Page, SiteCrawler
from leadscraper.dedupe import dedupe_companies
from leadscraper.exclusions import filter_chains
from leadscraper.extract import impressum as impressum_mod
from leadscraper.extract import people as people_mod
from leadscraper.extract import phones as phones_mod
from leadscraper.extract.htmlutil import decode_cloudflare_email
from leadscraper.extract.names import surname
from leadscraper.extract.size import (
    estimate_size,
    evidence_still_holds,
    headcount_from_indicators,
    is_rating_text,
)
from leadscraper.extract.staff import count_staff, personal_mailboxes
from leadscraper.extract.standorte import standort_hinweise
from leadscraper.models import (
    Company,
    Enrichment,
    Lead,
    Person,
    PhoneNumber,
    PhoneSource,
    SearchSpec,
    SizeEstimate,
)
from leadscraper.places import PlacesClient
from leadscraper.settings import Settings

log = logging.getLogger(__name__)

_DECIDER_ROLES = {"geschaeftsfuehrung", "inhaber", "vorstand"}

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


def _drop_shared_numbers(deduped: list[PhoneNumber], alle: list[PhoneNumber]) -> list[PhoneNumber]:
    """Steht dieselbe Nummer bei mehreren Personen, ist es die Firmennummer – dann keine Zuordnung.

    Viele Team-Seiten wiederholen unter jedem Porträt dieselbe Zentrale. Wer sie einer Person zuschreibt,
    ruft am Telefon den Falschen auf. Umgekehrt darf eine Nummer, die auf mehreren Seiten immer beim
    selben Menschen steht, ihm zugeordnet bleiben – das ist bei Inhabern der Normalfall.
    """
    personen: dict[str, set[str]] = {}
    for phone in alle:
        if phone.person:
            personen.setdefault(phone.e164, set()).add(phone.person)
    for phone in deduped:
        if len(personen.get(phone.e164, ())) > 1:
            phone.person = None
    return deduped


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


def _scope_to_own_location(urls: set[str], website: str | None) -> set[str]:
    """Portale mit vielen Standorten: nur Seiten unterhalb des eigenen Pfads zählen.

    Franchise-Systeme führen jeden Lizenzpartner unter einer eigenen Unterseite
    (`/immobilienmakler-in-koeln/sued/`). Ohne diese Einschränkung sammelt der Crawler die Belegschaft
    der Zentrale und fremder Standorte ein und schreibt sie dem örtlichen Betrieb zu.
    """
    if not website:
        return urls
    basis = urlsplit(website).path.rstrip("/")
    if basis.count("/") < 2:  # normale Firmenseite, kein Standort-Unterpfad
        return urls
    # Bewusst ohne Rückfall auf alle Seiten: Findet sich unter dem eigenen Standort keine Team-Seite,
    # ist die Belegschaft eben unbelegt – die der Zentrale gehört nicht diesem Betrieb.
    return {u for u in urls if urlsplit(u).path.rstrip("/").startswith(basis)}


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
    enr.phones = _drop_shared_numbers(_dedupe_phones(phones), phones)
    people_mod.attach_phones(people, enr.phones)
    enr.people = people
    promote_responsible_owner(enr, company.name)

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

    # 6) Größe – Personen auf Team- UND Kontakt-/Standortseiten („Ihre Ansprechpartner in Köln-Süd“);
    #    find_people ist dort streng (Rolle, bekannter Vorname oder Kontaktdaten); Bewertungen zählen nicht
    staff_urls = {p.final_url for p in crawl.pages if p.kind in ("team", "kontakt")}
    staff_urls = _scope_to_own_location(staff_urls, company.website)
    team_count = len({p.name for p in page_people if p.source_url in staff_urls}) or None
    # Team-Karten ohne Fließtext: Namen stehen im Link auf die Unterseite oder im Bild-Alternativtext
    karten_people: list[Person] = []
    for page in crawl.pages:
        if page.final_url in staff_urls:
            karten_people.extend(
                people_mod.staff_from_links_and_images(page.links, page.image_alts, source_url=page.final_url)
            )
    staff_people = people_mod.merge_people(
        [p for p in page_people if p.source_url in staff_urls], karten_people
    )
    enr.size = estimate_size(
        [(p.final_url, p.text) for p in crawl.pages],
        team_member_count=team_count,
        staff_mailboxes=len(personal_mailboxes(enr.emails, people)) or None,
        staff_phones=len({ph.person for ph in enr.phones if ph.person}) or None,
        rechtsform=enr.rechtsform,
        user_rating_count=company.user_rating_count,
    )
    stated = enr.size.point_estimate if enr.size.confidence == "high" else None
    enr.staff = count_staff(
        staff_people,
        enr.emails,
        enr.phones,
        all_people=people,
        stated=stated,
        stated_evidence=enr.size.evidence[0] if stated and enr.size.evidence else None,
    )
    attribute_sole_mobile(enr)
    enr.employment_signal, enr.employment_evidence = employment_signal(crawl, enr)  # nach size/Zuordnung
    enr.call_indicators = call_indicators(crawl, enr)
    alle_zeilen = [z for seite in crawl.pages for z in seite.lines]
    anker = [link.text for seite in crawl.pages for link in seite.links if link.text]
    enr.mehrstandort, enr.mehrstandort_beleg, _ = standort_hinweise(alle_zeilen, anker)
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


_EMPLOYED_RE = re.compile(
    r"festanstellung|festangestellt|unbefristet|sozialversicherungspflichtig|angestellte[nr]?\b|innendienst|"
    r"backoffice|back-office|büroleit|teamassisten|assistenz der geschäftsführung|vertriebsassisten|"
    r"immobilienassisten|empfang|sekretariat|buchhaltung|auszubildende|azubi|ausbildungsplatz|ausbildung zum|"
    r"ausbildung zur|immobilienkaufmann|immobilienkauffrau|werkstudent|vollzeit|teilzeit|"
    r"\d+\s*(?:mitarbeiter|beschäftigte|angestellte)",
    re.I,
)
_FREELANCE_RE = re.compile(
    r"freie[rn]?\s+(?:mitarbeiter|immobilienberater|immobilienmakler|handelsvertreter|vertriebspartner)|"
    r"freiberuflich|handelsvertreter|"
    r"selbst(?:st)?ändige[rn]?\s+\w*(?:berater|maklerin|makler|vertriebspartner|partner|vermittler)|"
    r"auf\s+selbst(?:st)?ändiger\s+basis|zusammenschluss\s+von\s+rechtlich\s+selbst(?:st)?ändigen|"
    r"rechtlich\s+(?:eigenständige|selbst(?:st)?ändige)[sn]?\s+unternehmen|"
    r"auf\s+provisionsbasis|provisionsbasis|lizenzpartner|lizenznehmer|franchisenehmer|franchise|"
    r"§\s*84\s*hgb",
    re.I,
)
_EMPLOYED_ROLE_RE = re.compile(
    r"assisten|büroleit|innendienst|backoffice|empfang|sekretariat|buchhalt|auszubildende|azubi|"
    r"immobilienkaufmann|immobilienkauffrau|marketing|office|verwaltung|vermietung",
    re.I,
)


_RESPONSIBLE_RE = re.compile(r"verantwortlich|redaktion|§\s*18|v\.\s*i\.\s*s\.\s*d\.", re.I)


def promote_responsible_owner(enr: Enrichment, company_name: str) -> None:
    """Kleine Maklerbüros nennen im Impressum nur den nach § 18 MStV Verantwortlichen. Trägt dieser den
    Firmennamen (Immobilienzentrum **Hoffmann** → Patrick **Hoffmann**), ist er der Inhaber."""
    if any(p.role_category in _DECIDER_ROLES for p in enr.people):
        return
    haystack = " ".join(filter(None, [company_name, enr.legal_name])).casefold()
    for person in enr.people:
        if person.role_category != "sonstige" or not _RESPONSIBLE_RE.search(person.role or ""):
            continue
        sn = surname(person.name).casefold()
        if len(sn) >= 4 and sn in haystack:
            person.role_category = "inhaber"
            person.role = "Inhaber/-in (Firmenname, im Impressum verantwortlich)"
            return


def attribute_sole_mobile(enr: Enrichment) -> None:
    """Eine einzige Handynummer auf der ganzen Website + genau ein Entscheider, sonst niemand mit Handy:
    Dann gehört sie diesem Entscheider (Ein-Personen-Maklerbüro). Wird als Zuordnung „eindeutig“ vermerkt,
    damit im Telefonat klar ist, dass der Name nicht direkt neben der Nummer stand."""
    deciders = [p for p in enr.decision_makers if p.role_category in _DECIDER_ROLES]
    if any(p.mobile for p in deciders):
        enr.mobile_assignment = "namentlich"
        return
    if len(deciders) != 1:
        return
    mobiles = [m for m in enr.mobiles if m.source != "places"]
    if len(mobiles) != 1 or mobiles[0].person:
        return
    decider = deciders[0]
    mobiles[0].person = decider.name
    decider.phones.append(mobiles[0])
    enr.mobile_assignment = "eindeutig"
    enr.mobile_assignment_note = (
        f"einzige Handynummer der Website, einziger Entscheider ({decider.name}) – Name stand nicht "
        f"unmittelbar neben der Nummer ({mobiles[0].source_url or ''})"
    )


def employment_signal(crawl: CrawlResult, enr: Enrichment) -> tuple[str, list[str]]:
    """Sozialversicherungspflichtige Beschäftigte erkennbar (§ 82 SGB III) oder freie Vertreter?"""
    positive: list[str] = []
    negative: list[str] = []
    for page in crawl.pages:
        for m in _EMPLOYED_RE.finditer(page.text):
            positive.append(
                f"„{page.text[max(0, m.start() - 25) : m.end() + 25].strip()}“ ({page.final_url})"
            )
            if len(positive) >= 3:
                break
        for m in _FREELANCE_RE.finditer(page.text):
            negative.append(
                f"„{page.text[max(0, m.start() - 25) : m.end() + 25].strip()}“ ({page.final_url})"
            )
            if len(negative) >= 3:
                break
    for person in enr.people:
        if person.role and _EMPLOYED_ROLE_RE.search(person.role):
            positive.append(f"Rolle „{person.role}“: {person.name}")
    # Indiz statt Fundstelle: Mehrere namentliche Mitarbeitende neben dem/den Entscheidern bedeuten
    # Beschäftigte – ein Ein-Mann-Büro mit freien Partnern führt keine sechs Leute mit Firmen-E-Mail.
    staff = [p for p in enr.people if p.role_category not in _DECIDER_ROLES]
    if len(staff) >= 2:
        names = ", ".join(p.name for p in staff[:3])
        positive.append(f"{len(staff)} Mitarbeitende neben der Geschäftsführung ({names} …)")
    if (enr.size.employees_min or 0) >= 5 and enr.size.confidence in ("high", "medium"):
        positive.append(f"belegte Betriebsgröße ab {enr.size.employees_min} Personen")
    evidence = [f"+ {x}" for x in positive[:3]] + [f"− {x}" for x in negative[:3]]
    if negative and not positive:
        return "frei", evidence
    if positive:
        return "angestellt", evidence
    return "unklar", evidence


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
    if enr.employment_signal == "angestellt":
        out.append("Festangestellte erkennbar (förderfähig)")
    elif enr.employment_signal == "frei":
        out.append("⚠ freie Handelsvertreter/Franchise erwähnt – Beschäftigte prüfen")
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
                # Schutzuhr je Betrieb. Ohne sie kann eine einzige hängende Verbindung den Platz
                # dauerhaft belegen; ein Lauf über 1.600 Firmen stand so anderthalb Stunden still,
                # ohne Rechenlast und ohne eine einzige geladene Seite.
                results[i] = await asyncio.wait_for(
                    enrich_company(c, crawler), timeout=settings.site_timeout_seconds
                )
            except TimeoutError:
                log.warning("Zeitüberschreitung für %s (%s)", c.name, c.website)
                results[i] = Enrichment(
                    website=c.website,
                    errors=[f"Zeitüberschreitung nach {settings.site_timeout_seconds:.0f} s"],
                )
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
        settings.google_places_api_key,
        cache=cache,
        cache_ttl_days=settings.places_cache_ttl_days,
        budget=request_budget(settings),
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


# --- Bundesweiter Lauf: Ort für Ort, Ergebnisse als JSONL, Wiederaufnahme nach Abbruch --------------


def load_orte(path: Path | None = None, bundeslaender: list[str] | None = None) -> list[dict]:
    """Ortsraster aus config/orte.yaml (optional auf Bundesländer gefiltert)."""
    import yaml

    from leadscraper.geo import normalize_bundesland
    from leadscraper.settings import CONFIG_DIR

    with open(path or CONFIG_DIR / "orte.yaml", encoding="utf-8") as fh:
        orte = yaml.safe_load(fh)["orte"]
    if bundeslaender:
        wanted = {normalize_bundesland(b) or b for b in bundeslaender}
        orte = [o for o in orte if o["bundesland"] in wanted]
    return orte


def refresh_lead(lead: Lead, spec: SearchSpec, funding_cfg: dict) -> Lead:
    """Einen gespeicherten Lead ohne neuen Crawl neu bewerten: Größen-Indizien, Beschäftigtenstatus,
    Handy-Zuordnung, Förderung, Score, Premium. Nutzt nur, was in der JSONL-Datei steht – so wirken
    Verbesserungen an den Regeln auch auf Orte, die schon abgearbeitet sind (ohne Google-Kosten)."""
    enr = lead.enrichment
    if enr is None:
        return finalize_lead(lead.company, None, spec, funding_cfg)
    promote_responsible_owner(enr, lead.company.name)
    attribute_sole_mobile(enr)
    # Zuerst die gespeicherte Fundstelle gegen die heutigen Regeln prüfen: Portalbewertungen,
    # Aktenzeichen und Berufsbezeichnungen ohne Besitzbezug belegen keine Belegschaft.
    erste = enr.size.evidence[0] if enr.size.evidence else ""
    if erste and (is_rating_text(erste) or not evidence_still_holds(erste)):
        enr.size = SizeEstimate()
    staff_urls = set(enr.pages_crawled)
    stated = enr.size.point_estimate if enr.size.confidence == "high" else None
    enr.staff = count_staff(
        [p for p in enr.people if p.source_url in staff_urls],
        enr.emails,
        enr.phones,
        all_people=enr.people,
        stated=stated,
        stated_evidence=enr.size.evidence[0] if stated and enr.size.evidence else None,
    )
    if enr.size.confidence in ("none", "low"):
        team_count = len({p.name for p in enr.people if p.source_url in set(enr.pages_crawled)}) or None
        indicator = headcount_from_indicators(
            team_count,
            len(personal_mailboxes(enr.emails, enr.people)) or None,
            len({ph.person for ph in enr.phones if ph.person}) or None,
        )
        if indicator is not None:
            n, why = indicator
            enr.size = SizeEstimate(
                employees_min=n,
                employees_max=max(12, round(n * 2.5)),
                point_estimate=max(n, round(n * 1.4)),
                confidence="medium" if n >= 3 else "low",
                evidence=[f"Indiz: {why} (mindestens so viele Beschäftigte)", *enr.size.evidence[:2]],
            )
    staff = [p for p in enr.people if p.role_category not in _DECIDER_ROLES]
    extra = []
    if len(staff) >= 2:
        names = ", ".join(p.name for p in staff[:3])
        extra.append(f"+ {len(staff)} Mitarbeitende neben der Geschäftsführung ({names} …)")
    if (enr.size.employees_min or 0) >= 5 and enr.size.confidence in ("high", "medium"):
        extra.append(f"+ belegte Betriebsgröße ab {enr.size.employees_min} Personen")
    for line in extra:
        if line not in enr.employment_evidence:
            enr.employment_evidence.append(line)
    if extra and enr.employment_signal == "unklar":
        enr.employment_signal = "angestellt"
    return finalize_lead(lead.company, enr, spec, funding_cfg)


def read_leads_jsonl(path: Path) -> list[Lead]:
    """Gespeicherte Leads lesen. Eine abgeschnittene letzte Zeile (Abbruch mitten im Schreiben) wird
    übersprungen, damit ein unterbrochener Lauf wieder aufgenommen werden kann."""
    if not path.exists():
        return []
    leads: list[Lead] = []
    broken = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            leads.append(Lead.model_validate_json(line))
        except ValidationError:
            broken += 1
    if broken:
        log.warning("%s: %d unvollständige Zeile(n) übersprungen", path, broken)
    return leads


async def run_cities(
    spec: SearchSpec,
    settings: Settings,
    orte: list[dict],
    jsonl_path: Path,
    progress: ProgressFn | None = None,
    checkpoint: Callable[[list[Lead]], None] | None = None,
) -> list[Lead]:
    """Alle Orte nacheinander; fertige Orte stehen in <jsonl>.state.json, Leads sofort in der JSONL-Datei.
    Ein erneuter Aufruf mit derselben Datei macht dort weiter, wo abgebrochen wurde."""
    if not settings.google_places_api_key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY fehlt (.env anlegen, siehe .env.example)")
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    state_path = jsonl_path.with_suffix(".state.json")
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else {"done": [], "seen": []}
    )
    done, seen = set(state["done"]), set(state["seen"])
    all_leads = read_leads_jsonl(jsonl_path)
    cache = Cache(settings.cache_path)
    places = PlacesClient(
        settings.google_places_api_key,
        cache=cache,
        cache_ttl_days=settings.places_cache_ttl_days,
        budget=request_budget(settings),
    )
    try:
        for i, ort in enumerate(orte, start=1):
            key = f"{ort['name']}|{ort['bundesland']}"
            if key in done:
                continue
            if progress:
                progress(f"[Ort {i}/{len(orte)}] {ort['name']} ({ort['bundesland']})")
            city_spec = spec.model_copy(
                update={
                    "city": ort["name"],
                    "cities": [],
                    "lat": None,
                    "lng": None,
                    "radius_km": float(ort.get("radius_km", spec.radius_km)),
                }
            )
            companies = await search_companies(city_spec, places, progress)
            fresh = []
            for c in companies:
                dom = c.domain or ""
                if c.place_id in seen or (dom and dom in seen):
                    continue
                seen.add(c.place_id)
                if dom:
                    seen.add(dom)
                fresh.append(c)
            leads = await build_leads(fresh, spec, settings, cache, progress) if fresh else []
            with open(jsonl_path, "a", encoding="utf-8") as fh:
                for ld in leads:
                    fh.write(ld.model_dump_json() + "\n")
            all_leads.extend(leads)
            done.add(key)
            state_path.write_text(json.dumps({"done": sorted(done), "seen": sorted(seen)}), encoding="utf-8")
            if checkpoint and i % 10 == 0:
                checkpoint(all_leads)
    finally:
        await places.close()
        cache.close()
    all_leads.sort(key=scoring.sort_key)
    return all_leads
