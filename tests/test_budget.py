"""Die Ausgabenbremse ist die einzige Zusage, dass die Recherche nichts kostet – also geprüft."""

import json

import pytest

from leadscraper.budget import BudgetExceededError, RequestBudget


def test_zaehlt_und_bremst(tmp_path):
    budget = RequestBudget(tmp_path / "verbrauch.json", limit=3)
    for _ in range(3):
        budget.reservieren()
    assert budget.verbraucht() == 3
    assert budget.rest() == 0
    with pytest.raises(BudgetExceededError) as fehler:
        budget.reservieren()
    assert "LEADSCRAPER_GOOGLE_MONATSLIMIT" in str(fehler.value)
    # Die abgewiesene Anfrage wurde nicht mitgezählt
    assert budget.verbraucht() == 3


def test_grenze_null_erlaubt_keine_anfrage(tmp_path):
    budget = RequestBudget(tmp_path / "verbrauch.json", limit=0)
    with pytest.raises(BudgetExceededError):
        budget.reservieren()


def test_neuer_monat_beginnt_von_vorn(tmp_path):
    pfad = tmp_path / "verbrauch.json"
    pfad.write_text(json.dumps({"monat": "2001-01", "anfragen": 999}), encoding="utf-8")
    budget = RequestBudget(pfad, limit=10)
    assert budget.verbraucht() == 0
    budget.reservieren()
    assert budget.verbraucht() == 1


def test_kaputte_datei_blockiert_nicht(tmp_path):
    pfad = tmp_path / "verbrauch.json"
    pfad.write_text("kein json", encoding="utf-8")
    budget = RequestBudget(pfad, limit=2)
    budget.reservieren()
    assert budget.verbraucht() == 1


def test_zaehler_ueberlebt_den_neustart(tmp_path):
    pfad = tmp_path / "verbrauch.json"
    RequestBudget(pfad, limit=5).reservieren()
    assert RequestBudget(pfad, limit=5).verbraucht() == 1


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_client_sendet_nichts_wenn_die_grenze_erreicht_ist(tmp_path, httpx_mock, anyio_backend):
    """Der Schutz sitzt vor dem Senden: bei erreichter Grenze geht keine Anfrage hinaus."""
    from leadscraper.places import PlacesClient

    budget = RequestBudget(tmp_path / "verbrauch.json", limit=0)
    client = PlacesClient("testschluessel", budget=budget)
    try:
        with pytest.raises(BudgetExceededError):
            await client.text_search("Steuerberater Köln")
    finally:
        await client.close()
    assert not httpx_mock.get_requests(), "es hätte keine HTTP-Anfrage geben dürfen"
