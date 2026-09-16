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

from leadscraper import excel, funding, pipeline
from leadscraper.excel import write_trello_csv, write_workbook
from leadscraper.models import Company, Lead, SearchSpec
from leadscraper.places import PlacesError, QuotaExceededError
from leadscraper.settings import CONFIG_DIR, Settings, get_settings

# Rückgabewert bei erschöpftem Google-Kontingent: die Slot-Skripte beenden sich dann, statt zu wiederholen.
_QUOTA_EXIT_CODE = 3

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
    premium: bool = False,
) -> SearchSpec:
    queries = list(query)
    profiles = _load_profiles()
    if not queries and not profile:
        profile = "makler"  # Standardfokus: Immobilienmakler (höchste Handy-Trefferquote)
    if profile:
        if profile not in profiles:
            raise typer.BadParameter(f"Unbekanntes Profil „{profile}“. Verfügbar: {', '.join(profiles)}")
        queries.extend(profiles[profile]["queries"])
        types = profiles[profile].get("included_types") or []
        if included_type is None and len(types) == 1:
            included_type = types[0]  # z. B. real_estate_agency – filtert Portale/Fremdtreffer
    cities = [c.strip() for c in city if c and c.strip()]
    return SearchSpec(
        queries=list(dict.fromkeys(queries)),
        city=cities[0] if cities else None,
        cities=cities[1:],
        radius_km=radius_km,
        included_type=included_type,
        max_results_per_query=max_results,
        min_employees=min_employees,
        max_employees=max_employees,
        require_mobile=require_mobile,
        exclude_chains=exclude_chains,
        premium=premium,
    )


