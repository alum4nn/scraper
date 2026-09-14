"""Zentrale Datenmodelle. Alle Module tauschen ausschließlich diese Typen aus."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PhoneKind = Literal["mobile", "landline", "voip", "unknown"]
PhoneSource = Literal[
    "places",  # Google Places nationalPhoneNumber
    "impressum",
    "kontakt",
    "team",
    "karriere",
    "startseite",
    "vcard",  # .vcf-Download (TEL;TYPE=CELL)
    "whatsapp",  # wa.me / api.whatsapp.com-Link
    "tel-link",  # <a href="tel:...">
    "sonstige",
]
RoleCategory = Literal[
    "geschaeftsfuehrung",  # Geschäftsführer/-in, Vertretungsberechtigte, Vorstand, Inhaber
    "inhaber",
    "vorstand",
    "hr",  # Personalleitung, HR, People & Culture
    "ausbildung",  # Ausbildungs-/Weiterbildungsleitung
    "prokura",
    "betriebsleitung",
    "sonstige",
]
Confidence = Literal["high", "medium", "low", "none"]

# Reihenfolge = Priorität für die Kaltakquise (wer entscheidet über Weiterbildung?)
ROLE_PRIORITY: dict[str, int] = {
    "geschaeftsfuehrung": 0,
    "inhaber": 0,
    "vorstand": 1,
    "hr": 2,
    "ausbildung": 3,
    "prokura": 4,
    "betriebsleitung": 5,
    "sonstige": 9,
}


class PhoneNumber(BaseModel):
    raw: str
    e164: str  # +4917112345678
    national: str  # 0171 12345678
    kind: PhoneKind = "unknown"
    source: PhoneSource = "sonstige"
    source_url: str | None = None
    label: str | None = None  # z. B. "Mobil", "Handy", "WhatsApp", "Tel."
    person: str | None = None  # zugeordneter Name, falls in der Nähe gefunden

    @property
    def is_mobile(self) -> bool:
        return self.kind == "mobile"


class Person(BaseModel):
    name: str
    role: str | None = None  # Original-Bezeichnung, z. B. "Geschäftsführerin"
    role_category: RoleCategory = "sonstige"
    phones: list[PhoneNumber] = Field(default_factory=list)
    email: str | None = None
    source_url: str | None = None

    @property
    def mobile(self) -> PhoneNumber | None:
        return next((p for p in self.phones if p.is_mobile), None)


class SizeEstimate(BaseModel):
    employees_min: int | None = None
    employees_max: int | None = None
    point_estimate: int | None = None
    confidence: Confidence = "none"
    evidence: list[str] = Field(default_factory=list)  # z. B. "Text: 'Team von 25 Mitarbeitern' (https://…)"

    def in_range(self, lo: int | None, hi: int | None) -> bool | None:
        """True/False wenn beurteilbar, None wenn keine Schätzung vorliegt."""
        if self.point_estimate is None and self.employees_min is None and self.employees_max is None:
            return None
        est_lo = self.employees_min if self.employees_min is not None else self.point_estimate
        est_hi = self.employees_max if self.employees_max is not None else self.point_estimate
        if est_lo is None or est_hi is None:
            return None
        if lo is not None and est_hi < lo:
            return False
        if hi is not None and est_lo > hi:
            return False
        return True


class Company(BaseModel):
    """Ergebnis aus Google Places (Text Search / Place Details)."""

    place_id: str
    name: str
    formatted_address: str | None = None
    street: str | None = None
    plz: str | None = None
    city: str | None = None
    bundesland: str | None = None
    country: str | None = "DE"
    lat: float | None = None
    lng: float | None = None
    phone: str | None = None  # nationalPhoneNumber
    phone_international: str | None = None
    website: str | None = None
    domain: str | None = None
    primary_type: str | None = None
    types: list[str] = Field(default_factory=list)
    rating: float | None = None
    user_rating_count: int | None = None
    business_status: str | None = None
    google_maps_uri: str | None = None
    query: str | None = None  # Suchbegriff, über den die Firma gefunden wurde


class Enrichment(BaseModel):
    """Ergebnis des Website-Crawls."""

    website: str | None = None
    impressum_url: str | None = None
    legal_name: str | None = None
    rechtsform: str | None = None
    handelsregister: str | None = None  # "HRB 12345"
    amtsgericht: str | None = None
    ustid: str | None = None
    people: list[Person] = Field(default_factory=list)
    phones: list[PhoneNumber] = Field(default_factory=list)  # alle gefundenen Nummern, dedupliziert
    emails: list[str] = Field(default_factory=list)
    linkedin_url: str | None = None
    xing_url: str | None = None
    whatsapp_url: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    size: SizeEstimate = Field(default_factory=SizeEstimate)
    impressum_street: str | None = None
    impressum_plz: str | None = None
    impressum_city: str | None = None
    call_indicators: list[str] = Field(
        default_factory=list
    )  # Anhaltspunkte für mutmaßliches Interesse (§ 7 UWG)
    pages_crawled: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def mobiles(self) -> list[PhoneNumber]:
        return [p for p in self.phones if p.is_mobile]

    @property
    def decision_makers(self) -> list[Person]:
        return sorted(
            (p for p in self.people if p.role_category != "sonstige"),
            key=lambda p: ROLE_PRIORITY.get(p.role_category, 9),
        )


class FundingAssessment(BaseModel):
    size_band: str | None = None  # "<10", "10-49", "50-249", "250-2499", ">=2500"
    lehrgangskosten_pct: int | None = None
    arbeitsentgeltzuschuss_pct: int | None = None
    bonus_hinweise: list[str] = Field(default_factory=list)
    landesprogramm: str | None = None
    landesprogramm_url: str | None = None
    landesprogramm_hinweis: str | None = None
    pitch: str | None = None  # 1-2 Sätze für das Telefonat


class Lead(BaseModel):
    company: Company
    enrichment: Enrichment | None = None
    funding: FundingAssessment | None = None
    score: int = 0
    score_reasons: list[str] = Field(default_factory=list)
    in_target_size: bool | None = None
    scraped_at: datetime = Field(default_factory=datetime.now)

    # --- Convenience für Export/Scoring -------------------------------------------------
    @property
    def display_name(self) -> str:
        """Firmenname aus dem Impressum (eigene Website) – Google-Name nur als Fallback."""
        if self.enrichment and self.enrichment.legal_name:
            return self.enrichment.legal_name
        return self.company.name

    @property
    def address(self) -> tuple[str | None, str | None, str | None]:
        """(Straße, PLZ, Ort) – bevorzugt aus dem Impressum."""
        e = self.enrichment
        if e and e.impressum_plz:
            return e.impressum_street, e.impressum_plz, e.impressum_city
        return self.company.street, self.company.plz, self.company.city

    @property
    def best_mobile(self) -> PhoneNumber | None:
        if not self.enrichment:
            return None
        mobiles = self.enrichment.mobiles
        if not mobiles:
            return None
        # Bevorzugt: Nummer mit zugeordneter Person, dann Impressum/Kontakt vor Sonstigem
        src_rank = {"impressum": 0, "kontakt": 1, "team": 2, "vcard": 2, "whatsapp": 3, "places": 4}
        return sorted(
            mobiles,
            key=lambda p: (0 if p.person else 1, src_rank.get(p.source, 9)),
        )[0]

    @property
    def best_contact(self) -> Person | None:
        if not self.enrichment:
            return None
        dms = self.enrichment.decision_makers
        return dms[0] if dms else (self.enrichment.people[0] if self.enrichment.people else None)


class SearchSpec(BaseModel):
    """Parameter eines Suchlaufs (landet auch im Excel-Blatt 'Meta')."""

    queries: list[str]
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_km: float = 25.0
    included_type: str | None = None
    max_results_per_query: int = 60
    min_employees: int | None = 5
    max_employees: int | None = 50
    require_mobile: bool = False
    exclude_chains: bool = True  # Ketten/Franchise/Portale (config/ausschluss.yaml) aussortieren
    language: str = "de"
    region: str = "DE"
