#!/usr/bin/env bash
# Pilotlauf für eine Branche: Lohnt sich die Spur? Ein Suchbegriff je Ort, danach Website-Prüfung.
# Kosten: je Ort eine Places-Textsuche plus ein Geocoding (rund 4 Cent).
# Aufruf: ./pilot.sh <profil> "<suchbegriff>" <Ort> [weitere Orte …]
set -u
cd "$(dirname "$0")"
. .venv/bin/activate

PROFIL="${1:?Profil fehlt}"
BEGRIFF="${2:?Suchbegriff fehlt}"
shift 2
[ $# -gt 0 ] || { echo "Mindestens ein Ort nötig"; exit 1; }

ORTE=()
for ort in "$@"; do ORTE+=(-c "$ort"); done
mkdir -p output/pilot

# --max-results 20 = eine Seite je Ort. 60 wären drei Seiten und damit dreimal so teuer.
leadscraper run -q "$BEGRIFF" "${ORTE[@]}" --max-results 20 \
  --json-out "output/pilot/${PROFIL}.json" \
  -o "output/pilot/${PROFIL}.xlsx"
