from pathlib import Path

from typer.testing import CliRunner

from leadscraper.cli import app

runner = CliRunner()


def test_profiles_lists_makler():
    result = runner.invoke(app, ["profiles"])
    assert result.exit_code == 0
    assert "makler" in result.stdout and "Immobilienmakler" in result.stdout


def test_demo_writes_excel(tmp_path: Path):
    out = tmp_path / "demo.xlsx"
    result = runner.invoke(app, ["demo", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.exists() and out.stat().st_size > 5000
    assert "Rheinblick" in result.stdout


def test_run_without_api_key_fails_with_hint(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # keine .env
    result = runner.invoke(app, ["run", "-q", "Immobilienmakler", "-c", "Köln"])
    assert result.exit_code != 0
    assert "GOOGLE_PLACES_API_KEY" in (result.stdout + str(result.exception))


def test_run_defaults_to_makler_profile(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["run", "-c", "Köln"])
    assert "Immobilienmakler" in result.stdout  # Makler-Profil als Default
    assert result.exit_code != 0  # scheitert erst am fehlenden API-Key


def test_enrich_list_reads_csv_and_writes_excel(fixture_web, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LEADSCRAPER_REQUEST_DELAY_SECONDS", "0")
    monkeypatch.setenv("LEADSCRAPER_CACHE_PATH", str(tmp_path / "c.sqlite"))
    csv = tmp_path / "firmen.csv"
    csv.write_text(
        "Firma;Website;PLZ\nRheinblick;www.rheinblick-immobilien-koeln.de;50667\n", encoding="utf-8"
    )
    out = tmp_path / "liste.xlsx"
    result = runner.invoke(app, ["enrich-list", str(csv), "--out", str(out), "--premium"])
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert "Thomas Berger" in result.stdout and "★" in result.stdout


def test_search_reports_places_error_without_traceback(httpx_mock, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        status_code=403,
        json={
            "error": {
                "code": 403,
                "message": "Places API (New) has not been used in project 1 before",
                "status": "PERMISSION_DENIED",
            }
        },
        is_reusable=True,
    )
    result = runner.invoke(app, ["search", "Immobilienmakler", "--city", "Köln"])
    assert result.exit_code == 1
    assert "Zugriff verweigert" in result.stdout and "Places API (New)" in result.stdout
    assert "Traceback" not in result.stdout


def test_export_from_jsonl(tmp_path: Path):
    from leadscraper.demo import demo_leads
    from leadscraper.models import SearchSpec

    jsonl = tmp_path / "leads.jsonl"
    jsonl.write_text(
        "\n".join(ld.model_dump_json() for ld in demo_leads(SearchSpec(queries=["x"]))), encoding="utf-8"
    )
    result = runner.invoke(app, ["export", str(jsonl), "--premium"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "leads_premium.xlsx").exists()
    assert "2 Leads" in result.stdout


def test_export_near_premium_merges_files_and_dedupes(tmp_path: Path):
    from leadscraper.cli import is_near_premium
    from leadscraper.demo import demo_leads
    from leadscraper.models import SearchSpec

    leads = demo_leads(SearchSpec(queries=["x"]))
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text("\n".join(ld.model_dump_json() for ld in leads), encoding="utf-8")
    b.write_text(leads[0].model_dump_json() + "\n", encoding="utf-8")  # Duplikat (gleiche place_id)
    near = [ld for ld in leads if is_near_premium(ld)]
    result = runner.invoke(app, ["export", str(a), str(b), "--near-premium"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "a_near_premium.xlsx").exists()
    assert f"{2 + len(near)} Leads (davon 2 Premium)" in result.stdout
    result = runner.invoke(app, ["export", str(a), str(b)])
    assert f"{len(leads)} Leads" in result.stdout  # Duplikat aus b.jsonl nur einmal


def test_rebuild_reruns_extractors_without_places(tmp_path: Path, fast_settings, fixture_web, monkeypatch):
    """rebuild liest die Websites erneut aus (Cache/Netz), aber ohne Google-Places-Anfragen."""
    from leadscraper.models import Company, Lead

    monkeypatch.setattr("leadscraper.cli.get_settings", lambda: fast_settings)
    jsonl = tmp_path / "de.jsonl"
    lead = Lead(
        company=Company(
            place_id="p1",
            name="Rheinblick",
            website="https://www.rheinblick-immobilien-koeln.de/",
            business_status="OPERATIONAL",
        )
    )
    jsonl.write_text(lead.model_dump_json() + "\n", encoding="utf-8")
    result = runner.invoke(app, ["rebuild", str(jsonl)])
    assert result.exit_code == 0, result.stdout
    assert "1 Firmen neu ausgewertet" in result.stdout
    out = [Lead.model_validate_json(line) for line in jsonl.read_text(encoding="utf-8").splitlines()]
    gf = next(p for p in out[0].enrichment.people if p.name == "Thomas Berger")
    assert gf.mobile is not None and out[0].premium is True
    assert not any("places.googleapis.com" in url for url in fixture_web)


def test_export_applies_current_chain_list(tmp_path: Path):
    """Die Ausschlussliste wächst während der Recherche – beim Export gilt der aktuelle Stand."""
    from leadscraper.models import Company, Lead

    jsonl = tmp_path / "de.jsonl"
    leads = [
        Lead(company=Company(place_id="a", name="Colliers International Hamburg", domain="colliers.de")),
        Lead(company=Company(place_id="b", name="Müller Immobilien GmbH", domain="mueller-immo.de")),
    ]
    jsonl.write_text("\n".join(ld.model_dump_json() for ld in leads), encoding="utf-8")
    result = runner.invoke(app, ["export", str(jsonl)])
    assert result.exit_code == 0, result.stdout
    assert "1 Ketten/Franchise/Portale aussortiert" in result.stdout
    assert "1 Leads" in result.stdout
