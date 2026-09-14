#!/usr/bin/env bash
# Stand der bundesweiten Recherche: fertige Orte je Bundesland, gefundene Firmen, Premium-Leads.
set -u
cd "$(dirname "$0")"
. .venv/bin/activate 2>/dev/null

python - <<'PY'
import json
from pathlib import Path

import yaml

from leadscraper.settings import CONFIG_DIR

KURZ = {
    "nrw": "Nordrhein-Westfalen",
    "bayern": "Bayern",
    "bw": "Baden-Württemberg",
    "he": "Hessen",
    "ni": "Niedersachsen",
    "be": "Berlin",
    "hh": "Hamburg",
    "rp": "Rheinland-Pfalz",
    "sh": "Schleswig-Holstein",
    "sn": "Sachsen",
    "bb": "Brandenburg",
    "st": "Sachsen-Anhalt",
    "th": "Thüringen",
    "mv": "Mecklenburg-Vorpommern",
    "hb": "Bremen",
    "sl": "Saarland",
}

orte = yaml.safe_load(open(CONFIG_DIR / "orte.yaml", encoding="utf-8"))["orte"]
gesamt = {}
for o in orte:
    gesamt[o["bundesland"]] = gesamt.get(o["bundesland"], 0) + 1

zeilen, firmen_ges, prem_ges, offen_ges = [], 0, 0, 0
for kurz, land in KURZ.items():
    state = Path(f"output/de_{kurz}.state.json")
    data = Path(f"output/de_{kurz}.jsonl")
    fertig = len(json.load(open(state))["done"]) if state.exists() else 0
    firmen = prem = 0
    if data.exists():
        for line in data.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                lead = json.loads(line)
            except json.JSONDecodeError:
                continue
            firmen += 1
            prem += 1 if lead.get("premium") else 0
    alle = gesamt.get(land, 0)
    offen = max(0, alle - fertig)
    firmen_ges += firmen
    prem_ges += prem
    offen_ges += offen
    zeilen.append((land, fertig, alle, firmen, prem, offen))

print(f"{'Bundesland':24} {'Orte':>9}  {'Firmen':>7} {'Premium':>8}  Status")
for land, fertig, alle, firmen, prem, offen in sorted(zeilen, key=lambda z: -z[4]):
    status = "fertig" if offen == 0 and alle else (f"{offen} offen" if alle else "kein Ortsraster")
    print(f"{land:24} {fertig:4}/{alle:<4}  {firmen:7} {prem:8}  {status}")
print(f"{'GESAMT':24} {'':9}  {firmen_ges:7} {prem_ges:8}  {offen_ges} Orte offen")

laeufe = sum(1 for _ in Path("/proc").glob("[0-9]*/cmdline"))
PY

echo
if pgrep -f "leadscraper run --deutschland" >/dev/null; then
  echo "Laufende Läufe:"
  ps -eo args | grep "leadscraper run --deutschland" | grep -v grep | sed 's/.*-b //;s/ --state.*//' | sort | sed 's/^/  /'
else
  echo "Kein Lauf aktiv (fortsetzen mit ./resume.sh)"
fi
