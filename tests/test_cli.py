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


def test_run_requires_query_or_profile(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["run", "-c", "Köln"])
    assert result.exit_code != 0


def test_enrich_list_reads_csv_and_writes_excel(fixture_web, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LEADSCRAPER_REQUEST_DELAY_SECONDS", "0")
    monkeypatch.setenv("LEADSCRAPER_CACHE_PATH", str(tmp_path / "c.sqlite"))
    csv = tmp_path / "firmen.csv"
    csv.write_text(
        "Firma;Website;PLZ\nRheinblick;www.rheinblick-immobilien-koeln.de;50667\n", encoding="utf-8"
    )
    out = tmp_path / "liste.xlsx"
    result = runner.invoke(app, ["enrich-list", str(csv), "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert "Thomas Berger" in result.stdout
