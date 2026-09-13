import pytest

from leadscraper.funding import assess, funding_reference_rows, load_funding_config, size_band_for
from leadscraper.models import SizeEstimate


@pytest.mark.parametrize(
    ("n", "band"),
    [
        (0, "<10"),
        (9, "<10"),
        (10, "10-49"),
        (49, "10-49"),
        (50, "50-249"),
        (249, "50-249"),
        (250, "250-2499"),
        (2499, "250-2499"),
        (2500, ">=2500"),
        (10_000, ">=2500"),
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
    assert fa.size_band == "<10"
    assert fa.lehrgangskosten_pct == 100
    assert fa.arbeitsentgeltzuschuss_pct == 75
    assert fa.landesprogramm == "Bildungsscheck NRW"
    assert "100 %" in fa.pitch and "Bildungsscheck" in fa.pitch
    assert fa.bonus_hinweise


def test_assess_uncertain_uses_upper_bound():
    # 8-12 MA bei medium → konservativ 12 → Band 10-49 (50 %), nicht 100 %
    fa = assess(
        SizeEstimate(employees_min=8, employees_max=12, point_estimate=10, confidence="medium"), "Bayern"
    )
    assert fa.size_band == "10-49"
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
