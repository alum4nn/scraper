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

### Nachtlauf 17./18.09. (Welle 8): Ziel 1.000 Handynummern, Stand 22:45 UTC 269

Auftrag 20:50 UTC: 1.000 Handynummern bei Firmen mit 10–50 belegten Köpfen, Festnetz nebenbei, Branchen
Personalagenturen, E-Commerce, sonstige Internet-Firmen plus eine Wahlbranche; Lieferung je 100 Handys,
Zwischenziel 400 in der Nacht. Verlauf:
- `welle8/sammeln.py` (OSM je Profil, Marken im Log) + `welle8/anreichern.sh` (wartet je Profil, Blöcke
  à 1.000) + `welle8/nachlese.sh <profil>` (Firmen aus nachgeholten Filtern als eigener Block).
- Personalagenturen: 503 Firmen, davon nur 22 im Korridor 10–50 → 8 Handys (6 GF bestätigt).
- E-Commerce über OSM gescheitert: kein Tag, Namens-Regex bundesweit bricht auf allen Spiegeln ab, je
  Bundesland einstellige Treffer. Aus der Kette genommen; Quelle dafür ist Google ab 1. Oktober.
- Sonstige Internet-Firmen: 2.036 gesammelt, 1.610 schon bekannt, 426 angereichert → +9 Handys.
- Wahlbranche Versicherung/Finanz vom Auftraggeber gestrichen (22:30), ebenso Steuerberater/Anwälte als
  Ersatz abgelehnt. Teilergebnisse liegen in `welle8/verworfen/`.
- Overpass-Regex ist POSIX-ERE: keine `(?:…)`-Gruppen, kein `\b` (HTTP 400). Schwere Namensabfragen laufen
  nur je Bundesland (`sammeln_laender.py`), bundesweit brechen die Spiegel ab.
- Nie `kill $(ps | grep muster)` mit einem Muster, das in der eigenen Kommandozeile steht – das killt die
  eigene Shell (zweimal passiert). Sicher: `awk '/muster/ && !/awk/'`.
Ergebnis: Anrufliste 1.362 (Handys 269: Internet 133, Großhandel 65, Immobilien 44, Planungsbüro 19,
Personalagentur 8). Das Ziel 400 wurde ohne vierte Branche nicht erreicht; offen ist die Branchenwahl des
Auftraggebers oder Google im Oktober.

### 19.09.: Gesamtexport aller Kontakte, getrennt nach Handy und Festnetz

Auftrag: alle je gesammelten Kontakte, nach Handy und Festnetz aufgeteilt, Branche in jeder Zeile.
Gebaut mit `scratchpad/kontakte.py` (Schalter `--nur-korridor` für 10–50 Köpfe) nach
`output/branchen/kontakte/`: eine Zeile je Mobilnummer, eine Zeile je Firma beim Festnetz (weitere
Anschlüsse in einer Spalte, sonst wären es 184.000 Zeilen). Je Branche ein Handy- und ein Festnetz-Blatt
plus eigene CSVs. Dedupliziert wird je Domain, wobei der reichhaltigste Datensatz gewinnt (Köpfe × 3 +
Personen × 2 + Nummern + Seiten) – vorher gewann die zuerst gelesene, oft ältere Fassung.

Ergebnis: 21.914 Handynummern, 48.545 Firmen mit Festnetz, 52.441 Firmen gesamt; im Korridor 10–50
Köpfe 4.753 Handynummern und 4.930 Festnetz-Firmen.

**Branchencheck (Workflow `wf_f43f455e-94a`, 80 Agenten).** Die OSM-Namensfilter hatten Handwerks- und
Industriebetriebe in die Internet-Rubrik gezogen. 1.522 verdächtige plus 450 zufällige Internet-Firmen
wurden mit dem Startseitentext aus dem HTML-Cache eingeordnet (kein neuer Netzzugriff), jede Umlabelung
von einem Skeptiker gegengeprüft: 1.186 umgelabelt, 221 vom Skeptiker zurückgeholt, 564 bestätigt.
Die frei formulierten Feinlabel (1.040 Schreibweisen für 1.186 Firmen) normalisiert `einarbeiten.py`
über eine Regex-Tabelle zu festen Oberbranchen; das Feinlabel bleibt als Unterbranche stehen.

Im Export markierte Restschwächen: `Beleg prüfen` (Belegschaftszahl stammt aus einem Werbetext über
Kundengrößen oder von einer fremden Domain – 227 Zeilen im Korridor), `Nummernformat` (735 Auslands-,
15 unklare Nummern), `Prüfung` (nur 310 Handys haben ein Einzelurteil, davon 120 bestätigte Chef-Handys).
In Autohaus/Kfz und Elektro/SHK sind viele ungeprüfte Handys Notdienstnummern.

