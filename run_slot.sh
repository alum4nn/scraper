#!/usr/bin/env bash
# Ein Slot arbeitet Bundesländer nacheinander ab und startet einen abgebrochenen Lauf erneut.
# Aufruf: ./run_slot.sh "Land:kurz" ...
set -u
cd "$(dirname "$0")"
. .venv/bin/activate
for entry in "$@"; do
  land="${entry%%:*}"; kurz="${entry##*:}"
  for versuch in 1 2 3 4 5 6 7 8; do
    echo "=== Start $land (Versuch $versuch)" >> "output/run_$kurz.log"
    leadscraper run --deutschland -b "$land" --state "output/de_$kurz.jsonl" >> "output/run_$kurz.log" 2>&1
    code=$?
    if [ $code -eq 0 ]; then
      echo "=== $land fertig" >> "output/run_$kurz.log"
      break
    fi
    if [ $code -eq 3 ]; then
      # Google-Kontingent erschöpft – weitere Versuche sind sinnlos, der Stand ist gesichert.
      echo "=== $land pausiert: Google-Kontingent erschöpft, fortsetzen mit ./resume.sh" >> "output/run_$kurz.log"
      exit 3
    fi
    echo "=== $land abgebrochen, neuer Versuch" >> "output/run_$kurz.log"
    sleep 5
  done
done
