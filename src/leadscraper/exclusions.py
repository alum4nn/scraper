"""Ketten-/Franchise-/Portal-Filter aus config/ausschluss.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from leadscraper.dedupe import normalize_domain
from leadscraper.models import Company
from leadscraper.settings import CONFIG_DIR


@lru_cache(maxsize=4)
def _load(path: str) -> tuple[frozenset[str], tuple[str, ...]]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    domains = frozenset(normalize_domain(d) or d.lower() for d in data.get("domains", []))
    names = tuple(n.lower() for n in data.get("names", []) if n)
    return domains, names


def load_exclusions(path: Path | None = None) -> tuple[frozenset[str], tuple[str, ...]]:
    return _load(str(path or CONFIG_DIR / "ausschluss.yaml"))


def exclusion_reason(company: Company, path: Path | None = None) -> str | None:
    """Grund, warum die Firma als Kette/Franchise/Portal gilt – oder None."""
    domains, names = load_exclusions(path)
    dom = normalize_domain(company.website or company.domain)
    if dom and dom in domains:
        return f"Kette/Franchise (Domain {dom})"
    lowered = company.name.lower()
    for needle in names:
        if needle in lowered:
            return f"Kette/Franchise (Name „{needle.strip()}“)"
    return None


def filter_chains(
    companies: list[Company], path: Path | None = None
) -> tuple[list[Company], list[tuple[Company, str]]]:
    kept: list[Company] = []
    dropped: list[tuple[Company, str]] = []
    for c in companies:
        reason = exclusion_reason(c, path)
        (dropped.append((c, reason)) if reason else kept.append(c))
    return kept, dropped
