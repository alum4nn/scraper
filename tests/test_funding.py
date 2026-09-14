import pytest

from leadscraper.funding import assess, funding_reference_rows, load_funding_config, size_band_for
from leadscraper.models import SizeEstimate


@pytest.mark.parametrize(
    ("n", "band"),
    [
        (0, "<50"),
        (9, "<50"),
        (49, "<50"),
        (50, "50-499"),
        (499, "50-499"),
        (500, ">=500"),
        (10_000, ">=500"),
        (None, None),
    ],
)
def test_size_band_for(n, band):
    assert size_band_for(n) == band


def test_assess_small_company_nrw():
    fa = assess(
        SizeEstimate(point_estimate=8, employees_min=8, employees_max=8, confidence="high"),
        "Nordrhein-Westfalen",
    )
    assert fa.size_band == "<50"
    assert fa.lehrgangskosten_pct == 100
    assert fa.arbeitsentgeltzuschuss_pct == 75
    assert fa.landesprogramm == "Bildungsscheck NRW 2.0"
    assert "100 %" in fa.pitch and "Bildungsscheck" in fa.pitch
    assert fa.bonus_hinweise


def test_assess_uncertain_uses_upper_bound():
    # 40-60 MA bei medium → konservativ 60 → Band 50-499 (50 %), nicht 100 %
    fa = assess(
        SizeEstimate(employees_min=40, employees_max=60, point_estimate=50, confidence="medium"), "Berlin"
    )
    assert fa.size_band == "50-499"
    assert fa.lehrgangskosten_pct == 50
    assert fa.landesprogramm is None


def test_assess_without_size():
    fa = assess(SizeEstimate(), "Hamburg")
    assert fa.size_band is None
    assert fa.lehrgangskosten_pct is None
    assert "§ 82 SGB III" in fa.pitch
    assert "Weiterbildungsbonus" in fa.pitch


def test_assess_low_confidence_adds_verification_hint():
    fa = assess(SizeEstimate(employees_min=5, employees_max=49, point_estimate=20, confidence="low"), None)
    assert "verifizieren" in fa.pitch


def test_reference_rows_cover_bands_and_laender():
    rows = funding_reference_rows()
    cfg = load_funding_config()
    bands = [r["Band / Bundesland"] for r in rows if r["Kategorie"].startswith("Bund")]
    assert bands == [b["band"] for b in cfg["bund"]["groessenklassen"]]
    assert any(r["Kategorie"] == "Landesprogramm" and r["Band / Bundesland"] == "Sachsen" for r in rows)
    assert rows[-1]["Kategorie"] == "Stand"
    assert any("ausgesetzt" in r["Hinweis"] for r in rows if r["Band / Bundesland"] == "Sachsen")
