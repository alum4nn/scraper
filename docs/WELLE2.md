# Welle 2: GF-Handynummern über sechs Branchen – Stand und Wiederaufnahme

Stand 17.09.2026, 01:30 Uhr. Alle Läufe sind beendet, es läuft kein Crawler. Was hier steht, reicht, um
nach einem Sitzungsende, einem Container-Neustart oder einem Stopp wegen Nutzungslimit weiterzumachen.

## Was der Auftraggeber will
- Handynummern von **Inhabern oder Geschäftsführern** in Betrieben mit **10 bis 50 belegten Köpfen**
  (am 16.09. von 20 auf 10 gesenkt, Obergrenze 50 ist ausdrücklich gewünscht – nicht 80).
- Alles Weitere trotzdem aufheben („Datenkrake“): Ansprechpartner-Handys, Festnetz-Anrufliste,
  alle Handynummern, alle Firmen.
- Keine Notdienst- und keine Agenturnummern in der Liste. Deshalb wird jede Nummer einzeln geprüft.

## Wo die Daten liegen
| Datei | Inhalt |
|---|---|
| `output/branchen/grosshandel.jsonl` | Großhandel, 1.719 Firmen, per `rebuild` auf 10–80 bewertet |
| `output/branchen/welle2/*.jsonl` | 18 Blöcke: Spedition 1, Kfz 1–9, Planungsbüro 1–2, Elektro/SHK 1–4, Metallbau 1–2 |
| `output/branchen/datenkrake.xlsx` | Arbeitsbuch mit sieben Tabellen (siehe unten) |
| `output/branchen/datenkrake_gf_trello.csv` / `_alle.csv` | Trello-Import: GF-Handy ein Standort / alle |
| `cache/leadscraper.sqlite` | HTML-Zwischenspeicher (13 GB); `rebuild` arbeitet nur daraus, ohne Netz |

Die Skripte liegen im Scratchpad der Sitzung (`…/scratchpad/welle2/anreichern.sh`, `nachlauf.sh`,
`…/scratchpad/datenkrake.py`, `…/scratchpad/audit/kontext.py`). Sie sind kurz und im Sitzungsprotokoll
vollständig enthalten; das Arbeitsbuch lässt sich mit `export`/`trello` der CLI auch ohne sie erzeugen:

    leadscraper export output/branchen/grosshandel.jsonl output/branchen/welle2/*.jsonl \
        --premium --nur-ein-standort --nach-belegschaft -o output/branchen/gf_handy.xlsx
    leadscraper trello output/branchen/grosshandel.jsonl output/branchen/welle2/*.jsonl \
        --premium --nur-ein-standort --nach-belegschaft -o output/branchen/gf_handy_trello.csv

`--premium` bedeutet: Entscheider namentlich, Handynummer belegt, Belegschaft im Fenster, das beim
`enrich-list`/`rebuild` gesetzt war (10–80). Für die Obergrenze 50 zusätzlich nach „Beschäftigte
belegt“ filtern oder alle Dateien mit `rebuild --min-employees 10 --max-employees 50` neu bewerten
(rund zwei Stunden aus dem Zwischenspeicher, kein Netz).

## Ergebnis vor der Nummernprüfung (10–50 Köpfe)
GF-Handy ein Standort 166, inkl. Mehrstandort 237. Nach Branchen (10–80, ein Standort / alle):
Elektro/SHK 66/79, Kfz 58/93, Großhandel 26/39, Metallbau 14/20, Planungsbüros 12/21, Spedition 4/5.

## Nummernprüfung (läuft bzw. lief als Workflow `handy-audit`, Run `wf_cdc1fb6b-567`)
Für jede der 237 Nummern wurde der Text um die Nummer aus dem Zwischenspeicher geholt
(`audit/handys.json`, 20 Stapel in `audit/batches/`). Stichwort-Vorprüfung: 55 mit
Notdienst/Bereitschaft/Störung im Umfeld, 9 mit Webdesign/Agentur. Jede Nummer wird in eine Kategorie
eingeordnet (chef, notdienst, agentur, mitarbeiter, zentrale, unklar), jede „chef“-Einstufung von einem
zweiten Prüfer gegengelesen. Ergebnis gehört nach `audit/urteile.json`; `datenkrake.py` liest es und
verschiebt Treffer der schlechten Kategorien in Tabelle „7 Aussortierte Handys“ mit Grund.
Wiederaufnahme eines abgebrochenen Workflows: `Workflow({scriptPath: <Skript>, resumeFromRunId: "wf_cdc1fb6b-567"})`.

Danach gehören dieselben Regeln in den Extraktor (Notdienst-Kontext, Agentur-Impressum), mit Tests,
und die Zustandsdateien werden per `rebuild` neu bewertet.

## Bekannte Fehler und Fallen
- `refresh` verwirft gültige Belegschaftsbelege (Benien: 56 → 6). Nach Regeländerungen `rebuild`
  benutzen, nicht `refresh` (Aufgabe #18).
- Nach einem Container-Neustart wechselt der Relay-Port; laufende Prozesse tragen die alte Adresse
  in `HTTPS_PROXY` und scheitern mit „All connection attempts failed“. Prozesse beenden (nach PID,
  nie `pkill -f` mit einem Muster, das die eigene Shell trifft) und aus einer frischen Shell neu starten.
- `LEADSCRAPER_CONCURRENCY` bleibt bei 12; zwei Crawler gleichzeitig bringen den Relay zum Abbruch.
- Bei ~99 % Nutzungslimit: `./pause.sh` (hält die bundesweiten `run --deutschland`-Läufe an), laufende
  `enrich-list`/`rebuild`-Prozesse nach PID beenden; fertige Blöcke liegen als JSONL vor, der
  Zwischenspeicher macht jeden Neustart billig.
