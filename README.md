# leadscraper – Entscheider-Handynummern für die Terminierung (Fokus: Immobilienmakler)

Findet kleine Unternehmen (**5–50 Mitarbeitende**) über Google Places oder eine eigene Liste, liest deren Website
aus und liefert pro Firma den **Entscheider (Geschäftsführer/Inhaber) mit Handynummer**, eine belegte
**Mitarbeiterzahl-Schätzung** und die **Förderquote nach § 82 SGB III** – als fertig formatierte Excel-Liste für
die telefonische Kaltakquise von KI-Weiterbildungen.

```
Google Places (oder CSV) ──► Firmenwebsite ──► Impressum → Entscheider-Namen
                                          ──► Team-/Kontakt-/Objektseiten, vCards, WhatsApp-Buttons → Handynummern
                                          ──► Mitarbeiterzahl, Rechtsform, E-Mail, Anruf-Indikatoren
                          ──► Förderquote + Pitch ──► Score ──► Excel (Leads · Entscheider · Alle Nummern · Förderung · Meta)
```

## Warum so?
Im Impressum steht fast immer nur die Festnetznummer. Die Handynummer des Chefs steht **woanders**: auf der
Team-Seite („Mobil: 0171 …“), in der „Ihr Ansprechpartner“-Box einer Objektseite, in einer vCard (`.vcf`) oder
hinter dem WhatsApp-Button. Der Crawler arbeitet deshalb zweistufig:

1. **Impressum** lesen → Namen und Rollen der Entscheider (Geschäftsführer, Inhaber, Vorstand, Partner).
2. **Gezielt** die Seiten laden, auf denen diese Namen vorkommen oder `tel:`-/`wa.me`-/`.vcf`-Links stehen;
   jede Nummer wird per `phonenumbers` als **Mobil/Festnetz** klassifiziert und der nächstgelegenen Person zugeordnet.

Der **Score (0–100)** sortiert nach Terminierungs-Chance: Entscheider **mit** Handy (+50) > Handynummer ohne
Namen (+20/25) > nur Festnetz; dazu Mitarbeiterzahl im Zielbereich, inhabergeführt (Nachname im Firmennamen,
e.K./GbR), E-Mail; Abzüge für geschlossene Betriebe, unerreichbare Websites, Größe außerhalb.

## Installation
```bash
# macOS / Linux
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # GOOGLE_PLACES_API_KEY eintragen (optional, siehe unten)
```
```powershell
# Windows (PowerShell): Python 3.11+ von python.org, dann im Projektordner
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env      # GOOGLE_PLACES_API_KEY eintragen
leadscraper demo
```
Das Tool braucht **freien Internetzugang zu beliebigen Firmenwebsites**. Hinter einem Firmen-Proxy oder in einer
Sandbox mit Allowlist bleibt der Crawl leer – der Lauf meldet dann „⚠ … Websites nicht erreichbar – Netzwerk/
Proxy/Firewall prüfen“. In dem Fall lokal auf dem eigenen Rechner ausführen.

### Google-API-Key (für `run`)
Google Cloud Console → Projekt → Abrechnung aktivieren → **„Places API (New)“** aktivieren → API-Key (auf diese API
beschränken) → in `.env`. **Hinweis:** Mit einem Firmen-/Workspace-Konto kann das Anlegen eines Rechnungskontos
gesperrt sein („Kostenlose Testversion nicht verfügbar“) – dann ein privates Google-Konto nutzen oder den Admin um
die Rolle *Abrechnungskonto-Ersteller* bitten.

**Kosten:** Eine Anfrage liefert bis zu 20 Firmen. Mit Telefon/Website im Feldsatz gilt die Stufe *Text Search
Enterprise*: ca. 35 $ pro 1.000 Anfragen, **1.000 Anfragen pro Monat frei** (≈ 20.000 Firmen). Max. 60 Treffer
pro Suchbegriff → Region über mehrere Orte/Stadtteile abdecken, das Tool dedupliziert.