### 19.09., Nachtrag: Geschäftsführer-Filter und Nachprüfung der offenen Nummern

`kontakte.py` schreibt zusätzlich Blatt „A Geschäftsführer-Handys" und `gf_handy*.csv`: nur Nummern mit
Kontaktart GF-Handy, GF-Handy geprüft oder Entscheider-Handy, also einer Person mit Entscheiderrolle
zugeordnet. 5.236 Nummern, davon 575 in Betrieben mit 10–50 belegten Köpfen.

Die 265 im Korridor noch ungeprüften Nummern wurden nachgeprüft (Workflow `wf_ac4b0498-8d4`, 46 Agenten,
Textfenster aus dem HTML-Cache über `audit/kontext_gf.py`, Skeptiker je Chef-Einstufung). Ergebnis
ernüchternd: nur 53 echte Chef-Handys, dagegen 123 Mitarbeiter (Niederlassungs- und Betriebsleiter,
Recruiter), 57 Zweifel, 9 Zentrale, 8 Agentur, 5 Notdienst. Die Kontaktart „Entscheider-Handy" des
Extraktors trägt also kaum: Sie stuft Standortleitungen regelmäßig als Entscheider ein.

**Fehler dabei gefunden und behoben:** Prüfurteile waren auf die Domain gekeyt, nicht auf die Nummer.
119 Betriebe haben mehrere geprüfte Nummern; deren Urteile haben sich gegenseitig überschrieben, wodurch
15 bestätigte Chef-Handys aus der Liste fielen. Schlüssel ist jetzt (Domain, Nummernziffern), und jede
Nummer bekommt ihr eigenes Urteil – auch Ansprechpartner- und Firmen-Handys, die vorher leer blieben.

Stand im Korridor 10–50: 173 bestätigte Chef-Handys, 401 aussortiert, 1 ohne Urteil.
Offen: die 4.662 Geschäftsführer-Handys außerhalb des Korridors sind ungeprüft (rund vier Stunden Prüfung).

## 22.09. – Der Engpass ist nicht die Handynummer, sondern der Größenbeleg

Gemessen über 52.095 angereicherte Firmen. 4.991 haben belegte 10–50 Köpfe, aber nur 469 davon tragen
ein Handy, das einer Chef-Person hängt. Umgekehrt liegen 4.431 Chef-Handys im Bestand, von denen die
allermeisten in Firmen stehen, deren Größe die Website nicht verrät.

**Ausbeute je Branche** (Firmen / veröffentlicht Chef-Handy / belegte 10–50 / beides):

| Branche | Firmen | Chef-Handy | Korridor | DIA-Quote |
|---|---:|---:|---:|---:|
| Großhandel | 1.710 | 4,4 % | 22,0 % | 2,16 % |
| Personalagentur | 404 | 5,7 % | 13,4 % | 1,98 % |
| Planungsbüro | 2.017 | 4,3 % | 13,4 % | 1,04 % |
| Immobilien | 12.314 | 17,7 % | 5,7 % | 0,62 % |
| Internet/Agentur | 12.099 | 4,6 % | 11,0 % | 0,45 % |
| Steuerberatung | 1.586 | 0,2 % | 4,3 % | 0,06 % |
| Bürobranchen (Welle 9) | 2.848 | 0,8 % | 6,5 % | 0,04 % |

Zwei Folgerungen. **Welle 9 wurde nach Block 5 abgebrochen** – Kanzleien und Steuerberater
veröffentlichen keine Handynummern, über 2.848 Firmen kam genau ein Kandidat heraus. Und Quellen
entscheiden mehr als Branchen: Großhandel kam aus Verbands-Mitgliederverzeichnissen (VTH, VCH, BDS,
DG Haustechnik, Soennecken) und konvertiert damit sechsmal besser als alles aus OpenStreetMap.

### Geprüft und verworfen (damit es niemand zweimal versucht)

- **Übersehene Handynummern im Zwischenspeicher:** 250 Korridorfirmen ohne Handy durchsucht, **0**
  gefunden. Der Telefon-Extraktor übersieht nichts; diese Firmen nennen schlicht keine Nummer.
