#!/usr/bin/env bash
# Recherche fortsetzen: startet für jedes Bundesland mit offenen Orten wieder einen Slot.
# Bereits abgearbeitete Orte werden übersprungen, es entstehen keine doppelten Google-Anfragen.
# Aufruf: ./resume.sh [Anzahl paralleler Slots, Default 4]
set -u
cd "$(dirname "$0")"
. .venv/bin/activate

SLOTS="${1:-4}"

offen=$(python - <<'PY'
import json
from pathlib import Path

import yaml

from leadscraper.settings import CONFIG_DIR

KURZ = {
    "nrw": "Nordrhein-Westfalen", "bayern": "Bayern", "bw": "Baden-Württemberg", "he": "Hessen",
    "ni": "Niedersachsen", "be": "Berlin", "hh": "Hamburg", "rp": "Rheinland-Pfalz",
    "sh": "Schleswig-Holstein", "sn": "Sachsen", "bb": "Brandenburg", "st": "Sachsen-Anhalt",
    "th": "Thüringen", "mv": "Mecklenburg-Vorpommern", "hb": "Bremen", "sl": "Saarland",
}
orte = yaml.safe_load(open(CONFIG_DIR / "orte.yaml", encoding="utf-8"))["orte"]
gesamt = {}
for o in orte:
    gesamt[o["bundesland"]] = gesamt.get(o["bundesland"], 0) + 1

# Bundesländer mit den meisten offenen Orten zuerst – so werden die Slots gleichmäßig ausgelastet.
rest = []
for kurz, land in KURZ.items():
    state = Path(f"output/de_{kurz}.state.json")
    fertig = len(json.load(open(state))["done"]) if state.exists() else 0
    offen = gesamt.get(land, 0) - fertig
    if offen > 0:
        rest.append((offen, f"{land}:{kurz}"))
print("\n".join(e for _, e in sorted(rest, reverse=True)))
PY
)

if [ -z "$offen" ]; then
  echo "Alle Bundesländer sind abgearbeitet."
  exit 0
fi

mapfile -t laender <<< "$offen"
echo "Offen: ${#laender[@]} Bundesländer, verteilt auf $SLOTS Slots"

for ((s = 0; s < SLOTS; s++)); do
  slot=()
  for ((i = s; i < ${#laender[@]}; i += SLOTS)); do
    slot+=("${laender[$i]}")
  done
  [ ${#slot[@]} -eq 0 ] && continue
  echo "  Slot $((s + 1)): ${slot[*]}"
  setsid nohup ./run_slot.sh "${slot[@]}" > /dev/null 2>&1 < /dev/null &
done

sleep 5
echo
./status.sh
