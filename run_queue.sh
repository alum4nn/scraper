#!/usr/bin/env bash
# Arbeitet eine Liste von Bundesländern nacheinander ab (ein Lauf nach dem anderen).
# Aufruf: ./run_queue.sh "Rheinland-Pfalz:rp" "Sachsen:sn" …
set -u
cd "$(dirname "$0")"
. .venv/bin/activate
for entry in "$@"; do
  land="${entry%%:*}"
  kurz="${entry##*:}"
  echo "=== $(date +%H:%M) Start $land" >> "output/run_$kurz.log"
  leadscraper run --deutschland -b "$land" --state "output/de_$kurz.jsonl" >> "output/run_$kurz.log" 2>&1
  echo "=== $(date +%H:%M) Ende $land (exit $?)" >> "output/run_$kurz.log"
done
