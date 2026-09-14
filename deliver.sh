#!/usr/bin/env bash
# Lieferung bauen: Excel und Trello-CSV aus allen Zustandsdateien, plus Kurzbericht je Bundesland.
# Aufruf: ./deliver.sh [Zielordner, Default output/lieferung]
set -u
cd "$(dirname "$0")"
. .venv/bin/activate

ZIEL="${1:-output/lieferung}"
mkdir -p "$ZIEL"

# Beide Suchspuren: Makler (de_*.jsonl) und Hausverwaltungen (hv_*.jsonl). Doppelte Firmen entfernt
# der Export selbst über place_id und Domain.
DATEIEN=$(ls output/de_*.jsonl output/hv_*.jsonl 2>/dev/null | grep -v state || true)
if [ -z "$DATEIEN" ]; then
  echo "Keine Zustandsdateien in output/ gefunden."
  exit 1
fi

# shellcheck disable=SC2086
leadscraper export $DATEIEN --premium -o "$ZIEL/premium_deutschland.xlsx"
# shellcheck disable=SC2086
leadscraper trello $DATEIEN -o "$ZIEL/trello_premium.csv"
# Zweite Reihe: Entscheider mit Handynummer, drei oder vier belegte Köpfe
# shellcheck disable=SC2086
leadscraper export $DATEIEN --near-premium -o "$ZIEL/zweite_reihe.xlsx"

python - "$ZIEL" <<'PY'
import json
import sys
from collections import Counter
from pathlib import Path

ziel = Path(sys.argv[1])
leads, gesehen = [], set()
for pfad in sorted(Path("output").glob("*.jsonl")):
    if "state" in pfad.name or not (pfad.name.startswith("de_") or pfad.name.startswith("hv_")):
        continue
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        if not zeile.strip():
            continue
        try:
            lead = json.loads(zeile)
        except json.JSONDecodeError:
            continue
        schluessel = lead["company"]["place_id"]
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        leads.append(lead)

premium = [x for x in leads if x["premium"]]
zeilen = []
for land, gesamt in Counter(x["company"].get("bundesland") or "?" for x in leads).most_common():
    prem = sum(1 for x in premium if (x["company"].get("bundesland") or "?") == land)
    zeilen.append((land, gesamt, prem))

bericht = [f"Stand: {len(leads)} geprüfte Firmen, {len(premium)} Kontakte mit mindestens 5 belegten Beschäftigten", ""]
bericht.append(f"{'Bundesland':26}{'geprüft':>9}{'Premium':>9}{'Quote':>8}")
for land, gesamt, prem in sorted(zeilen, key=lambda z: -z[2]):
    bericht.append(f"{land:26}{gesamt:9}{prem:9}{100 * prem / max(gesamt, 1):7.1f} %")

koepfe = Counter(min((x.get("enrichment") or {}).get("staff", {}).get("headcount", 0), 20) for x in premium)
bericht += ["", "Belegte Beschäftigte je Kontakt:"]
for k in sorted(koepfe):
    bericht.append(f"  {k:2}{'+' if k == 20 else ' '} Köpfe: {koepfe[k]}")

zuordnung = Counter((x.get("enrichment") or {}).get("mobile_assignment", "?") for x in premium)
bericht += ["", f"Handy-Zuordnung: {dict(zuordnung)}"]

text = "\n".join(bericht)
(ziel / "bericht.txt").write_text(text + "\n", encoding="utf-8")
print(text)
PY

echo
echo "Dateien in $ZIEL:"
ls -la "$ZIEL"