**Ausgabenbremse.** Damit die Recherche nichts kostet, zählt das Tool jede tatsächlich gesendete Anfrage gegen
`LEADSCRAPER_GOOGLE_MONATSLIMIT` (Vorgabe **1000**, also genau das freie Monatskontingent oben). Oberhalb der
Grenze wird nichts mehr gesendet, geprüft wird unmittelbar vor dem Senden. Treffer aus dem Zwischenspeicher
kosten nichts und zählen nicht mit.
```bash
leadscraper kosten                  # Stand des laufenden Monats
leadscraper kosten --zuruecksetzen  # Zähler auf null
```
`LEADSCRAPER_GOOGLE_MONATSLIMIT=0` schaltet Google vollständig ab. Vor dem Erhöhen das eigene Freikontingent in
der Google Cloud Console nachsehen – die Stufen und Freimengen ändern sich.

### Ohne Google
Google liefert nur die Firmenliste; die **Lead-Qualität entsteht im Website-Crawl**. Deshalb geht es auch ganz
ohne Google – kostenlos und ohne Konto:

```bash
# 1. Firmenliste aus OpenStreetMap holen (Tag-Filter je Profil in config/branchen.yaml)
leadscraper osm --profile steuerberatung -o output/osm/steuerberatung.csv
# 2. durch dieselbe Pipeline schicken
leadscraper enrich-list output/osm/steuerberatung.csv --jsonl-out output/steuer.jsonl -o output/steuer.xlsx
# 3. beide Anruflisten exportieren
leadscraper export output/steuer.jsonl --premium -o output/liste_a.xlsx
leadscraper export output/steuer.jsonl --mit-belegschaft -o output/liste_b.xlsx
```

Die Abdeckung von OpenStreetMap ist branchenabhängig und immer kleiner als die amtliche Grundgesamtheit; der
Abruf meldet deshalb Objekte, Namen und Websites. Erste Messung: 3.933 Steuerkanzleien, davon 2.074 mit Website.
Die Overpass-Server sind gespendete Rechenzeit – eine Abfrage je Tag, Pause dazwischen, Wiederholung bei
Überlastung. Daten © OpenStreetMap-Mitwirkende (ODbL); bei Weitergabe die Quelle nennen.

`leadscraper enrich-list firmen.csv` nimmt genauso jede eigene Liste (CSV/XLSX mit Spalten *Firma, Website*,
optional *Telefon, PLZ, Ort*).

## Benutzung
```bash
# Standard: Immobilienmakler-Profil, 5–50 Mitarbeitende, 25 km Radius
leadscraper run --city "Köln"
# Nur Diamanten (Entscheider mit namentlicher Handynummer + belegte Mitarbeiterzahl), mehrere Orte
leadscraper run -c Köln -c Bonn -c Leverkusen -c Bergisch\ Gladbach --radius-km 15 --premium

# Eigene Suchbegriffe / anderes Profil (siehe `leadscraper profiles`)
leadscraper run -q "Immobilienbüro" -q "Hausverwaltung" -c Düsseldorf --included-type real_estate_agency
leadscraper run --profile versicherung --city "Landkreis Rosenheim"

# Eigene Firmenliste ohne Google (mit Zustandsdatei für spätere Exporte)
leadscraper enrich-list firmen.csv --out output/liste.xlsx --jsonl-out output/liste.jsonl
# Firmenliste aus OpenStreetMap statt aus Google
leadscraper osm --profile pflegedienst -o output/osm/pflege.csv

# Bundesweit, Ort für Ort, unterbrechungssicher (erneuter Aufruf setzt fort)
leadscraper run --deutschland -b "Nordrhein-Westfalen" --state output/de.jsonl

# Ergebnisse ausgeben: Excel, nur Premium; mehrere Zustandsdateien werden zusammengeführt
leadscraper export output/de.jsonl output/de_bayern.jsonl --premium -o output/premium.xlsx
# Liste B: Entscheider + mindestens fünf belegte Beschäftigte, Handynummer nicht nötig (Zentrale anrufen)
leadscraper export output/de.jsonl --mit-belegschaft -o output/liste_b.xlsx
# CSV für den Trello-Import: Spalte 1 Unternehmensname, Spalte 2 alle Infos
leadscraper trello output/de.jsonl -o output/trello.csv

# Nach Regel-/Extraktor-Verbesserungen ohne neue Google-Anfragen nachziehen
leadscraper refresh output/de.jsonl     # nur neu bewerten (Score, Premium, Belegschaft)
leadscraper rebuild output/de.jsonl     # Websites erneut auslesen (HTML-Cache) und neu bewerten
```

