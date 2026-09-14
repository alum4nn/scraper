#!/usr/bin/env bash
# Recherche anhalten. Beendet die Slots und die laufenden Läufe geordnet; der Zwischenstand bleibt in
# output/de_<kurz>.jsonl und output/de_<kurz>.state.json stehen. Fortsetzen mit ./resume.sh
set -u
cd "$(dirname "$0")"

slots=$(pgrep -f "run_slot.sh" || true)
[ -n "$slots" ] && kill $slots 2>/dev/null

runs=$(pgrep -f "leadscraper run --deutschland" || true)
[ -n "$runs" ] && kill $runs 2>/dev/null

for _ in 1 2 3 4 5 6 7 8 9 10; do
  pgrep -f "leadscraper run --deutschland" >/dev/null || break
  sleep 1
done
rest=$(pgrep -f "leadscraper run --deutschland" || true)
[ -n "$rest" ] && kill -9 $rest 2>/dev/null

# Eine beim Abbruch halb geschriebene letzte Zeile entfernen, damit der Neustart sauber aufsetzt
. .venv/bin/activate 2>/dev/null && python - <<'PY'
import json
from pathlib import Path

for path in sorted(Path("output").glob("de*.jsonl")):
    lines = path.read_text(encoding="utf-8").splitlines()
    good = []
    for line in lines:
        if not line.strip():
            continue
        try:
            json.loads(line)
            good.append(line)
        except json.JSONDecodeError:
            pass
    if len(good) != len([x for x in lines if x.strip()]):
        path.write_text("\n".join(good) + "\n", encoding="utf-8")
        print(f"{path.name}: unvollständige Zeile entfernt")
PY

echo "Recherche angehalten. Stand:"
./status.sh
