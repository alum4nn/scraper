"""Konfiguration über Umgebungsvariablen / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    google_places_api_key: str | None = Field(default=None, alias="GOOGLE_PLACES_API_KEY")

    # Crawler
    max_pages_per_site: int = Field(default=8, alias="LEADSCRAPER_MAX_PAGES_PER_SITE")
    request_timeout_seconds: float = Field(default=15.0, alias="LEADSCRAPER_REQUEST_TIMEOUT_SECONDS")
    request_delay_seconds: float = Field(default=1.0, alias="LEADSCRAPER_REQUEST_DELAY_SECONDS")
    concurrency: int = Field(default=8, alias="LEADSCRAPER_CONCURRENCY")
    user_agent: str = Field(
        default="LeadScraper/0.1 (+https://github.com/alum4nn/scraper; B2B-Recherche)",
        alias="LEADSCRAPER_USER_AGENT",
    )
    respect_robots_txt: bool = Field(default=True, alias="LEADSCRAPER_RESPECT_ROBOTS")
    max_html_bytes: int = Field(default=2_000_000, alias="LEADSCRAPER_MAX_HTML_BYTES")

    # Cache (Google-Nutzungsbedingungen: nur place_id dauerhaft, Rest max. 30 Tage)
    cache_path: Path = Field(default=PROJECT_ROOT / "cache" / "leadscraper.sqlite", alias="LEADSCRAPER_CACHE_PATH")
    places_cache_ttl_days: int = Field(default=30, alias="LEADSCRAPER_PLACES_CACHE_TTL_DAYS")
    html_cache_ttl_days: int = Field(default=14, alias="LEADSCRAPER_HTML_CACHE_TTL_DAYS")

    output_dir: Path = Field(default=PROJECT_ROOT / "output", alias="LEADSCRAPER_OUTPUT_DIR")


def get_settings() -> Settings:
    return Settings()