### Bundesweit über Tage hinweg
```bash
./status.sh    # je Bundesland: fertige Orte, gefundene Firmen, Premium-Leads
./pause.sh     # alle Läufe geordnet anhalten, Zwischenstand bleibt erhalten
./resume.sh    # überall dort weitermachen, wo Orte offen sind
./run_hv.sh "Bayern:bayern"   # zweiter Durchlauf nur für Hausverwaltungen

# Nur Google-Suche testen / eine Website prüfen / Beispiel-Excel
leadscraper search "Immobilienmakler" --city Leverkusen
leadscraper enrich https://www.beispiel-makler.de
leadscraper demo --out output/demo.xlsx
```

### Wichtige Optionen (`run`)
| Option | Bedeutung |
|---|---|
| `--query/-q`, `--profile/-p` | Suchbegriffe bzw. Profil aus `config/branchen.yaml`; ohne Angabe: Profil `makler` |
| `--city/-c`, `--radius-km` | Ort/Region und Radius (max. 50 km); `-c` mehrfach für mehrere Orte (Google liefert max. 60 Treffer je Suchbegriff und Ort – Stadtteile/Nachbarstädte einzeln angeben) |
| `--premium` | Nur Diamanten: aktiver Betrieb, Website erreichbar, Entscheider aus dem Impressum, Handynummer diesem Entscheider zugeordnet, Betriebsgröße nicht belegt außerhalb, Beschäftigte plausibel. Ohne `--premium` zeigt die Spalte „Premium-Check“, was jeweils fehlt |
| `--deutschland`, `-b` | Ortsraster aus `config/orte.yaml` abarbeiten, optional auf Bundesländer beschränkt; `--state` speichert Zwischenstand und erlaubt Fortsetzen |
| `--min-employees/--max-employees` | Zielgröße (Default 5–50); sicher außerhalb liegende Firmen fliegen raus, unbekannte bleiben (abgewertet) |
| `--require-mobile` | Nur Firmen mit gefundener Handynummer |
| `--included-type` | Google-Place-Type, z. B. `real_estate_agency` (nur ein Typ) |
| `--no-chain-filter` | Ketten/Franchise/Portale (`config/ausschluss.yaml`) nicht aussortieren |
| `--json-out` | Rohdaten zusätzlich als JSON |

## Premium – wann gilt ein Lead als sofort terminierbar?
1. Betrieb aktiv und Website erreichbar.
2. Entscheider (Geschäftsführung/Inhaber/Vorstand) bekannt – aus dem Impressum, aus „Inhaber: …“ auf der
   Kontaktseite, aus dem Fließtext („… ist Gründer und Inhaber …“) oder als im Impressum Verantwortlicher,
   der den Firmennamen trägt.
3. Handynummer diesem Entscheider zugeordnet. Die Spalte **Handy-Zuordnung** sagt, wie sicher:
   *namentlich* (Name stand neben der Nummer) oder *eindeutig* (einzige Handynummer der Website bei genau
   einem Entscheider).
4. **Mindestens fünf Beschäftigte belegt.** Das ist das schärfste Kriterium: gezählt werden
   unterscheidbare Menschen, nicht Vermutungen. Eine Stichprobe an 30 echten Makler-Websites zeigte, dass
   ohne diese Hürde überwiegend Ein-Personen-Büros in der Liste landen.
   | Beleg | zählt als |
   |---|---|
   | Ausdrückliche Angabe („Team aus 14 Mitarbeitern“) | die genannte Zahl |
   | Namentlich genannte Mitarbeitende auf Team-/Kontaktseiten (auch aus Bild-Alternativtexten und Links auf Personen-Unterseiten) | eine Person je Nachname |
   | Persönliche Postfächer `vorname.nachname@`; `info@`, `buchhaltung@` zählen nicht | eine Person je Postfach |
   | Eigene Durchwahlen: mehrere Festnetznummern mit gleichem Stamm | ein Arbeitsplatz je Durchwahl |

   Die Signale werden über den Nachnamen **zusammengeführt, nicht addiert** – dieselbe Person hat Name,
   Postfach und Durchwahl. Die Rechtsform allein („GmbH, also wohl 5–49“) reicht nicht mehr.
5. Betriebsgröße nicht belegt über der Obergrenze und keine Hinweise auf ausschließlich freie
   Handelsvertreter, Franchise oder Provisionsbasis (§ 82 SGB III fördert keine Selbstständigen).
   Liegt schon die **belegte** Kopfzahl über der Obergrenze, fällt der Betrieb ebenfalls heraus – solche
   Treffer sind meist Verbünde mit einer gemeinsamen Teamseite.

