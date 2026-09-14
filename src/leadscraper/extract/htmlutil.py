"""HTML → Text/Zeilen/Links. Gemeinsame Basis aller Extraktoren.

- extract_text(html): sichtbarer Text; Block-Elemente erzeugen Zeilenumbrüche, <script>/<style>/… entfallen.
- extract_lines(html): nicht-leere, gestrippte Zeilen – Grundlage für die Zuordnung Telefonnummer ↔ Person.
- extract_links(html, base_url): alle <a href> absolut, mit Anker-Text und Klassifikation
  ("tel", "mailto", "whatsapp", "vcard", "internal", "external", "social", "other").
- decode_cloudflare_email(hex): Cloudflare-E-Mail-Schutz (data-cfemail) dekodieren.
"""

from __future__ import annotations

import html as html_mod
import re
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urljoin, urlsplit

from selectolax.parser import HTMLParser, Node

from leadscraper.dedupe import normalize_domain

LinkKind = Literal["tel", "mailto", "whatsapp", "vcard", "internal", "external", "social", "other"]

_DROP_TAGS = ("script", "style", "noscript", "svg", "template", "head", "iframe", "canvas")
_BLOCK_TAGS = frozenset(
    "p div li ul ol tr table thead tbody tfoot h1 h2 h3 h4 h5 h6 address section article header footer "
    "nav aside main form fieldset legend blockquote pre dl dt dd figure figcaption hr details summary "
    "option select textarea label button".split()
)
_CELL_TAGS = frozenset({"td", "th"})
_SOCIAL_HOSTS = (
    "linkedin.com",
    "xing.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "pinterest.",
    "kununu.com",
)
_WS_RE = re.compile(r"[ \t\r\f\v ]+")


@dataclass
class Link:
    href: str
    text: str
    kind: LinkKind
    attrs: dict[str, str] = field(default_factory=dict)


def _parse(html: str) -> HTMLParser:
    tree = HTMLParser(html or "")
    tree.strip_tags(list(_DROP_TAGS))
    return tree


def _walk(node: Node, out: list[str]) -> None:
    for child in node.iter(include_text=True):
        tag = child.tag
        if tag == "-text":
            text = child.text(deep=False)
            if text:
                out.append(text)
            continue
        if tag == "br":
            out.append("\n")
            continue
        if tag in _DROP_TAGS:
            continue
        if tag in _BLOCK_TAGS:
            out.append("\n")
            _walk(child, out)
            out.append("\n")
        elif tag in _CELL_TAGS:
            out.append("\t")
            _walk(child, out)
            out.append("\t")
        elif tag == "a":
            out.append(" ")
            before = len(out)
            _walk(child, out)
            number = _number_from_href(child.attributes.get("href") or "")
            if number and not any(ch.isdigit() for ch in "".join(out[before:])):
                out.append(f" {number}")  # "Mobil" → "Mobil +49171…": Nummer steht im Textkontext
            out.append(" ")
        else:
            _walk(child, out)


def _number_from_href(href: str) -> str | None:
    """Rufnummer aus tel:-/WhatsApp-Links (nur Ziffern und führendes +)."""
    low = href.strip().lower()
    if low.startswith(("tel:", "callto:")):
        raw = html_mod.unescape(href.split(":", 1)[1])
        digits = re.sub(r"[^\d+]", "", raw.replace("%20", ""))
        if digits.startswith("00"):
            digits = "+" + digits[2:]
        return digits if len(re.sub(r"\D", "", digits)) >= 7 else None
    m = re.search(r"wa\.me/(\d{8,15})|[?&]phone=(?:%2b|\+)?(\d{8,15})", low)
    if m:
        return "+" + (m.group(1) or m.group(2))
    return None


def extract_text(html: str) -> str:
    tree = _parse(html)
    root = tree.body or tree.root
    if root is None:
        return ""
    parts: list[str] = []
    _walk(root, parts)
    raw = html_mod.unescape("".join(parts))
    lines = []
    for line in raw.replace("\t", " · ").split("\n"):
        cleaned = _WS_RE.sub(" ", line)
        cleaned = re.sub(r"(?:\s*·\s*)+", " · ", cleaned).strip(" ·")
        lines.append(cleaned)
    # mehrfache Leerzeilen zusammenfassen
    text = "\n".join(lines)
    return re.sub(r"\n{2,}", "\n", text).strip()


def extract_lines(html: str) -> list[str]:
    return [line for line in extract_text(html).split("\n") if line.strip()]


def decode_cloudflare_email(encoded: str) -> str | None:
    try:
        data = bytes.fromhex(encoded.strip())
    except ValueError:
        return None
    if len(data) < 2:
        return None
    key = data[0]
    try:
        return bytes(b ^ key for b in data[1:]).decode("utf-8")
    except UnicodeDecodeError:
        return None


def classify_href(href: str, base_url: str, base_domain: str | None = None) -> LinkKind:
    low = href.lower()
    if low.startswith("tel:") or low.startswith("callto:"):
        return "tel"
    if low.startswith("mailto:"):
        return "mailto"
    if "wa.me/" in low or "whatsapp.com" in low or low.startswith("whatsapp:"):
        return "whatsapp"
    if low.startswith(("javascript:", "#", "data:")) or low in ("", "/#"):
        return "other"
    parts = urlsplit(low)
    if parts.path.endswith(".vcf"):
        return "vcard"
    if not parts.scheme and not parts.netloc:
        return "internal"  # relativer Link
    host = parts.hostname or ""
    if any(s in host for s in _SOCIAL_HOSTS):
        return "social"
    if base_domain is None:
        base_domain = normalize_domain(base_url)
    if base_domain and normalize_domain(href) == base_domain:
        return "internal"
    return "external"


def extract_links(html: str, base_url: str) -> list[Link]:
    tree = _parse(html)
    base_domain = normalize_domain(base_url)
    links: list[Link] = []
    for node in tree.css("a[href], a[data-cfemail], [data-cfemail]"):
        attrs = {k: (v or "") for k, v in node.attributes.items() if k != "href"}
        cf = attrs.get("data-cfemail")
        href = node.attributes.get("href") or ""
        if cf:
            decoded = decode_cloudflare_email(cf)
            if decoded:
                href = f"mailto:{decoded}"
        href = html_mod.unescape(href).strip()
        if not href:
            continue
        kind = classify_href(href, base_url, base_domain)
        if kind in ("internal", "external", "vcard", "social"):
            href = urljoin(base_url, href)
            href, _, _ = href.partition("#")
        text = _WS_RE.sub(" ", node.text(separator=" ", strip=True)).strip()
        if kind == "vcard" and ".vcf" not in href.lower():
            kind = "internal"
        links.append(Link(href=href, text=text, kind=kind, attrs=attrs))
    return links
