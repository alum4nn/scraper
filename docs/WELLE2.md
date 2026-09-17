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

## Welle 4 und 5 (17.09.2026): nur noch Firmen, die am PC arbeiten

Neue Zielgruppe seit 17.09.: Internet-Firmen (E-Commerce, Onlineshops, Online-Marketing, Digital-/Webagenturen,
Softwarehäuser) zuerst, dann Planungsbüros und Großhandel. Autohäuser, Speditionen, Elektro/SHK, Metallbau und
Werkstätten sind komplett raus (`datenkrake.py` liest sie gar nicht mehr ein).

- **Welle 4 (Google Places, Profil `internet`)**: 58 größte Städte × 6 Suchen → 3.683 Firmen mit Website
  (`welle4/internet.csv`, Spalte Rubrik), 4 Blöcke → `output/branchen/welle4/internet_0N.jsonl`. Ergebnis:
  3.328 angereicherte Firmen, 13 GF-Handys bei 10–50 Köpfen, davon 6 nach Einzelprüfung bestätigt.
  Google-Zähler danach 994/1000 – im September keine weiteren Google-Anfragen möglich.
- **Befund**: Internet-Firmen ab 10 Köpfen veröffentlichen das GF-Handy fast nie (87 GF-Handys in 1.783
  Firmen, fast alle bei Ein- bis Zwei-Personen-Agenturen). Tabelle 4 der Datenkrake (GF namentlich, Festnetz,
  10–50 Köpfe belegt) ist dort die Arbeitsliste.
- **Welle 5 (OpenStreetMap, ohne Google)**: `leadscraper osm --profile internet` (office=it,
  advertising_agency, web_design, marketing, software, Namensregex). Achtung: Der erste Lauf lieferte für
  office=it stillschweigend 0 Objekte; die direkte Abfrage bringt 5.060 Objekte / 3.666 mit Website
  (`welle5/internet_osm_it.csv`, getrennt nachgeholt). Kette `welle5/anreichern.sh`: 5.476 neue Firmen in
  6 Blöcken → `output/branchen/welle5/internet_osm_0N.jsonl`, etwa 40 Minuten je Block.
- **Prüfkette je Block**: `audit/kontext.py audit/handys_welle4.json 'output/branchen/welle4/*.jsonl'
  'output/branchen/welle5/*.jsonl'` → neue `audit/batches_w4/batch_NN.json` (alte Batches unverändert lassen,
  der Workflow-Cache hängt am Dateipfad) → Workflow `handy-audit-w4` (Run `wf_aa7a69c6-7c6`, BATCHES im Skript
  erweitern, mit resumeFromRunId fortsetzen) → `audit/urteile_w4.py` → `datenkrake.py` → Lieferung.

### Korrektur 17.09. 12:50 UTC: ausschließlich Internet-Firmen

Der Auftraggeber will nur Firmen, die online arbeiten. Großhandel (OSM `shop=wholesale` liefert Stahl-,
Schweiß- und Industrietechnik-Händler) und Planungsbüros sind deshalb aus der Datenkrake gestrichen; ihre
Rohdaten bleiben in `output/branchen/`. `datenkrake.py` liest nur noch `welle4/` und `welle5/` und wirft per
Namensregex (`_NICHT_ONLINE_RE`) Druckereien, Werbetechnik, Beschriftung, Fulfillment/Logistik, Verlage,
Verbände, Elektronik und Industrie heraus (221 von rund 7.000 Firmen). In Tabelle 1/2 steht nur, was die
Einzelprüfung als Chef-Handy bestätigt hat; ungeprüfte Nummern landen in Tabelle 7 als „ungeprüft“.

### 17.09. ab 16:20 UTC: Anrufliste über vier PC-Branchen (Ziel 1.000 Kontakte)

Der Auftraggeber will 1.000 Kontakte, „überwiegend Handynummern“, mehrere Branchen sind erlaubt. Zählung über
alles Gecrawlte bei 10–50 belegten Köpfen und einem Standort: In Internet, Immobilien, Planungsbüro und
Großhandel gibt es zusammen nur rund 340 Handynummern (89 beim GF, roh); mit den gestrichenen Branchen
(Kfz, Elektro/SHK, Metallbau, Spedition) rund 690, davon die Hälfte Notdienst und Werkstatt. „Überwiegend
Handy“ ist mit diesem Material also nicht erreichbar – so gemeldet.

Gebaut wurde stattdessen `datenkrake.py` → Blatt **„0 Anrufliste“** und `output/branchen/anrufliste.csv`:
eine Zeile je Firma, Stufe 1 GF-Handy einzeln geprüft, 2 Handy eines namentlichen Ansprechpartners,
3 Firmen-Handy bei bekanntem GF, 4 GF + Festnetz. Quellen: welle4–7 (Internet, inkl. OSM-Runden 2 und 3,
Profile `internet_erweitert` und `internet_runde3`), `welle2/planungsbuero_*`, `grosshandel.jsonl`
(Namensfilter `_GROSSHANDEL_RAUS_RE`: kein Stahl, keine Technik, kein Bau, keine Lebensmittel),
`output/de_*.jsonl` + `hv_*.jsonl` (Immobilien). Immobilien-GF-Handys wurden nachgeprüft
(`audit/batches_immo`, 41 → 15 chef). Stand 17:20 UTC: 1.281 Kontakte, davon 247 mit Handy (37 GF geprüft).

Fallen aus diesem Abschnitt:
- **Prüf-Kennnummern müssen über alle Batch-Ordner eindeutig sein.** `batch_neu.py` vergab neue ids nur
  nach `batches_w4` und kollidierte mit `batches_immo`; die Urteile wären falschen Firmen zugeordnet worden.
  Behoben (ids über `batches_*`), veraltete Journal-Einträge stehen in `audit/stale_keys.json` und werden
  von `urteile_w4.py` übersprungen. Das Workflow-Journal kennt nur ids, keine Dateinamen.
- OSM-Namensfilter über `office=company` holen auch Landtechnik, Energieberatung und Baugesellschaften;
  `_NICHT_ONLINE_RE` in `datenkrake.py` ist entsprechend gewachsen.
- Die Welle-6c-Kette schreibt wegen eines sed-Fehlers nach `output/branchen/welle6cb/`; die Globs sind
  darauf angepasst (`welle6c*`).

**Abschluss 17.09. 17:40 UTC:** Anrufliste 1.325 Kontakte (Internet 790, Immobilien 234, Großhandel 161,
Planungsbüro 140); Stufe 1 GF-Handy geprüft 36, Stufe 2 Ansprechpartner-Handy 121, Stufe 3 Firmen-Handy 95,
Stufe 4 GF + Festnetz 1.073. Insgesamt 93 GF-Handys einzeln geprüft, 39 bestätigt. Alle Ketten beendet, kein
Crawler aktiv. Nächste Hebel, wenn mehr Handys gewünscht: Google-Kontingent ab Oktober (1.000 Anfragen),
Korridor 5–9 Köpfe (+135 Handys in den vier Branchen), oder neue Branchen mit derselben Kette.