### Liste B: dieselbe Förderbedingung, ohne Handynummer
Die Kriterien 3 und 4 arbeiten gegeneinander. Eine Handynummer im Impressum ist zulässig, weil ein
Festnetzanschluss Einzelunternehmer unverhältnismäßig belasten würde – sie ist deshalb ein **Marker für sehr
kleine Betriebe**. Wer fünf Beschäftigte hat, hat eine Telefonanlage mit Durchwahlen und kein Handy auf der
Seite. In den bisherigen Daten stehen 265 Betrieben mit namentlicher Handynummer 1.430 gegenüber, die die
Förderbedingung genauso erfüllen und nur über die Zentrale erreichbar sind.

```bash
leadscraper export output/de.jsonl --mit-belegschaft -o output/liste_b.xlsx
leadscraper trello output/de.jsonl --mit-belegschaft -o output/liste_b.csv
```

Liste B = Entscheider namentlich **und** mindestens fünf belegte Beschäftigte, Handynummer nicht erforderlich.
Die Spalte *Nummer* fällt dann auf die Zentrale zurück, damit jede Zeile wählbar ist. Kostet ein Gespräch mehr
am Empfang, dafür rund sechsmal so viele Betriebe, die tatsächlich förderfähige Beschäftigte haben.

Spalten **Beschäftigte belegt** und **Beleg Beschäftigte** zeigen Zahl und Fundstelle, sodass sich jeder
Lead vor dem Anruf prüfen lässt. `leadscraper export --near-premium` nimmt zusätzlich die Fälle auf, bei
denen nur der Beleg fehlt.