def _print_summary(leads: list[Lead], limit: int = 25) -> None:
    table = Table(title=f"Top {min(limit, len(leads))} von {len(leads)} Leads", show_lines=False)
    for col in ("Score", "Premium", "Firma", "Entscheider", "Handy", "MA", "Ort"):
        table.add_column(col)
    for ld in leads[:limit]:
        bc = ld.best_contact
        bm = ld.best_mobile
        size = ld.enrichment.size if ld.enrichment else None
        ma = "?" if not size or size.point_estimate is None else str(size.point_estimate)
        table.add_row(
            str(ld.score),
            "★" if ld.premium else "",
            ld.display_name[:40],
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
    city: list[str] = typer.Option(
        [], "--city", "-c", help="Ort/Region (mehrfach möglich: -c Köln -c Bonn -c Leverkusen)"
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
    premium: bool = typer.Option(
        False,
        "--premium",
        help="Nur Diamanten: Entscheider mit namentlicher Handynummer und belegter Mitarbeiterzahl",
    ),
    deutschland: bool = typer.Option(
        False,
        "--deutschland",
        help="Ortsraster aus config/orte.yaml abarbeiten (unterbrechungssicher, wiederaufnehmbar)",
    ),
    bundesland: list[str] = typer.Option(
        [], "--bundesland", "-b", help="Nur diese Bundesländer (mit --deutschland)"
    ),
    state: Path = typer.Option(
        Path("output/deutschland.jsonl"),
        "--state",
        help="Ergebnisdatei für --deutschland; erneuter Aufruf setzt fort",
    ),
    queries_per_city: int = typer.Option(
        2,
        "--queries-per-city",
        help="Suchbegriffe je Ort bei --deutschland (jeder kostet eine Places-Anfrage)",
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
        premium,
    )
    if deutschland:
        if not query:
            # Kostenbremse: je Ort kostet jeder Suchbegriff eine Places-Anfrage.
            spec.queries = spec.queries[:queries_per_city]
        orte = pipeline.load_orte(bundeslaender=bundesland)
        target = out or state.with_suffix(".xlsx")
        console.print(
            f"[bold]Bundesweit:[/] {len(orte)} Orte, Suchbegriffe {', '.join(spec.queries)}, Stand in {state}"
        )

        def checkpoint(leads: list[Lead]) -> None:
            write_workbook(leads, spec, target, funding_rows=funding.funding_reference_rows())
            console.print(f"[dim]Zwischenstand gespeichert: {target} ({len(leads)} Leads)[/]")

        try:
            leads = asyncio.run(
                pipeline.run_cities(
                    spec,
                    settings,
                    orte,
                    state,
                    progress=lambda m: console.print(f"[dim]{m}[/]"),
                    checkpoint=checkpoint,
                )
            )
        except QuotaExceededError as exc:
            # Eigener Rückgabewert, damit die Slot-Skripte nicht sinnlos neu starten.
            console.print(f"[yellow]Kontingent erschöpft:[/] {exc}")
            console.print(f"[dim]Stand gesichert in {state} – Fortsetzen mit ./resume.sh[/]")
            raise typer.Exit(code=_QUOTA_EXIT_CODE) from None
        except (PlacesError, RuntimeError) as exc:
            raise typer.Exit(code=_err(str(exc))) from None
        write_workbook(leads, spec, target, funding_rows=funding.funding_reference_rows())
        _print_summary(leads)
        console.print(f"\n[green]✔[/] Excel gespeichert: [bold]{target}[/]  (Rohdaten: {state})")
        return
    where = f"{', '.join([spec.city, *spec.cities]) if spec.city else 'ohne Ort'}, {spec.radius_km:.0f} km"
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
        from leadscraper.budget import request_budget

        client = PlacesClient(settings.google_places_api_key, budget=request_budget(settings))
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
    premium: bool = typer.Option(False, "--premium", help="Nur Premium-Leads (siehe run --premium)"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Ziel-Excel"),
    jsonl_out: Path | None = typer.Option(
        None,
        "--jsonl-out",
        help="Zusätzlich als JSONL speichern – nötig für rebuild, refresh und den Export von Liste B",
    ),
    verbose: bool = typer.Option(False, "-v", help="Debug-Logging"),
) -> None:
    """Eigene Firmenliste (ohne Google) durch die Pipeline schicken: Websites → Entscheider/Handy → Excel.

    Mit `--jsonl-out` entsteht dieselbe Zustandsdatei wie bei einem bundesweiten Lauf. Nur dann lassen
    sich die Ergebnisse später ohne neuen Abruf erneut auswerten (`rebuild`, `refresh`) und als Liste B
    exportieren (`export --mit-belegschaft`).
    """
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
        premium=premium,
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
    if jsonl_out:
        jsonl_out.parent.mkdir(parents=True, exist_ok=True)
        jsonl_out.write_text("".join(ld.model_dump_json() + "\n" for ld in leads), encoding="utf-8")
    _print_summary(leads)
    console.print(f"\n[green]✔[/] Excel gespeichert: [bold]{target}[/]")
    if jsonl_out:
        console.print(f"[green]✔[/] Zustandsdatei: [bold]{jsonl_out}[/]  (für rebuild/refresh/Liste B)")


_NEAR_PREMIUM_MIN = 3


def is_near_premium(lead: Lead) -> bool:
    """Zweite Reihe: Entscheider mit Handynummer, aktiv, keine freien Vertreter – und drei oder vier
    belegte Köpfe. Innendienst, Buchhaltung und Azubis stehen selten auf der Website, diese Betriebe
    liegen also oft doch bei fünf und mehr. Im Telefonat mit einer Frage geklärt."""
    if not lead.premium_missing or lead.enrichment is None:
        return False
    offen = [m for m in lead.premium_missing if not m.startswith("nur ")]
    return not offen and lead.enrichment.staff.headcount >= _NEAR_PREMIUM_MIN


_OHNE_HANDY = "keine Handynummer beim Entscheider"
_LISTE_B_MIN = 5


def has_workforce(lead: Lead, mindestens: int = _LISTE_B_MIN, hoechstens: int | None = None) -> bool:
    """Liste B: Entscheider bekannt, Belegschaft belegt – aber nur die Zentrale auf der Website.

    Eine Handynummer im Impressum ist erlaubt, weil ein Festnetzanschluss Einzelunternehmer
    unverhältnismäßig belasten würde – sie ist deshalb ein Marker für sehr kleine Betriebe. Wer fünf
    Beschäftigte hat, hat meist eine Telefonanlage mit Durchwahlen und gerade kein Handy auf der Seite.
    Die beiden Pflichtkriterien arbeiten also gegeneinander: In den vorhandenen Daten stehen 286
    Betrieben mit namentlicher Handynummer 1.704 gegenüber, die nur über die Zentrale erreichbar sind.
    Diese Liste ist das Gegenstück zu Premium – ein Gespräch mehr am Empfang, dafür siebenmal so viele
    Betriebe, die die Förderbedingung tatsächlich erfüllen.
    """
    if lead.enrichment is None:
        return False
    kopfzahl = lead.enrichment.staff.headcount
    if kopfzahl < mindestens:
        return False
    # Die Obergrenze ist keine Geschmacksfrage, sondern die Förderschwelle: Unter 50 Beschäftigten
    # trägt die Agentur 100 % der Lehrgangskosten, ab 50 nur noch die Hälfte.
    if hoechstens is not None and kopfzahl > hoechstens:
        return False
    # „nur 7 Beschäftigte belegt“ stammt aus der Premium-Regel und wird durch `mindestens` ersetzt.
    # Der Hinweis auf eine zu große Belegschaft bleibt dagegen ein Ausschluss.
    offen = [m for m in lead.premium_missing or [] if m != _OHNE_HANDY and not m.startswith("nur ")]
    return not offen


def _load_leads(paths: list[Path], *, exclude_chains: bool = True) -> list[Lead]:
    """Leads aus einer oder mehreren Dateien; Duplikate (place_id/Domain, z. B. Grenzregionen) einmal.

    Die Ausschlussliste wird beim Export erneut angewandt: Sie wächst im Lauf der Recherche, und Treffer
    aus früheren Läufen sollen nicht deshalb in der Liste bleiben, weil die Kette damals noch fehlte.
    """
    leads: list[Lead] = []
    for path in paths:
        if path.suffix == ".json":
            leads.extend(Lead.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8")))
        else:
            leads.extend(pipeline.read_leads_jsonl(path))
    leads.sort(key=lambda ld: (-ld.score, ld.display_name.lower()))
    seen: set[str] = set()
    unique: list[Lead] = []
    for ld in leads:
        keys = [ld.company.place_id] + ([ld.company.domain] if ld.company.domain else [])
        if any(k in seen for k in keys):
            continue
        seen.update(keys)
        unique.append(ld)
    if exclude_chains:
        from leadscraper.exclusions import filter_chains

        by_place = {ld.company.place_id: ld for ld in unique}
        keep, dropped = filter_chains([ld.company for ld in unique])
        if dropped:
            console.print(f"[dim]{len(dropped)} Ketten/Franchise/Portale aussortiert[/]")
        unique = [by_place[c.place_id] for c in keep]
    return unique


@app.command()
def export(
    jsonl: list[Path] = typer.Argument(
        ..., help="JSONL-Datei(en) aus --deutschland (oder --json-out); mehrere werden zusammengeführt"
    ),
    out: Path | None = typer.Option(None, "--out", "-o", help="Ziel-Excel"),
    premium: bool = typer.Option(False, "--premium", help="Nur Premium-Leads exportieren"),
    near_premium: bool = typer.Option(
        False,
        "--near-premium",
        help="Premium plus Fast-Premium: Entscheider mit Handy, nur Mitarbeiterzahl/Beschäftigte unbelegt",
    ),
    mit_belegschaft: bool = typer.Option(
        False,
        "--mit-belegschaft",
        help="Liste B: Entscheider und belegte Beschäftigte, Handynummer nicht nötig",
    ),
    min_belegschaft: int = typer.Option(
        _LISTE_B_MIN,
        "--min-belegschaft",
        help="Untergrenze belegter Beschäftigter für --mit-belegschaft (Förderung: unter 50 voll)",
    ),
    max_belegschaft: int | None = typer.Option(
        None,
        "--max-belegschaft",
        help="Obergrenze belegter Beschäftigter (ab 50 halbiert sich die Förderung)",
    ),
    min_score: int = typer.Option(0, help="Mindest-Score"),
    nach_belegschaft: bool = typer.Option(
        False,
        "--nach-belegschaft",
        help="Größte Belegschaft zuerst statt bester Score – wer 40 Köpfe hat, ist mehr wert als wer 6 hat",
    ),
    nur_ein_standort: bool = typer.Option(
        False,
        "--nur-ein-standort",
        help="Betriebe mit Hinweis auf mehrere Standorte weglassen (dort zählt das ganze Unternehmen)",
    ),
) -> None:
    """Excel aus gespeicherten Leads bauen (z. B. nur Premium, ohne neuen Crawl)."""
    leads = _load_leads(jsonl)
    if mit_belegschaft:
        leads = [ld for ld in leads if has_workforce(ld, min_belegschaft, max_belegschaft)]
    elif near_premium:
        leads = [ld for ld in leads if ld.premium or is_near_premium(ld)]
    elif premium:
        leads = [ld for ld in leads if ld.premium]
    leads = [ld for ld in leads if ld.score >= min_score]
    if nur_ein_standort:
        # § 82 Abs. 6 Satz 3 Nr. 2 SGB III: Bei mehreren Standorten zählt das ganze Unternehmen,
        # der Fördersatz fällt dann meist von 100 auf 50 Prozent der Lehrgangskosten.
        leads = [ld for ld in leads if not (ld.enrichment and ld.enrichment.mehrstandort)]
    if nach_belegschaft:
        leads.sort(
            key=lambda ld: (
                -(ld.enrichment.staff.headcount if ld.enrichment else 0),
                -ld.score,
                ld.display_name.lower(),
            )
        )
        excel.set_sortierung(excel.SORTIERUNG_UEBERNEHMEN)
    first = jsonl[0]
    if mit_belegschaft:
        spanne = f"_ab_{min_belegschaft}" + (f"_bis_{max_belegschaft}" if max_belegschaft else "")
        suffix = spanne if min_belegschaft != _LISTE_B_MIN or max_belegschaft else "_mit_belegschaft"
    else:
        suffix = "_near_premium" if near_premium else ("_premium" if premium else "")
    target = out or first.with_name(first.stem + suffix + ".xlsx")
    names = ", ".join(p.name for p in jsonl)
    spec = SearchSpec(queries=[f"Export: {names}"], premium=premium or near_premium or mit_belegschaft)
    write_workbook(leads, spec, target, funding_rows=funding.funding_reference_rows())
    _print_summary(leads)
    n_prem = sum(1 for ld in leads if ld.premium)
    console.print(f"\n[green]✔[/] {len(leads)} Leads (davon {n_prem} Premium) → [bold]{target}[/]")


@app.command()
def refresh(
    jsonl: list[Path] = typer.Argument(..., help="JSONL-Datei(en) aus --deutschland"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Ziel-JSONL (Default: Datei ersetzen)"),
    min_employees: int | None = typer.Option(5, help="Untergrenze Mitarbeiterzahl"),
    max_employees: int | None = typer.Option(50, help="Obergrenze Mitarbeiterzahl"),
) -> None:
    """Gespeicherte Leads mit den aktuellen Regeln neu bewerten – ohne Crawl, ohne Google-Anfragen.

    Nach Verbesserungen an Größen-Indizien, Beschäftigtenstatus oder Handy-Zuordnung wirken diese damit
    auch auf bereits abgearbeitete Orte. Ein laufender Lauf darf dieselbe Datei nicht gleichzeitig
    beschreiben – vorher beenden oder mit --out in eine neue Datei schreiben.
    """
    spec = SearchSpec(queries=["refresh"], min_employees=min_employees, max_employees=max_employees)
    cfg = funding.load_funding_config()
    for path in jsonl:
        leads = pipeline.read_leads_jsonl(path)
        before = sum(1 for ld in leads if ld.premium)
        refreshed = [pipeline.refresh_lead(ld, spec, cfg) for ld in leads]
        target = out or path
        target.write_text("".join(ld.model_dump_json() + "\n" for ld in refreshed), encoding="utf-8")
        after = sum(1 for ld in refreshed if ld.premium)
        console.print(
            f"[green]✔[/] {path.name}: {len(refreshed)} Leads neu bewertet, "
            f"Premium {before} → [bold]{after}[/] → {target}"
        )


@app.command()
def rebuild(
    jsonl: list[Path] = typer.Argument(..., help="JSONL-Datei(en) aus --deutschland"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Ziel-JSONL (Default: Datei ersetzen)"),
    min_employees: int | None = typer.Option(5, help="Untergrenze Mitarbeiterzahl"),
    max_employees: int | None = typer.Option(50, help="Obergrenze Mitarbeiterzahl"),
    verbose: bool = typer.Option(False, "-v", help="Debug-Logging"),
) -> None:
    """Gespeicherte Firmen mit den aktuellen Extraktoren neu auswerten – ohne Google-Anfragen.

    Anders als `refresh` werden die Websites erneut ausgelesen (aus dem HTML-Cache, sonst frisch geladen),
    sodass auch Verbesserungen an Impressum-, Personen- und Telefon-Erkennung greifen. Kostet keine
    Places-Anfragen, weil die Firmenliste schon vorliegt. Ein laufender Lauf darf dieselbe Datei nicht
    gleichzeitig beschreiben.
    """
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING)
    from leadscraper.cache import Cache

    settings = get_settings()
    spec = SearchSpec(queries=["rebuild"], min_employees=min_employees, max_employees=max_employees)
    cfg = funding.load_funding_config()
    for path in jsonl:
        leads = pipeline.read_leads_jsonl(path)
        before = sum(1 for ld in leads if ld.premium)
        companies = [ld.company for ld in leads]
        cache = Cache(settings.cache_path)
        try:
            enrichments = asyncio.run(pipeline.enrich_all(companies, settings, cache, progress=None))
        finally:
            cache.close()
        rebuilt = [
            pipeline.finalize_lead(c, e, spec, cfg) for c, e in zip(companies, enrichments, strict=True)
        ]
        target = out or path
        target.write_text("".join(ld.model_dump_json() + "\n" for ld in rebuilt), encoding="utf-8")
        after = sum(1 for ld in rebuilt if ld.premium)
        console.print(
            f"[green]✔[/] {path.name}: {len(rebuilt)} Firmen neu ausgewertet, "
            f"Premium {before} → [bold]{after}[/] → {target}"
        )


@app.command()
def trello(
    jsonl: list[Path] = typer.Argument(..., help="JSONL-Datei(en) aus --deutschland"),
    out: Path = typer.Option(Path("output/trello.csv"), "--out", "-o", help="Ziel-CSV für Trello-Import"),
    premium: bool = typer.Option(True, "--premium/--alle", help="Nur Premium-Leads (Default: ja)"),
    mit_belegschaft: bool = typer.Option(
        False,
        "--mit-belegschaft",
        help="Liste B: Entscheider und belegte Beschäftigte, Handynummer nicht nötig",
    ),
    min_belegschaft: int = typer.Option(
        _LISTE_B_MIN, "--min-belegschaft", help="Untergrenze belegter Beschäftigter für --mit-belegschaft"
    ),
    max_belegschaft: int | None = typer.Option(
        None,
        "--max-belegschaft",
        help="Obergrenze belegter Beschäftigter (ab 50 halbiert sich die Förderung)",
    ),
    limit: int | None = typer.Option(None, help="Höchstens so viele Karten (beste Scores zuerst)"),
    nach_belegschaft: bool = typer.Option(
        False, "--nach-belegschaft", help="Größte Belegschaft zuerst statt bester Score"
    ),
) -> None:
    """CSV für den Trello-Import: Spalte 1 = Unternehmensname (Kartenname), Spalte 2 = alle Infos."""
    leads = _load_leads(jsonl)
    if mit_belegschaft:
        leads = [ld for ld in leads if has_workforce(ld, min_belegschaft, max_belegschaft)]
    elif premium:
        leads = [ld for ld in leads if ld.premium]
    if nach_belegschaft:
        leads.sort(
            key=lambda ld: (
                -(ld.enrichment.staff.headcount if ld.enrichment else 0),
                -ld.score,
                ld.display_name.lower(),
            )
        )
    if limit:
        leads = leads[:limit]
    out.parent.mkdir(parents=True, exist_ok=True)
    write_trello_csv(leads, out)
    console.print(f"[green]✔[/] {len(leads)} Karten → [bold]{out}[/]  (Trello: Import → CSV)")


@app.command()
def osm(
    profile: str = typer.Option(
        ..., "--profile", "-p", help="Profil aus config/branchen.yaml mit osm-Filtern"
    ),
    out: Path | None = typer.Option(None, "--out", "-o", help="Ziel-CSV für enrich-list"),
    gebiet: str = typer.Option("DE", help="ISO-Ländercode des Suchgebiets"),
    alle: bool = typer.Option(
        False, "--alle", help="Auch Betriebe ohne Website aufnehmen (für die Pipeline meist wertlos)"
    ),
    verbose: bool = typer.Option(False, "-v", help="Debug-Logging"),
) -> None:
    """Firmenliste aus OpenStreetMap holen – ohne Google, ohne Kosten.

    Schreibt eine CSV, die `leadscraper enrich-list` direkt liest. Die Abdeckung ist branchenabhängig
    und kleiner als die amtliche Grundgesamtheit; die Meldung nennt deshalb Objekte, Namen und Websites.
    """
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING)
    from leadscraper.exclusions import filter_chains
    from leadscraper.osm import fetch_branch, write_csv

    profile_config = _load_profiles()
    if profile not in profile_config:
        raise typer.BadParameter(f"Unbekanntes Profil „{profile}“. Verfügbar: {', '.join(profile_config)}")
    filter_ = profile_config[profile].get("osm") or []
    if not filter_:
        raise typer.Exit(
            code=_err(
                f"Profil „{profile}“ hat keine osm-Filter. In config/branchen.yaml ergänzen, z. B.\n"
                '  osm:\n      - \'["office"="tax_advisor"]\''
            )
        )
    console.print(f"[bold]{profile}[/]: {len(filter_)} OpenStreetMap-Abfragen für {gebiet}")
    from leadscraper.osm import OverpassError

    try:
        ergebnis = fetch_branch(
            filter_,
            gebiet=gebiet,
            nur_mit_website=not alle,
            nicht_name=profile_config[profile].get("osm_nicht_name"),
        )
    except OverpassError as exc:
        raise typer.Exit(code=_err(str(exc))) from exc
    behalten, verworfen = filter_chains(ergebnis.firmen)
    if verworfen:
        console.print(f"[dim]{len(verworfen)} Ketten/Franchise/Portale aussortiert[/]")
    ziel = out or (get_settings().output_dir / f"osm_{profile}.csv")
    write_csv(behalten, ziel)
    console.print(f"{ergebnis.bericht}")
    console.print(f"\n[green]✔[/] {len(behalten)} Firmen → [bold]{ziel}[/]")
    console.print(f"[dim]Weiter mit: leadscraper enrich-list {ziel} --premium[/]")
    console.print("[dim]Daten © OpenStreetMap-Mitwirkende, ODbL.[/]")


@app.command()
def kosten(
    zuruecksetzen: bool = typer.Option(False, "--zuruecksetzen", help="Zähler auf null setzen"),
) -> None:
    """Wie viele bezahlte Google-Anfragen wurden in diesem Monat gesendet?"""
    from leadscraper.budget import request_budget

    budget = request_budget(get_settings())
    if zuruecksetzen:
        budget.zuruecksetzen()
        console.print("[yellow]Zähler zurückgesetzt.[/]")
    verbraucht, rest = budget.verbraucht(), budget.rest()
    farbe = "green" if rest > budget.limit * 0.2 else "red"
    console.print(f"[{farbe}]{budget.bericht()}[/]")
    if verbraucht == 0:
        console.print("[dim]Keine bezahlte Anfrage in diesem Monat – alles kam aus dem Zwischenspeicher.[/]")


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
