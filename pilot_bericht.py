"""Pilotläufe vergleichen: Wo findet das Werkzeug Entscheider, Handynummer und Belegschaft?

Aufruf: python pilot_bericht.py [output/pilot]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SPALTEN = ("Firmen", "Website", "Entscheider", "Handy", "namentl.", "5+ belegt", "Premium")


def zaehle(leads: list[dict]) -> dict[str, int]:
    zahl = dict.fromkeys(SPALTEN, 0)
    for lead in leads:
        enr = lead.get("enrichment") or {}
        staff = enr.get("staff") or {}
        zahl["Firmen"] += 1
        zahl["Website"] += 1 if (lead.get("company") or {}).get("website") else 0
        entscheider = [p for p in enr.get("people") or [] if p.get("role_category", "sonstige") != "sonstige"]
        zahl["Entscheider"] += 1 if entscheider else 0
        zahl["Handy"] += 1 if any(p.get("kind") == "mobile" for p in enr.get("phones") or []) else 0
        zahl["namentl."] += 1 if enr.get("mobile_assignment") in ("namentlich", "eindeutig") else 0
        zahl["5+ belegt"] += 1 if staff.get("headcount", 0) >= 5 else 0
        zahl["Premium"] += 1 if lead.get("premium") else 0
    return zahl


def main(ordner: Path) -> int:
    dateien = sorted(ordner.glob("*.json"))
    if not dateien:
        print(f"Keine Pilotdateien in {ordner}")
        return 1
    print(f"{'Branche':18}" + "".join(f"{s:>12}" for s in SPALTEN))
    for datei in dateien:
        leads = json.loads(datei.read_text(encoding="utf-8"))
        zahl = zaehle(leads)
        print(f"{datei.stem:18}" + "".join(f"{zahl[s]:>12}" for s in SPALTEN))
    print("\nPremium = Entscheider + namentliche Handynummer + mindestens fünf belegte Beschäftigte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "output/pilot")))