## Die Excel-Datei
| Blatt | Inhalt |
|---|---|
| **Leads** | Eine Zeile pro Firma, vorn die Spalten fürs Telefonat: **Name, Unternehmensname, E-Mail, Nummer, Webseite**; danach Score, Premium-Check, Rolle, **Handy-Zuordnung**, Fundstelle-URL, weitere Handys, Festnetz, E-Mail, Mitarbeiter (Schätzung/min/max/Konfidenz/**Beleg-Zitat**), Förderband, Lehrgangskosten %, AEZ %, Landesprogramm, **Pitch**, **Anruf-Indikatoren**, Adresse, Rechtsform, Register, Links … plus CRM-Spalten (Status Akquise als Dropdown, Termin, Notizen) |
| **Entscheider** | Eine Zeile pro Person (Handy zuerst, dann Rollen-Priorität) |
| **Alle Nummern** | Jede Nummer mit Art (mobil/festnetz), Label (Mobil/WhatsApp/Notdienst …), Person, Quelle, URL |
| **Förderung** | Referenztabelle § 82 SGB III + Landesprogramme (aus `config/foerderung.yaml`) |
| **Meta** | Suchparameter, Datum, Kennzahlen, Compliance-Hinweise |

Telefonnummern sind als **Text** gespeichert. Firmenname und Adresse kommen aus dem **Impressum**; Google-Daten
sind nur Fallback (Spalte „Firmenname Quelle“).

## Förderung (Stand 09/2026 – vor Kundengesprächen prüfen)
§ 82 SGB III seit 01.04.2024: **unter 50 Beschäftigte → bis 100 % Lehrgangskosten + 75 % Arbeitsentgeltzuschuss**,
50–499 → 50 %/50 %, ab 500 → 25 %/25 %; +5 Prozentpunkte bei Betriebsvereinbarung/Tarifvertrag; 100 %
Lehrgangskosten für Ü45/Schwerbehinderte in Betrieben < 500. Voraussetzungen: Maßnahme > 120 Stunden, AZAV-
zugelassener Träger und Maßnahme, Kenntnisse über reine Tool-Schulung hinaus, Berufsabschluss/letzte Förderung
≥ 2 Jahre zurück, Antrag vor Beginn beim Arbeitgeber-Service. Betriebsgröße zählt unternehmensweit (ohne
Azubis/Minijobber). Landesprogramme (für kurze Kurse) siehe `config/foerderung.yaml` – Status wechselt oft
(NRW nur noch individuell, Sachsen/Thüringen ausgesetzt).

## Mitarbeiterzahl – wie geschätzt?
Explizite Website-Angaben („Team von 12“, „über 30 Mitarbeitende“; Konzern-/„weltweit“-Angaben abgewertet)
→ Anzahl Personen auf der Team-Seite → Rechtsform-Prior (e.K./GbR klein, GmbH & Co. KG größer) → Anzahl
Google-Bewertungen (schwach). Für die Förderquote wird bei Unsicherheit die **obere** Schätzung verwendet.

## Rechtlicher Rahmen (Kurzfassung, keine Rechtsberatung)
- **Google Maps Platform (EWR-Bedingungen):** Nur die offizielle Places API, kein Scraping der Maps-Oberfläche.
  Dauerhaft gespeichert wird nur die `place_id`; Google-Firmendaten werden nicht vorgehalten (Places-Cache
  standardmäßig 1 Tag). Firmenname, Adresse, Telefon in der Excel stammen aus dem Impressum der Firmenwebsite.
- **§ 7 UWG – Kaltakquise B2B:** Telefonanrufe bei Unternehmen nur bei *mutmaßlicher Einwilligung* – es muss ein
  sachliches Interesse gerade an einem Anruf vermutet werden können (BGH); das BVerwG (29.01.2025, 6 C 3.23) hält
  ohne diese Vermutung schon das Erheben der Nummer für unzulässig. Die Spalte **„Anruf-Indikatoren“**
  dokumentiert die Anhaltspunkte je Lead (Karriereseite/Personalsuche, KI/Digitalisierung erwähnt, Weiterbildung
  erwähnt, HR-Verantwortliche benannt, förderfähige Größe). **Kalt-E-Mails, SMS, WhatsApp-, LinkedIn-/XING-
  Nachrichten sind ohne ausdrückliche Einwilligung unzulässig** – WhatsApp-Nummern nur telefonisch nutzen.
- **DSGVO:** Namen/Rollen/dienstliche Kontaktdaten aus Impressum und Website werden auf Basis des berechtigten
  Interesses (Art. 6 Abs. 1 lit. f, ErwGr. 47) verarbeitet. Beim Erstkontakt über Datenquelle, Zweck und
  Widerspruchsrecht informieren (Art. 14, 21); Widersprüche sofort umsetzen (Status „kein Interesse“ →
  Sperrliste); Verarbeitungsverzeichnis (Art. 30) und Löschfristen festlegen; Exporte nicht an Dritte weitergeben.
- **Websites:** `robots.txt` wird respektiert, identifizierender User-Agent, ~1 Anfrage/Sekunde pro Domain,
  wenige Seiten je Website, keine Umgehung von Schutzmaßnahmen, kein Auslesen von LinkedIn/XING/Portalen.

## Konfiguration
- `config/branchen.yaml` – Suchprofile (`makler` ist Default; `versicherung`, `handwerk`, …).
- `config/ausschluss.yaml` – Ketten/Franchise/Portale, die aussortiert werden.
- `config/foerderung.yaml` – Größenklassen/Förderquoten, Bonus-Regeln, Landesprogramme (Stand-Datum pflegen).
- `.env` – API-Key, Crawl-Tempo (`LEADSCRAPER_REQUEST_DELAY_SECONDS`), Seitenbudget
  (`LEADSCRAPER_MAX_PAGES_PER_SITE`), Parallelität (`LEADSCRAPER_CONCURRENCY`), User-Agent (eigene Kontaktadresse
  eintragen!).

## Entwicklung
```bash
pytest -q                      # ~230 Tests, inkl. Ende-zu-Ende gegen fiktive Websites in tests/fixtures/sites
ruff check src tests && ruff format src tests
```
Architektur: [`docs/ARCHITEKTUR.md`](docs/ARCHITEKTUR.md).

## Grenzen / Ideen
- JavaScript-only-Websites (SPA ohne Server-HTML) liefern wenig Text → Hinweis in „Fehler“; optionales
  Playwright-Rendering ist vorbereitet (`pip install -e ".[browser]"`), aber noch nicht angebunden.
- Impressum als PDF/Bild wird nicht gelesen; Mitarbeiterzahl bleibt eine Schätzung (im Gespräch verifizieren).
- Ideen: Playwright-Fallback, Handelsregister-Abgleich, Sperrlisten-Import (Widersprüche), CRM-Export.
