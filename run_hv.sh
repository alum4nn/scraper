#!/usr/bin/env bash
# Zweiter Durchlauf: Hausverwaltungen. Eigene Zustandsdatei, damit der Makler-Lauf unberührt bleibt.
# Aufruf: ./run_hv.sh "Land:kurz" ...
set -u
cd "$(dirname "$0")"
. .venv/bin/activate
for entry in "$@"; do
  land="${entry%%:*}"; kurz="${entry##*:}"
  for versuch in 1 2 3 4 5 6 7 8; do
    echo "=== Start Hausverwaltung $land (Versuch $versuch)" >> "output/run_hv_$kurz.log"
    if leadscraper run --deutschland -q "Hausverwaltung" -b "$land" \
        --state "output/hv_$kurz.jsonl" >> "output/run_hv_$kurz.log" 2>&1; then
      echo "=== Hausverwaltung $land fertig" >> "output/run_hv_$kurz.log"
      break
    fi
    echo "=== Hausverwaltung $land abgebrochen, neuer Versuch" >> "output/run_hv_$kurz.log"
    sleep 5
  done
done
