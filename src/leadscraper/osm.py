"""Firmenlisten aus OpenStreetMap holen – der Weg ohne Google.

Die Google-Places-Suche kostet Geld und ist an ein Konto gebunden. OpenStreetMap kennt viele derselben
Betriebe, und die Overpass-API liefert sie mit Name, Adresse und – entscheidend – der Website-Adresse.
Das Ergebnis wird als CSV geschrieben, die `leadscraper enrich-list` direkt frisst; die Pipeline
dahinter (Website lesen, Entscheider, Handynummer, Belegschaft) ist dieselbe.

Die Abdeckung ist branchenabhängig und immer kleiner als die amtliche Grundgesamtheit: OSM ist eine
Freiwilligenkarte. Für Steuerkanzleien lagen bei der ersten Messung 3.933 Objekte vor, davon 2.074 mit
Website. Deshalb meldet `fetch_branch` beide Zahlen, damit die Abdeckung sichtbar bleibt.

Nutzungsbedingungen: Die Overpass-Server sind gespendete Rechenzeit. Deshalb wird eine Abfrage je Tag
gestellt (nicht alle auf einmal), zwischen den Abfragen gewartet und bei Überlastung (429, 504) mit
wachsendem Abstand wiederholt. Die Daten stehen unter der ODbL; wer sie weitergibt, muss
„© OpenStreetMap-Mitwirkende“ nennen.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

from leadscraper.dedupe import normalize_domain
from leadscraper.geo import bundesland_from_plz
from leadscraper.models import Company

log = logging.getLogger(__name__)

# Gespiegelte Overpass-Server; bei Überlastung wird der nächste genommen.
SPIEGEL: tuple[str, ...] = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
_UEBERLASTET = frozenset({429, 502, 503, 504})
# Overpass ist häufig belegt. Lieber geduldig warten als aufgeben: Die Abfrage ist kostenlos, ein
# Fehlschlag kostet dagegen den ganzen Branchenabruf.
_WARTEN = (5.0, 15.0, 30.0, 60.0, 90.0)
_RUNDEN = 3
_ABFRAGE_TIMEOUT = 180
_PAUSE_ZWISCHEN_TAGS = 3.0


class OverpassError(RuntimeError):
    """Overpass hat nicht geantwortet oder nur Fehler geliefert."""


def bauen(tag_filter: str, *, gebiet: str = "DE", timeout: int = _ABFRAGE_TIMEOUT) -> str:
    """Overpass-QL für einen Tag-Filter wie `["office"="tax_advisor"]` im ganzen Land."""
    return (
        f"[out:json][timeout:{timeout}];"
        f'area["ISO3166-1"="{gebiet}"][admin_level=2]->.gebiet;'
        f"(nwr{tag_filter}(area.gebiet););"
        f"out tags center;"
    )


def _retry_after(antwort: httpx.Response) -> float | None:
    """Wartezeit, die der Server selbst nennt – die schlägt jede eigene Schätzung."""
    wert = (antwort.headers.get("retry-after") or "").strip()
    if wert.isdigit():
        return min(float(wert), 300.0)
    return None


def _abrufen(
    abfrage: str,
    *,
    client: httpx.Client,
    warten: tuple[float, ...] | None = None,
    runden: int | None = None,
) -> dict:
    """Eine Overpass-Abfrage über alle Spiegel, mehrere Runden lang, mit wachsender Wartezeit.

    Die Vorgaben werden hier und nicht in der Signatur aufgelöst: Vorgabewerte einer Signatur werden
    beim Import festgelegt und ließen sich in Tests nicht mehr ersetzen.
    """
    warten = warten if warten is not None else _WARTEN
    runden = runden if runden is not None else _RUNDEN
    letzter_fehler = "kein Versuch"
    versuche = 0
    gesamt = runden * len(SPIEGEL)
    for _runde in range(runden):
        for server in SPIEGEL:
            versuche += 1
            pause: float | None = None
            try:
                antwort = client.post(server, data={"data": abfrage}, timeout=timeout_fuer(abfrage))
            except httpx.HTTPError as exc:
                letzter_fehler = f"{type(exc).__name__}: {str(exc)[:120]}"
                log.debug("Overpass %s: %s", server, letzter_fehler)
            else:
                if antwort.status_code == 200:
                    try:
                        return antwort.json()
                    except ValueError as exc:  # Overpass schickt bei Überlast auch mal HTML
                        letzter_fehler = f"unlesbare Antwort: {exc}"
                else:
                    letzter_fehler = f"HTTP {antwort.status_code}"
                    if antwort.status_code not in _UEBERLASTET:
                        raise OverpassError(f"Overpass {server}: {letzter_fehler}")
                    pause = _retry_after(antwort)
            if versuche < gesamt:
                time.sleep(pause if pause is not None else warten[min(versuche - 1, len(warten) - 1)])
    raise OverpassError(
        f"Overpass antwortet auch nach {versuche} Versuchen auf {len(SPIEGEL)} Servern nicht "
        f"(zuletzt: {letzter_fehler}). Die Server sind gespendete Rechenzeit und zeitweise belegt – "
        f"später erneut versuchen, der Abruf kostet nichts."
    )


def timeout_fuer(abfrage: str) -> float:
    """HTTP-Timeout etwas über dem Overpass-Timeout, sonst bricht die Leitung vor der Antwort ab."""
    return float(_ABFRAGE_TIMEOUT + 60) if f"timeout:{_ABFRAGE_TIMEOUT}" in abfrage else 120.0


def _website(tags: dict[str, str]) -> str | None:
    for schluessel in ("website", "contact:website", "url", "operator:website"):
        wert = (tags.get(schluessel) or "").strip()
        if not wert or " " in wert:
            continue
        if wert.startswith("//"):
            wert = "https:" + wert
        elif "://" not in wert:
            wert = "https://" + wert
        if "." in wert.split("//", 1)[-1]:
            return wert
    return None


def _telefon(tags: dict[str, str]) -> str | None:
    for schluessel in ("phone", "contact:phone", "contact:mobile"):
        wert = (tags.get(schluessel) or "").strip()
        if wert:
            return wert.split(";")[0].strip()
    return None


def _adresse(tags: dict[str, str]) -> tuple[str | None, str | None, str | None]:
    strasse = (tags.get("addr:street") or "").strip() or None
    if strasse and (nr := (tags.get("addr:housenumber") or "").strip()):
        strasse = f"{strasse} {nr}"
    return (
        strasse,
        (tags.get("addr:postcode") or "").strip() or None,
        (tags.get("addr:city") or "").strip() or None,
    )


@dataclass
class OsmErgebnis:
    """Was ein Abruf gebracht hat – die Abdeckung soll sichtbar bleiben."""

    firmen: list[Company] = field(default_factory=list)
    objekte: int = 0
    mit_name: int = 0
    mit_website: int = 0
    abfragen: list[str] = field(default_factory=list)

    @property
    def bericht(self) -> str:
        return (
            f"{self.objekte} Objekte, davon {self.mit_name} mit Name und {self.mit_website} mit Website "
            f"→ {len(self.firmen)} Firmen (ohne Dubletten)"
        )


def fetch_branch(
    tag_filter: list[str],
    *,
    gebiet: str = "DE",
    nur_mit_website: bool = True,
    client: httpx.Client | None = None,
    pause: float = _PAUSE_ZWISCHEN_TAGS,
) -> OsmErgebnis:
    """Alle Betriebe einer Branche holen: je Tag eine Abfrage, Ergebnisse zusammengeführt.

    Dubletten entstehen reichlich (derselbe Betrieb als Punkt und als Gebäudeumriss, oder unter zwei
    Tags). Zusammengeführt wird über die Domain, sonst über Name und Ort.
    """
    eigener_client = client is None
    client = client or httpx.Client(headers={"User-Agent": "leadscraper/1.0 (Recherche)"})
    ergebnis = OsmErgebnis()
    gesehen: set[str] = set()
    try:
        for i, filt in enumerate(tag_filter):
            if i and pause:
                time.sleep(pause)
            abfrage = bauen(filt, gebiet=gebiet)
            ergebnis.abfragen.append(abfrage)
            daten = _abrufen(abfrage, client=client)
            for element in daten.get("elements", []):
                tags = element.get("tags") or {}
                if not isinstance(tags, dict):
                    continue
                ergebnis.objekte += 1
                name = (tags.get("name") or tags.get("operator") or "").strip()
                if name:
                    ergebnis.mit_name += 1
                website = _website(tags)
                if website:
                    ergebnis.mit_website += 1
                if not name or (nur_mit_website and not website):
                    continue
                strasse, plz, ort = _adresse(tags)
                domain = normalize_domain(website)
                schluessel = domain or f"{name.casefold()}|{(ort or '').casefold()}"
                if schluessel in gesehen:
                    continue
                gesehen.add(schluessel)
                ergebnis.firmen.append(
                    Company(
                        place_id=f"osm-{element.get('type', 'n')}-{element.get('id')}",
                        name=name,
                        website=website,
                        domain=domain,
                        phone=_telefon(tags),
                        street=strasse,
                        plz=plz,
                        city=ort,
                        bundesland=bundesland_from_plz(plz),
                        primary_type=filt,
                        query=f"OSM {filt}",
                    )
                )
    finally:
        if eigener_client:
            client.close()
    return ergebnis


CSV_SPALTEN = ("Firma", "Website", "Telefon", "Straße", "PLZ", "Ort", "Bundesland", "Quelle")


def write_csv(firmen: list[Company], path) -> None:
    """CSV in genau der Form, die `leadscraper enrich-list` liest (Semikolon, UTF-8 mit BOM für Excel)."""
    import csv
    from pathlib import Path

    ziel = Path(path)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with open(ziel, "w", encoding="utf-8-sig", newline="") as fh:
        schreiber = csv.writer(fh, delimiter=";")
        schreiber.writerow(CSV_SPALTEN)
        for firma in firmen:
            schreiber.writerow(
                [
                    firma.name,
                    firma.website or "",
                    firma.phone or "",
                    firma.street or "",
                    firma.plz or "",
                    firma.city or "",
                    firma.bundesland or "",
                    firma.query or "OpenStreetMap",
                ]
            )
