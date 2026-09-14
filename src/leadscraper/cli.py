"""Kommandozeile: leadscraper run | search | enrich | demo | profiles."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from leadscraper import funding, pipeline
from leadscraper.excel import write_workbook
from leadscraper.models import Company, Lead, SearchSpec
from leadscraper.places import PlacesError
from leadscraper.settings import CONFIG_DIR, Settings, get_settings

app = typer.Typer(
    help="B2B-Leads (Entscheider + Handynummer) aus Google Places & Firmenwebsites → Excel",
    no_args_is_help=True,
)
console = Console()


def _load_profiles() -> dict:
    with open(CONFIG_DIR / "branchen.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["profiles"]


def _default_out(settings: Settings, stem: str) -> Path:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)[:60]
    return settings.output_dir / f"leads_{safe}_{datetime.now():%Y%m%d_%H%M}.xlsx"


def _spec_from_args(
    query: list[str],
    profile: str | None,
    city: str | None,
    radius_km: float,
    included_type: str | None,
    max_results: int,
    min_employees: int | None,
    max_employees: int | None,
    require_mobile: bool,
    exclude_chains: bool = True,
) -> SearchSpec:
    queries = list(query)
    if profile:
        profiles = _load_profiles()
        if profile not in profiles:
            raise typer.BadParameter(f"Unbekanntes Profil „{profile}“. Verfügbar: {', '.join(profiles)}")
        queries.extend(profiles[profile]["queries"])
    if not queries:
        profile = "makler"  # Standardfokus: Immobilienmakler (höchste Handy-Trefferquote)
        queries = list(_load_profiles()[profile]["queries"])
    return SearchSpec(
        queries=list(dict.fromkeys(queries)),
        city=city,
        radius_km=radius_km,
        included_type=included_type,
        max_results_per_query=max_results,
        min_employees=min_employees,
        max_employees=max_employees,
        require_mobile=require_mobile,
        exclude_chains=exclude_chains,
    )


def _print_summary(leads: list[Lead], limit: int = 25) -> None:
    table = Table(title=f"Top {min(limit, len(leads))} von {len(leads)} Leads", show_lines=False)
    for col in ("Score", "Firma", "Entscheider", "Handy", "MA", "Ort"):
        table.add_column(col)
    for ld in leads[:limit]:
        bc = ld.best_contact
        bm = ld.best_mobile
        size = ld.enrichment.size if ld.enrichment else None
        ma = "?" if not size or size.point_estimate is None else str(size.point_estimate)
        table.add_row(
            str(ld.score),
            ld.company.name[:40],
            f"{bc.name} ({bc.role_category})" if bc else "–",
            (bm.national + (f" ({bm.person})" if bm.person else "")) if bm else "–",
            ma,
            ld.company.city or "",
        )
    console.print(table)


@app.command()
def run(
    query: list[str] = typer.Option(
        [], "--query", "-q", help="Suchbegriff (mehrfach möglich), z. B. 'Immobilienmakler'"
    ),
    profile: str | None = typer.Option(
        None, "--profile", "-p", help="Profil aus config/branchen.yaml (Default ohne --query: makler)"
    ),
    city: str | None = typer.Option(
        None, "--city", "-c", help="Ort/Region, z. B. 'Köln' oder 'Landkreis Rosenheim'"
    ),
    radius_km: float = typer.Option(25.0, help="Suchradius um den Ort (max 50)"),
    included_type: str | None = typer.Option(None, help="Google-Place-Type, z. B. real_estate_agency"),
    max_results: int = typer.Option(60, help="Max. Treffer pro Suchbegriff (API-Limit 60)"),
    min_employees: int | None = typer.Option(5, help="Untergrenze Mitarbeiterzahl"),
    max_employees: int | None = typer.Option(50, help="Obergrenze Mitarbeiterzahl"),
    require_mobile: bool = typer.Option(False, help="Nur Leads mit gefundener Handynummer exportieren"),
    chain_filter: bool = typer.Option(
        True,
        "--chain-filter/--no-chain-filter",
        help="Ketten/Franchise/Portale (config/ausschluss.yaml) aussortieren",
    ),
    out: Path | None = typer.Option(None, "--out", "-o", help="Ziel-Excel (Default: output/leads_<…>.xlsx)"),
    json_out: Path | None = typer.Option(None, help="Zusätzlich Roh-Leads als JSON speichern"),
    verbose: bool = typer.Option(False, "-v", help="Debug-Logging"),
) -> None:
    """Kompletter Lauf: Google Places → Websites → Excel."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )
    settings = get_settings()
    spec = _spec_from_args(
        query,
        profile,
        city,
        radius_km,
        included_type,
        max_results,
        min_employees,
        max_employees,
        require_mobile,
        chain_filter,
    )
    where = f"{spec.city or 'ohne Ort'}, {spec.radius_km:.0f} km"
    console.print(f"[bold]Suche:[/] {', '.join(spec.queries)}  [dim]({where})[/]")
    try:
        leads = asyncio.run(pipeline.run(spec, settings, progress=lambda m: console.print(f"[dim]{m}[/]")))
    except (PlacesError, RuntimeError) as exc:
        raise typer.Exit(code=_err(str(exc))) from None
    target = out or _default_out(settings, profile or spec.queries[0])
    write_workbook(leads, spec, target, funding_rows=funding.funding_reference_rows())
    if json_out:
        json_out.write_text(
            json.dumps([ld.model_dump(mode="json") for ld in leads], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    _print_summary(leads)
    console.print(f"\n[green]✔[/] Excel gespeichert: [bold]{target}[/]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Suchbegriff"),
    city: str | None = typer.Option(None, "--city", "-c"),
    radius_km: float = typer.Option(25.0),
    included_type: str | None = typer.Option(None),
    max_results: int = typer.Option(20),
) -> None:
    """Nur Google-Places-Suche (ohne Website-Crawl) – zum Testen von Suchbegriffen."""
    settings = get_settings()
    if not settings.google_places_api_key:
        raise typer.Exit(code=_err("GOOGLE_PLACES_API_KEY fehlt (.env anlegen, siehe .env.example)"))
    from leadscraper.places import PlacesClient

    async def go() -> list[Company]:
        client = PlacesClient(settings.google_places_api_key)
        try:
            spec = SearchSpec(
                queries=[query],
                city=city,
                radius_km=radius_km,
                included_type=included_type,
                max_results_per_query=max_results,
            )
            return await pipeline.search_companies(
                spec, client, progress=lambda m: console.print(f"[dim]{m}[/]")
            )
        finally:
            await client.close()

    try:
        companies = asyncio.run(go())
    except PlacesError as exc:
        raise typer.Exit(code=_err(str(exc))) from None
    table = Table(title=f"{len(companies)} Firmen")
    for col in ("Firma", "Telefon", "Website", "PLZ", "Ort", "Bundesland", "Typ", "Bewertungen"):
        table.add_column(col)
    for c in companies:
        table.add_row(
            c.name[:40],
            c.phone or "",
            (c.domain or c.website or "")[:40],
            c.plz or "",
            c.city or "",
            c.bundesland or "",
            c.primary_type or "",
            str(c.user_rating_count or ""),
        )
    console.print(table)


@app.command()
def enrich(
    url: str = typer.Argument(..., help="Website einer Firma, z. B. https://www.beispiel-makler.de"),
    name: str = typer.Option("Test GmbH", help="Firmenname (nur für die Ausgabe)"),
    verbose: bool = typer.Option(False, "-v"),
) -> None:
    """Eine einzelne Website crawlen und Entscheider/Handynummern anzeigen (Debugging)."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING)
    settings = get_settings()
    from leadscraper.crawler import SiteCrawler

    async def go():
        crawler = SiteCrawler(settings)
        try:
            company = Company(place_id="manual", name=name, website=url)
            return await pipeline.enrich_company(company, crawler)
        finally:
            await crawler.close()

    enr = asyncio.run(go())
    console.print(f"[bold]{name}[/] – {len(enr.pages_crawled)} Seiten: {', '.join(enr.pages_crawled)}")
    console.print(
        f"Impressum: {enr.impressum_url}  Rechtsform: {enr.rechtsform}  Register: {enr.handelsregister}"
    )
    sz = enr.size
    console.print(f"Größe: {sz.point_estimate} ({sz.employees_min}-{sz.employees_max}, {sz.confidence})")
    for ev in sz.evidence[:2]:
        console.print(f"  [dim]{ev}[/]")
    table = Table(title="Personen")
    for col in ("Name", "Rolle", "Kategorie", "Handy", "E-Mail", "Quelle"):
        table.add_column(col)
    for p in enr.people:
        table.add_row(
            p.name,
            p.role or "",
            p.role_category,
            p.mobile.national if p.mobile else "",
            p.email or "",
            p.source_url or "",
        )
    console.print(table)
    table = Table(title="Telefonnummern")
    for col in ("Nummer", "Art", "Label", "Person", "Quelle", "URL"):
        table.add_column(col)
    for ph in enr.phones:
        table.add_row(ph.national, ph.kind, ph.label or "", ph.person or "", ph.source, ph.source_url or "")
    console.print(table)
    if enr.errors:
        console.print(f"[yellow]Hinweise:[/] {enr.errors}")


@app.command()
def demo(out: Path = typer.Option(Path("output/demo_leads.xlsx"), "--out", "-o")) -> None:
    """Excel mit Beispiel-Leads erzeugen (ohne API-Key, ohne Internet) – zeigt das Ausgabeformat."""
    from leadscraper.demo import demo_leads

    spec = SearchSpec(queries=["Immobilienmakler", "Elektrotechnik Betrieb"], city="Köln")
    leads = demo_leads(spec)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_workbook(leads, spec, out, funding_rows=funding.funding_reference_rows())
    _print_summary(leads)
    console.print(f"\n[green]✔[/] Demo-Excel: [bold]{out}[/]")


@app.command(name="enrich-list")
def enrich_list(
    input_file: Path = typer.Argument(
        ..., help="CSV/XLSX mit Spalten Firma, Website (optional Telefon, PLZ, Ort)"
    ),
    min_employees: int | None = typer.Option(5, help="Untergrenze Mitarbeiterzahl"),
    max_employees: int | None = typer.Option(50, help="Obergrenze Mitarbeiterzahl"),
    require_mobile: bool = typer.Option(False, help="Nur Leads mit gefundener Handynummer exportieren"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Ziel-Excel"),
    verbose: bool = typer.Option(False, "-v", help="Debug-Logging"),
) -> None:
    """Eigene Firmenliste (ohne Google) durch die Pipeline schicken: Websites → Entscheider/Handy → Excel."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING)
    from leadscraper.cache import Cache
    from leadscraper.dedupe import dedupe_companies
    from leadscraper.importer import read_company_list

    settings = get_settings()
    companies = dedupe_companies(read_company_list(input_file))
    if not companies:
        raise typer.Exit(code=_err(f"Keine Firmen in {input_file} gefunden (Spalten Firma/Website?)"))
    console.print(f"[bold]{len(companies)} Firmen[/] aus {input_file}")
    spec = SearchSpec(
        queries=[f"Liste: {input_file.name}"],
        min_employees=min_employees,
        max_employees=max_employees,
        require_mobile=require_mobile,
    )
    cache = Cache(settings.cache_path)
    try:
        leads = asyncio.run(
            pipeline.build_leads(
                companies, spec, settings, cache, progress=lambda m: console.print(f"[dim]{m}[/]")
            )
        )
    finally:
        cache.close()
    target = out or _default_out(settings, input_file.stem)
    write_workbook(leads, spec, target, funding_rows=funding.funding_reference_rows())
    _print_summary(leads)
    console.print(f"\n[green]✔[/] Excel gespeichert: [bold]{target}[/]")


@app.command()
def profiles() -> None:
    """Verfügbare Branchen-Profile anzeigen."""
    table = Table(title="Profile (config/branchen.yaml)")
    table.add_column("Profil")
    table.add_column("Beschreibung")
    table.add_column("Suchbegriffe")
    for key, prof in _load_profiles().items():
        table.add_row(key, prof.get("beschreibung", ""), ", ".join(prof["queries"]))
    console.print(table)


def _err(msg: str) -> int:
    console.print(f"[red]Fehler:[/] {msg}")
    return 1


if __name__ == "__main__":
    app()
