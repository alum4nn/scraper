"""Deduplizierung von Firmen über Suchläufe hinweg (place_id, Domain, Telefonnummer)."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import tldextract

from leadscraper.models import Company

_extract = tldextract.TLDExtract(suffix_list_urls=())  # offline, keine Netzabfrage der Suffix-Liste


def normalize_domain(website_or_domain: str | None) -> str | None:
    """Registrierbare Domain (ohne www), z. B. 'beispiel-makler.de'. Unbekannte TLDs → Hostname ohne www."""
    if not website_or_domain:
        return None
    value = website_or_domain.strip().lower()
    if not value:
        return None
    if "://" not in value:
        value = "http://" + value
    try:
        ext = _extract(value)
        if ext.top_domain_under_public_suffix:
            return ext.top_domain_under_public_suffix
        host = urlsplit(value).hostname or ""
    except ValueError:
        return None  # kaputte URL auf der Seite (z. B. „http://[“) – kein gültiger Host
    host = host.removeprefix("www.")
    return host or None


def normalize_phone_key(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    if digits.startswith("0049"):
        digits = "49" + digits[4:]
    elif digits.startswith("0"):
        digits = "49" + digits[1:]
    # "+49 (0) 221 …" → nach Ländervorwahl steht oft noch eine 0
    if digits.startswith("490"):
        digits = "49" + digits[3:]
    return digits if len(digits) >= 8 else None


def _merge(into: Company, other: Company) -> None:
    for field_name in Company.model_fields:
        if field_name == "query":
            continue
        if getattr(into, field_name) in (None, "", []):
            setattr(into, field_name, getattr(other, field_name))
    existing = [q.strip() for q in (into.query or "").split("|") if q.strip()]
    if other.query and other.query not in existing:
        into.query = " | ".join([*existing, other.query])


def dedupe_companies(companies: list[Company]) -> list[Company]:
    result: list[Company] = []
    by_place: dict[str, Company] = {}
    by_domain: dict[str, Company] = {}
    by_phone: dict[str, Company] = {}
    for c in companies:
        dom = normalize_domain(c.website or c.domain)
        phone = normalize_phone_key(c.phone or c.phone_international)
        existing = by_place.get(c.place_id) or (dom and by_domain.get(dom)) or (phone and by_phone.get(phone))
        if existing:
            _merge(existing, c)
            target = existing
        else:
            target = c.model_copy(deep=True)
            if dom and not target.domain:
                target.domain = dom
            result.append(target)
        by_place.setdefault(c.place_id, target)
        if dom:
            by_domain.setdefault(dom, target)
        if phone:
            by_phone.setdefault(phone, target)
    return result
