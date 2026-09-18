"""Verifikations-Sonde: laedt offizielle Firmenseiten und liefert je Mobilnummer
den Textkontext, die Zahl der Fundseiten (Footer-Erkennung) und ob eine
Geschaeftsfuehrer-/Inhaber-Rolle unmittelbar davor steht.

Ergaenzt den Crawler um genau die Pruefungen, die eine belastbare Zuordnung
"Mobilnummer gehoert dem Entscheider" braucht:
  * Nummer auf >=3 Seiten  -> Footer-/Allgemeinnummer, keine Personennummer
  * Rollen-Wort <=220 Zeichen davor -> Kandidat fuer Entscheider-Zuordnung
  * Klassifikation strikt ueber phonenumbers (MOBILE), nicht ueber Praefix-Raten

Aufruf: python tools/impressum_probe.py domains.txt > treffer.jsonl
"""

import asyncio
import json
import re
import sys
from urllib.parse import urljoin, urlparse

import httpx
import phonenumbers
from phonenumbers import PhoneNumberType
from selectolax.parser import HTMLParser

UA = "LeadResearch/0.1 (+mailto:kontakt@example.de)"
WANT = ("impressum", "kontakt", "team", "ueber-uns", "über-uns", "about", "ansprechpartner", "unternehmen")
PHONE_RE = re.compile(r"(?:\+49|0049|0)\s*\(?\s*1\s*[567]\s*\d\s*\)?[\s\-/.–]*(?:\d[\s\-/.–]*){5,11}")
GF_NEAR_RE = re.compile(
    r"(Geschäftsführ\w*|Geschäftsleitung|Inhaber(?:in)?|Alleininhaber"
    r"|Vorstand|Firmeninhaber|Gesellschafter-Geschäftsführer)",
    re.I,
)
ROLE_RE = re.compile(
    r"(Geschäftsführer(?:in)?|Inhaber(?:in)?|Vorstand|vertreten durch"
    r"|Betriebsleiter|Alleinvorstand|Gesellschafter)",
    re.I,
)
EMP_RE = re.compile(
    r"(?:(\d{1,4})\s*(?:Mitarbeiter|Mitarbeitende|Beschäftigte|Kolleg|Angestellte|MitarbeiterInnen)"
    r"|(?:Team\s+(?:von|aus)\s+(?:über\s+|rund\s+|ca\.\s*|mehr als\s+)?(\d{1,4}))"
    r"|(?:(?:über|rund|ca\.|mehr als|knapp)\s+(\d{1,4})\s*(?:Mitarbeiter|Mitarbeitende|Beschäftigte)))",
    re.I,
)


def text_of(html: str) -> str:
    tree = HTMLParser(html)
    for tag in tree.css("script,style,noscript"):
        tag.decompose()
    t = tree.body.text(separator="\n") if tree.body else tree.text(separator="\n")
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t)


def mobiles(text: str):
    out = []
    for m in PHONE_RE.finditer(text):
        raw = m.group(0).strip(" -/.–")
        try:
            num = phonenumbers.parse(raw, "DE")
        except Exception:
            continue
        if not phonenumbers.is_valid_number(num):
            continue
        if phonenumbers.number_type(num) != PhoneNumberType.MOBILE:
            continue
        e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        back = text[max(0, m.start() - 220) : m.start()]
        gf = GF_NEAR_RE.search(back)
        label = text[max(0, m.start() - 70) : m.start()].replace("\n", " | ").strip()
        ctx = text[max(0, m.start() - 300) : m.end() + 200].replace("\n", " | ")
        out.append(
            {
                "nummer": e164,
                "roh": raw,
                "label": label,
                "kontext": ctx,
                "gf_nah": bool(gf),
                "gf_wort": gf.group(0) if gf else None,
            }
        )
    return out


async def one(client, url):
    host = urlparse(url if "://" in url else "https://" + url).netloc or url
    base = f"https://{host}"
    res = {"host": host, "seiten": [], "mobil": [], "rollen": [], "mitarbeiter": [], "fehler": None}
    try:
        r = await client.get(base, follow_redirects=True)
        pages = {str(r.url): r.text}
        tree = HTMLParser(r.text)
        links = {}
        for a in tree.css("a[href]"):
            href = a.attributes.get("href") or ""
            lab = ((a.text() or "") + " " + href).lower()
            if any(w in lab for w in WANT):
                full = urljoin(str(r.url), href)
                if urlparse(full).netloc == urlparse(str(r.url)).netloc and full not in links:
                    links[full] = lab
        for full in list(links)[:6]:
            await asyncio.sleep(1.0)
            try:
                rr = await client.get(full, follow_redirects=True)
                if rr.status_code == 200:
                    pages[str(rr.url)] = rr.text
            except Exception:
                pass
        for u, html in pages.items():
            t = text_of(html)
            res["seiten"].append(u)
            for hit in mobiles(t):
                hit["url"] = u
                res["mobil"].append(hit)
            for rm in ROLE_RE.finditer(t):
                res["rollen"].append(
                    {"url": u, "text": t[rm.start() : rm.start() + 160].replace("\n", " | ")}
                )
            for em in EMP_RE.finditer(t):
                res["mitarbeiter"].append(
                    {"url": u, "text": t[max(0, em.start() - 120) : em.end() + 80].replace("\n", " | ")}
                )
    except Exception as e:
        res["fehler"] = f"{type(e).__name__}: {e}"
    agg = {}
    for h in res["mobil"]:
        a = agg.setdefault(h["nummer"], {"nummer": h["nummer"], "urls": set(), "labels": [], "kontexte": []})
        a["urls"].add(h["url"])
        if h["label"]:
            a["labels"].append(h["label"])
        a["kontexte"].append(h["kontext"])
        a["gf"] = a.get("gf") or h["gf_nah"]
        a["gf_wort"] = a.get("gf_wort") or h["gf_wort"]
    res["mobil_agg"] = [
        {
            "nummer": a["nummer"],
            "gf_nah": a.get("gf"),
            "gf_wort": a.get("gf_wort"),
            "n_seiten": len(a["urls"]),
            "footer_verdacht": len(a["urls"]) >= 3,
            "auf_impressum": any("impressum" in u.lower() for u in a["urls"]),
            "urls": sorted(a["urls"])[:4],
            "labels": a["labels"][:3],
            "kontext": a["kontexte"][0][:400],
        }
        for a in agg.values()
    ]
    res.pop("mobil", None)
    return res


async def main():
    with open(sys.argv[1]) as fh:
        urls = [line.strip() for line in fh if line.strip() and not line.startswith("#")]
    limits = httpx.Limits(max_connections=10)
    async with httpx.AsyncClient(
        headers={"User-Agent": UA}, timeout=25, limits=limits, verify="/root/.ccr/ca-bundle.crt"
    ) as client:
        sem = asyncio.Semaphore(6)

        async def guarded(u):
            async with sem:
                return await one(client, u)

        for res in await asyncio.gather(*[guarded(u) for u in urls]):
            print(json.dumps(res, ensure_ascii=False))


asyncio.run(main())
