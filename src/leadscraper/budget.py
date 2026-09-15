"""Ausgabenbremse für kostenpflichtige Google-Anfragen.

Der Auftraggeber will für die Recherche nichts bezahlen. Google rechnet pro Anfrage ab und gewährt je
Produkt ein monatliches Freikontingent; wie hoch es im konkreten Konto ist, steht nur in der Cloud
Console. Deshalb zählt dieses Modul jede tatsächlich gesendete Anfrage mit und bricht ab, bevor die
eingestellte Grenze überschritten wird.

Gezählt wird nur, was wirklich hinausgeht: Treffer aus dem Zwischenspeicher kosten nichts und zählen
deshalb nicht. Der Zähler läuft je Kalendermonat und steht in einer Datei, überlebt also jeden Neustart.

    LEADSCRAPER_GOOGLE_MONATSLIMIT=1000   # Vorgabe, bewusst weit unter jedem Freikontingent
    LEADSCRAPER_GOOGLE_MONATSLIMIT=0      # Notbremse: gar keine Anfragen mehr
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path


class BudgetExceededError(RuntimeError):
    """Die eingestellte Obergrenze für bezahlte Google-Anfragen ist erreicht."""


def _monat() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


class RequestBudget:
    """Zählt Google-Anfragen je Kalendermonat und verweigert sie oberhalb der Grenze."""

    def __init__(self, path: Path, limit: int) -> None:
        self.path = path
        self.limit = max(0, int(limit))

    # --- lesen ----------------------------------------------------------------------------------

    def _laden(self) -> dict[str, object]:
        try:
            daten = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"monat": _monat(), "anfragen": 0}
        if not isinstance(daten, dict) or daten.get("monat") != _monat():
            return {"monat": _monat(), "anfragen": 0}  # neuer Monat, Zähler beginnt von vorn
        try:
            anzahl = int(daten.get("anfragen", 0))
        except (TypeError, ValueError):
            anzahl = 0
        return {"monat": _monat(), "anfragen": max(0, anzahl)}

    def verbraucht(self) -> int:
        return int(self._laden()["anfragen"])  # type: ignore[arg-type]

    def rest(self) -> int:
        return max(0, self.limit - self.verbraucht())

    def bericht(self) -> str:
        verbraucht = self.verbraucht()
        return (
            f"Google-Anfragen im {_monat()}: {verbraucht} von {self.limit} "
            f"({self.rest()} übrig, Zähler in {self.path})"
        )

    # --- schreiben ------------------------------------------------------------------------------

    def reservieren(self, anzahl: int = 1) -> None:
        """Eine Anfrage anmelden. Wirft BudgetExceededError, wenn die Grenze erreicht ist.

        Wird unmittelbar vor dem Senden aufgerufen, damit ein Abbruch keine Anfrage kostet.
        """
        daten = self._laden()
        verbraucht = int(daten["anfragen"])  # type: ignore[arg-type]
        if verbraucht + anzahl > self.limit:
            raise BudgetExceededError(
                f"Grenze erreicht: {verbraucht} von {self.limit} Google-Anfragen in diesem Monat "
                f"({_monat()}). Weitere Anfragen könnten Geld kosten und werden deshalb nicht "
                f"gesendet. Ändern mit LEADSCRAPER_GOOGLE_MONATSLIMIT in der .env – vorher das "
                f"Freikontingent des eigenen Kontos in der Google Cloud Console nachsehen."
            )
        daten["anfragen"] = verbraucht + anzahl
        self._schreiben(daten)

    def _schreiben(self, daten: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".budget-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(daten, fh, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def zuruecksetzen(self) -> None:
        self._schreiben({"monat": _monat(), "anfragen": 0})


def request_budget(settings: object) -> RequestBudget:
    """Zähler für die laufenden Einstellungen: liegt neben den Ergebnissen, Grenze aus der .env."""
    ordner = Path(getattr(settings, "output_dir", Path("output")))
    limit = int(getattr(settings, "google_monatslimit", 1000))
    return RequestBudget(ordner / "google_verbrauch.json", limit)
