"""Förderlogik (§ 82 SGB III + Landesprogramme) aus config/foerderung.yaml – inkl. Pitch fürs Telefonat."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from leadscraper.models import FundingAssessment, SizeEstimate
from leadscraper.settings import CONFIG_DIR


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_funding_config(path: Path | None = None) -> dict[str, Any]:
    return _load(str(path or CONFIG_DIR / "foerderung.yaml"))


def _bands(config: dict[str, Any]) -> list[dict[str, Any]]:
    return config["bund"]["groessenklassen"]


def size_band_for(employees: int | None, config: dict[str, Any] | None = None) -> str | None:
    if employees is None or employees < 0:
        return None
    cfg = config or load_funding_config()
    for band in _bands(cfg):
        lo = band.get("min") or 0
        hi = band.get("max")
        if employees >= lo and (hi is None or employees <= hi):
            return band["band"]
    return None


def _band_entry(band: str | None, cfg: dict[str, Any]) -> dict[str, Any] | None:
    return next((b for b in _bands(cfg) if b["band"] == band), None) if band else None


def _estimate_for_band(size: SizeEstimate) -> int | None:
    """Konservativ: bei Unsicherheit die größere Zahl nehmen, damit die Förderquote nicht überschätzt wird."""
    if size.confidence == "high" and size.point_estimate is not None:
        return size.point_estimate
    if size.employees_max is not None:
        return size.employees_max
    return size.point_estimate


def assess(
    size: SizeEstimate, bundesland: str | None, *, config: dict[str, Any] | None = None
) -> FundingAssessment:
    cfg = config or load_funding_config()
    result = FundingAssessment(bonus_hinweise=list(cfg["bund"].get("bonus", [])))

    land = (cfg.get("laender") or {}).get(bundesland or "", None)
    if land:
        result.landesprogramm = land.get("programm")
        result.landesprogramm_url = land.get("url")
        result.landesprogramm_hinweis = land.get("hinweis")

    est = _estimate_for_band(size)
    band = size_band_for(est, cfg)
    entry = _band_entry(band, cfg)
    if entry is None:
        result.pitch = (
            "Die Agentur für Arbeit fördert Weiterbildung Beschäftigter nach § 82 SGB III – bei kleinen "
            "Betrieben bis zu 100 % der Lehrgangskosten. Die genaue Quote hängt von der Beschäftigtenzahl ab."
        )
        if result.landesprogramm:
            result.pitch += f" Zusätzlich in {bundesland}: {result.landesprogramm}."
        return result

    result.size_band = band
    result.lehrgangskosten_pct = int(entry["lehrgangskosten_pct"])
    result.arbeitsentgeltzuschuss_pct = int(entry["arbeitsentgeltzuschuss_pct"])

    if band == "<10":
        groesse = "Bei unter 10 Beschäftigten"
    elif entry.get("max") is None:
        groesse = f"Ab {entry['min']} Beschäftigten"
    else:
        groesse = f"Bei {entry['min']} bis {entry['max']} Beschäftigten"
    pitch = (
        f"{groesse} übernimmt die Agentur für Arbeit bis zu {result.lehrgangskosten_pct} % der "
        f"Lehrgangskosten und bis zu {result.arbeitsentgeltzuschuss_pct} % des Arbeitsentgelts "
        f"während der Weiterbildung "
        f"({cfg['bund'].get('gesetz', '§ 82 SGB III')})."
    )
    if result.landesprogramm:
        detail = f" ({result.landesprogramm_hinweis})" if result.landesprogramm_hinweis else ""
        pitch += f" In {bundesland} zusätzlich: {result.landesprogramm}{detail}."
    if size.confidence in ("low", "none"):
        pitch += " Beschäftigtenzahl im Gespräch verifizieren."
    result.pitch = pitch
    return result


def _row(
    kategorie: str, band: str = "", lk: Any = "", aez: Any = "", hinweis: str = "", url: str = ""
) -> dict[str, Any]:
    return {
        "Kategorie": kategorie,
        "Band / Bundesland": band,
        "Lehrgangskosten %": lk,
        "Arbeitsentgeltzuschuss %": aez,
        "Hinweis": hinweis,
        "URL": url,
    }


def funding_reference_rows(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = config or load_funding_config()
    ba_url = "https://www.arbeitsagentur.de/unternehmen/finanziell/foerderung-von-weiterbildung"
    rows = [
        _row(
            "Bund (§ 82 SGB III)",
            b["band"],
            b["lehrgangskosten_pct"],
            b["arbeitsentgeltzuschuss_pct"],
            url=ba_url,
        )
        for b in _bands(cfg)
    ]
    rows += [_row("Bonus", hinweis=b) for b in cfg["bund"].get("bonus", [])]
    rows += [_row("Voraussetzung", hinweis=v) for v in cfg["bund"].get("voraussetzungen", [])]
    for land, info in (cfg.get("laender") or {}).items():
        hinweis = f"{info.get('programm', '')}: {info.get('hinweis', '')}".strip(": ")
        rows.append(_row("Landesprogramm", land, hinweis=hinweis, url=info.get("url", "")))
    rows.append(_row("Stand", str(cfg.get("stand", "")), hinweis="Werte vor Kundengesprächen prüfen"))
    return rows
