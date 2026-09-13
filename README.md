# leadscraper – B2B-Leads mit Entscheider-Handynummer für die Terminierung

Findet kleine Unternehmen (Ziel: **5–50 Mitarbeitende**) über **Google Places**, liest deren Website aus und
liefert pro Firma den **Entscheider (Geschäftsführer/Inhaber) mit Handynummer**, eine **Mitarbeiterzahl-Schätzung**
und die passende **Förderquote nach § 82 SGB III** – fertig formatiert als Excel-Liste für die telefonische
Kaltakquise von KI-Weiterbildungen.

```
Google Places ──► Firmenwebsite ──► Impressum (Entscheider-Namen)
                                 ──► Team-/Kontakt-/Objekt-Seiten, vCards, WhatsApp-Buttons (Handynummern)
                                 ──► Mitarbeiterzahl, Rechtsform, E-Mail, LinkedIn/XING
                 ──► Förderquote + Pitch ──► Score ──► Excel (Leads · Entscheider · Alle Nummern · Förderung · Meta)
```

## Warum so?
Im Impressum steht fast immer nur die Festnetznummer. Die Handynummer des Chefs steht aber oft **woanders**:
auf der Team-Seite („Mobil: 0171 …“), in der Ansprechpartner-Box einer Objekt-/Leistungsseite, in einer
vCard (`.vcf`) oder hinter dem WhatsApp-Button. Der Crawler arbeitet deshalb zweistufig:

1. **Impressum** lesen → Namen und Rollen der Entscheider.
2. **Gezielt** die Seiten laden, auf denen diese Namen (oder `tel:`-/`wa.me`-/`.vcf`-Links) vorkommen, jede
   Nummer per `phonenumbers` als **Mobil/Festnetz** klassifizieren und der nächstgelegenen Person zuordnen.

Der **Score (0–100)** sortiert die Liste nach Terminierungs-Chance: Entscheider mit Handy > Handynummer ohne
Namen > nur Festnetz; dazu Mitarbeiterzahl im Zielbereich, erreichbare Website, E-Mail usw.

## Installation
```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # GOOGLE_PLACES_API_KEY eintragen
```