- **Chef taucht bei einer anderen Firma mit Handy auf:** nur 7 belastbare Treffer bundesweit.
- **`leadscraper rebuild` über den Bestand:** an `de_hb.jsonl` getestet, 32 Firmen gewinnen, 30
  verlieren, Korridor 18 → 16. Der erneute Abruf verliert Personen, weil sich die Seiten geändert
  haben. **Ausnahme:** `output/de.jsonl` (1.687 Firmen, erste Welle) hatte gar kein `staff`-Feld, weil
  sie vor der Belegschaftszählung entstand. Dafür rechnet `tiefe/staff_nachtragen.py` die Belegschaft
  aus den gespeicherten Personen, Postfächern und Durchwahlen nach, ohne Netzzugriff
  (→ `output/branchen/rebuild/de_nachgetragen.jsonl`, 95 Korridorfirmen, 14 davon mit Chef-Handy).
- **Größenbeleg aus fremden Quellen:** northdata.de erlaubt es laut robots.txt, implisense.com
  ausdrücklich auch für ClaudeBot; europages.de, wlw.de und companyhouse.de sperren. Nicht weiter
  verfolgt, weil kleine GmbHs nach § 288 HGB keine Beschäftigtenzahl offenlegen müssen.

### Was heute dazukam

- **Korridor-Handys zugeordnet:** 1.572 Nummern in Korridorfirmen hingen an keiner Person. Vorfilter:
  nur wo der Nachname eines Chefs im Textfenster neben der Nummer steht, kann „chef" herauskommen –
  das sind 233 statt 1.572. Ungefiltert brachten 72 Nummern 0 Treffer, gefiltert 229 Nummern **17
  bestätigte** (`wf_439e98af-cec`, `wf_b65376ec-7ad`, Nachschlag `wf_67e86919-0f2` mit 13 weiteren).
- **Liste B angelegt:** Chef-Handys in Firmen mit 5–9 belegten Köpfen, 259 Nummern geprüft, **113
  bestätigt** (`wf_dd07c4a2-a42`). Die Gegenprüfung kippte nur 10 – Nummern, die der Extraktor bereits
  einer Chef-Person zugeordnet hat, halten zu rund 92 %.
- **Stand:** 212 bestätigte Chef-Handys in Bildschirmbranchen, davon 138 mit belegten 10–50 Köpfen.
  Ausgabe über `scratchpad/dia.py` (Excel, fünf Blätter) und `scratchpad/trello_dia.py` (Trello-CSV,
  Kartenname plus Beschreibung).

### Offen – hier geht es weiter

1. **Zwei Prüfungen abbrechen, nicht vergessen:** Größenbelege (`wf_81e086fd-f98`, Stufe 1 fertig: 76
   von 102 halten das Band 10–50) und Branchencheck (`wf_aa7f0c32-758`, Stufe 1 fertig: **39 von 160
   Firmen gehören nicht in die Liste**). Beide mit `resumeFromRunId` fortsetzen, dann `dia.py` und
   `trello_dia.py` neu bauen. Erst danach ist die gelieferte Trello-Datei belastbar.
2. **Liste B füllen:** `audit/batches_c/` hält 68 Stapel mit 1.010 ungeprüften Chef-Handys aus
   PC-Branchen, bei denen die Firma Anzeichen für Substanz zeigt (mehrere Personen, Postfächer oder
   Durchwahlen). Workflow `wf/liste_b.js`, Konsolidierung `audit/urteile_c_einarbeiten.py`. Erwartung
   nach den heutigen Quoten: 400 bis 450 neue bestätigte Nummern.
3. **Welle 11 zu Ende holen:** `welle11/sammeln.py` hat drei von vier Filtern (2.637 Firmen mit
   Website), der Namensfilter fehlt noch; fertige Filter werden übersprungen. Danach `enrich-list`.
4. **Welle 10 anreichern fertig** (535 eco-Mitglieder, `output/branchen/welle10/eco.jsonl`) – Chef-Handys
   daraus noch ungeprüft.
5. **Quellensuche** (`wf_d3558fde-0e0`) war erst bei 2 von 12 Branchen; sie sucht öffentliche
   Mitgliederverzeichnisse und prüft jedes technisch nach (robots.txt, HTML statt JavaScript, Website je
   Eintrag). Das ist der Weg für Liste A, weil dort der Korridor-Anteil zählt.

### Rechnung für 3.000 Leads

Bei der besten gemessenen Quote (Großhandel, 2,16 %) braucht ein Ziel von 3.000 belegten Leads rund
139.000 Firmen, realistisch gemischt eher 300.000. Der Relay schafft etwa 8.600 Firmen am Tag, das sind
fünf Wochen Dauerbetrieb. Zählt dagegen das bestätigte Chef-Handy und wird die Größe am Telefon geklärt,
sind 3.000 in ein bis zwei Wochen erreichbar: 212 liegen vor, rund 430 stecken in `audit/batches_c/`,
und Immobilien liefert mit 17,7 % dicht genug Nummern für den Rest. Der Auftraggeber will beide Listen
getrennt geführt bekommen.
