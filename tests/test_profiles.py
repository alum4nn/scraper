"""Die Suchprofile steuern, wofür Google-Geld ausgegeben wird – deshalb werden sie geprüft."""

import yaml

from leadscraper.settings import CONFIG_DIR

# Offizielle Place-Types (Tabelle A der Places API New), soweit hier verwendet. Ein Tippfehler
# führt sonst erst beim bezahlten Lauf zu INVALID_ARGUMENT.
BEKANNTE_TYPES = {
    "accounting",
    "car_dealer",
    "car_repair",
    "courier_service",
    "dentist",
    "electrician",
    "general_contractor",
    "home_health_care_service",
    "hotel",
    "insurance_agency",
    "lawyer",
    "moving_company",
    "painter",
    "pharmacy",
    "physiotherapist",
    "plumber",
    "real_estate_agency",
    "restaurant",
    "roofing_contractor",
}


def _profile() -> dict:
    with open(CONFIG_DIR / "branchen.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["profiles"]


def test_jedes_profil_hat_beschreibung_und_suchbegriffe():
    for name, prof in _profile().items():
        assert prof.get("beschreibung"), f"{name} ohne Beschreibung"
        assert prof.get("queries"), f"{name} ohne Suchbegriffe"
        assert len(prof["queries"]) == len(set(prof["queries"])), f"{name} mit doppeltem Suchbegriff"


def test_place_types_sind_gueltig():
    for name, prof in _profile().items():
        for typ in prof.get("included_types") or []:
            assert typ in BEKANNTE_TYPES, f"{name}: unbekannter Place-Type {typ}"


def test_recherchierte_zielbranchen_sind_vorhanden():
    """Ergebnis der Branchenrecherche: Betriebsgröße schlägt KI-Druck."""
    profile = _profile()
    for name in ("steuerberatung", "pflegedienst", "zahnarztpraxis", "apotheke", "kfz_betrieb"):
        assert name in profile, f"Profil {name} fehlt"