**Google-API-Key:** In der [Google Cloud Console](https://console.cloud.google.com/) ein Projekt anlegen,
Abrechnung aktivieren, **„Places API (New)“** aktivieren, API-Key erstellen (empfohlen: auf diese API beschränken).
Kosten: siehe Abschnitt „Kosten“.

## Benutzung
```bash
# Alles auf einmal: Suche → Websites → Excel (Default: 5–50 Mitarbeitende, 25 km Radius)
leadscraper run --query "Immobilienmakler" --city "Köln" --radius-km 20

# Mehrere Suchbegriffe / Branchen-Profil aus config/branchen.yaml
leadscraper run --profile handwerk --city "Landkreis Rosenheim" --max-employees 30
leadscraper run -q "Steuerberater" -q "Rechtsanwalt" -c Bonn --require-mobile -o output/bonn_kanzleien.xlsx

# Nur Google-Suche testen (ohne Website-Crawl)
leadscraper search "Autohaus" --city Leverkusen

# Eine einzelne Website prüfen (Debugging: Was wird erkannt?)
leadscraper enrich https://www.beispiel-makler.de

# Beispiel-Excel ohne API-Key
leadscraper demo --out output/demo.xlsx

leadscraper profiles     # verfügbare Branchen-Profile
```

### Wichtige Optionen (`run`)
| Option | Bedeutung |
|---|---|
| `--query/-q` | Suchbegriff, mehrfach möglich („Immobilienmakler“, „Elektro Betrieb“) |
| `--profile/-p` | Profil aus `config/branchen.yaml` (mehrere Suchbegriffe + Google-Types) |
| `--city/-c`, `--radius-km` | Ort/Region und Radius (Google erlaubt max. 50 km Bias) |
| `--min-employees/--max-employees` | Zielgröße (Default 5–50). Sicher außerhalb liegende Firmen werden aussortiert, unbekannte bleiben (abgewertet) |
| `--require-mobile` | Nur Firmen mit gefundener Handynummer exportieren |
| `--included-type` | Google-Place-Type (z. B. `real_estate_agency`) für präzisere Treffer |
| `--json-out` | Rohdaten zusätzlich als JSON |

## Die Excel-Datei
| Blatt | Inhalt |
|---|---|
| **Leads** | Eine Zeile pro Firma: Score, Firma, **Entscheider, Rolle, Handy Entscheider, Fundstelle**, weitere Handys, Festnetz, E-Mail, Mitarbeiter (Schätzung, min/max, Konfidenz, **Beleg-Zitat**), Förderband, Lehrgangskosten %, AEZ %, Landesprogramm, **Pitch**, Adresse, Bundesland, Website, Rechtsform, Google-Bewertung … plus leere CRM-Spalten (Status Akquise mit Dropdown, Termin, Notizen) |
| **Entscheider** | Eine Zeile pro Person (Handy zuerst, dann Rollen-Priorität) |
| **Alle Nummern** | Jede gefundene Nummer mit Art (mobil/festnetz), Label, Person, Quelle, URL |
| **Förderung** | Referenztabelle § 82 SGB III + Landesprogramme (aus `config/foerderung.yaml`) |
| **Meta** | Suchparameter, Datum, Kennzahlen, Compliance-Hinweise |

Telefonnummern sind als **Text** gespeichert (keine Excel-Zahlenkonvertierung).

## Konfiguration
- `config/branchen.yaml` – Suchprofile (Suchbegriffe + Google-Types je Branche).
- `config/foerderung.yaml` – Größenklassen/Förderquoten § 82 SGB III, Bonus-Regeln, Landesprogramme.
  **Stand-Datum pflegen und Werte vor Kundengesprächen prüfen.**
- `.env` – API-Key, Crawl-Geschwindigkeit (`LEADSCRAPER_REQUEST_DELAY_SECONDS`), Seitenbudget pro Website
  (`LEADSCRAPER_MAX_PAGES_PER_SITE`), Parallelität (`LEADSCRAPER_CONCURRENCY`), User-Agent.

## Mitarbeiterzahl – wie geschätzt?
Reihenfolge der Signale (mit Konfidenz in der Excel): explizite Website-Angaben („Team von 12“, „über 30
Mitarbeitende“ – Konzern-/„weltweit“-Angaben werden abgewertet) → Anzahl Personen auf der Team-Seite → Rechtsform
(e.K./GbR klein, GmbH & Co. KG größer) → Anzahl Google-Bewertungen (schwach). Für die Förderquote wird bei
Unsicherheit die **obere** Schätzung verwendet, damit im Gespräch nichts versprochen wird, was nicht hält.

## Kosten (Google Places API)
Text Search wird pro Anfrage (Seite à 20 Treffer) abgerechnet; mit dem hier genutzten Feldsatz (Telefon, Website,
Adresse, Typ, Bewertung) liegt jede Anfrage in der teureren „Pro/Enterprise“-Stufe. Richtwert: **60 Treffer pro
Suchbegriff = 3 Anfragen**. Google gewährt ein monatliches Freikontingent; Details und aktuelle Preise unter
<https://developers.google.com/maps/billing-and-pricing/pricing>. Der lokale Cache (30 Tage) verhindert doppelte
Abfragen bei wiederholten Läufen.

## Rechtlicher Rahmen (Kurzfassung, keine Rechtsberatung)
- **Google Maps Platform:** Es wird ausschließlich die offizielle Places API verwendet (kein Scraping der
  Maps-Oberfläche). Dauerhaft gespeichert werden darf nur die `place_id`; andere Places-Daten werden max. 30 Tage
  gecacht. Die Excel ist das interne Arbeitsdokument des Vertriebs.
- **§ 7 UWG – Kaltakquise B2B:** Telefonanrufe bei Unternehmen sind zulässig, wenn ein sachliches Interesse
  vermutet werden darf (mutmaßliche Einwilligung) – bei geförderter Mitarbeiter-Weiterbildung in der Regel gegeben.
  **Kalt-E-Mails, SMS/WhatsApp-Nachrichten ohne Einwilligung sind unzulässig** – WhatsApp-Nummern nur telefonisch nutzen.
- **DSGVO:** Namen/Rollen/Geschäftsnummern aus Impressum und Website sind öffentlich zugängliche Geschäftsdaten;
  Verarbeitung auf Basis des berechtigten Interesses (Art. 6 Abs. 1 lit. f). Verarbeitungsverzeichnis führen,
  Widersprüche (Art. 21) sofort umsetzen („kein Interesse“ → Löschen/Sperren), Daten nicht länger als nötig behalten.
- **Websites:** `robots.txt` wird respektiert, identifizierender User-Agent, ca. 1 Anfrage/Sekunde pro Domain,
  max. ~8–12 Seiten pro Website. Keine Logins, keine Umgehung von Schutzmaßnahmen, kein LinkedIn/XING-Scraping
  (nur Profil-Links).

## Entwicklung
```bash
pytest -q
ruff check src tests && ruff format src tests
```
Architektur: [`docs/ARCHITEKTUR.md`](docs/ARCHITEKTUR.md). Test-Websites: `tests/fixtures/sites/`.

## Grenzen / Ideen
- JavaScript-only-Websites (SPA ohne Server-HTML) liefern wenig Text → Hinweis in der Spalte „Fehler“;
  optional Playwright-Rendering (`pip install -e ".[browser]"`, noch nicht angebunden).
- Impressum als PDF/Bild wird nicht gelesen.
- Mitarbeiterzahl ist eine Schätzung – im Gespräch verifizieren (die Förderquote hängt daran).
- Mögliche Erweiterungen: Handelsregister-/Unternehmensregister-Abgleich, Kununu-Größenklasse, CRM-Import.
