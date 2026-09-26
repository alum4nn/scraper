# Arbeitsanweisungen für dieses Repository

## Recherche bei 99 % Nutzungslimit anhalten
Die bundesweite Recherche läuft in abgekoppelten Hintergrundprozessen weiter, auch wenn die Sitzung
endet. Der Auftraggeber will nicht, dass sie unbeaufsichtigt weiterläuft, wenn das Nutzungslimit
erschöpft ist.

**Regel:** Sobald das Kontingent der Sitzung zu ~99 % verbraucht ist (Anzeige „tokens left“ unter etwa
150.000 von 15.000.000, oder eine Warnung über das erreichte Limit), sofort `./pause.sh` ausführen und
dem Auftraggeber in einem Satz mitteilen, dass mit `./resume.sh` weitergearbeitet wird. Nicht erst eine
Aufgabe zu Ende bringen – der Zwischenstand ist jederzeit wiederaufnehmbar.

```bash
./pause.sh     # hält alle Läufe an, Zwischenstand bleibt erhalten
./status.sh    # zeigt je Bundesland: fertige Orte, Firmen, Premium-Leads
./resume.sh    # setzt alle Bundesländer mit offenen Orten fort
```

## Ziel der Recherche
Bundesweite Liste von Immobilienmaklern für die telefonische Terminierung geförderter KI-Weiterbildung
(§ 82 SGB III). Ein Lead ist nur brauchbar, wenn

1. der Inhaber oder Geschäftsführer namentlich bekannt ist,
2. seine **Handynummer** belegt ist (Spalte „Handy-Zuordnung“ sagt, wie sicher) und
3. der Betrieb **mindestens fünf sozialversicherungspflichtig Beschäftigte** hat – belegt über
   `Enrichment.staff` (namentliche Mitarbeitende, persönliche Postfächer, eigene Durchwahlen oder eine
   ausdrückliche Angabe). Eine Vermutung aus der Rechtsform reicht nicht.

Ketten, Franchise-Systeme und Betriebe mit ausschließlich freien Handelsvertretern gehören nicht in die
Liste (`config/ausschluss.yaml`, `Enrichment.employment_signal`).

**Branchen (Auftraggeber, 25.09.):** Nur PC-lastige Betriebe. Handwerk bleibt draußen (auch Kfz, Elektro/SHK,
Metallbau, Spedition, ausführender Bau, Gastronomie, Ladengeschäfte). Produktion darf bleiben.

**Sperrgebiet Nordwesten (Auftraggeber, 25.09., „ganz wichtig“):** Keine Firma aus dem Nordwesten von Ahaus bis vor
Hamburg (Emsland, Grafschaft Bentheim, Ostfriesland, Oldenburger Land, Osnabrück, Münsterland, Bremen mit Umland,
Elbe-Weser-Dreieck). Maßgeblich ist die PLZ der Impressumsadresse (Firmensitz). Ausschließen, wenn die PLZ mit 26, 27,
28, 48, 49, 212, 216 oder 217 beginnt oder zum Kreis Borken gehört (46325, 46342, 46348, 46354, 46359, 46395, 46397,
46399, 46414, 46419). Ohne Adresse entscheidet die Festnetzvorwahl (025, 042, 044, 047, 049, 054, 059, 0414, 0416,
0418, 0286, 0287); Mobilnummern zählen nicht. Hamburg und alles östlich/südlich davon bleibt drin. Ort nicht
bestimmbar: Firma drinlassen, „📍 Ort unklar – bitte prüfen“. Ausgeschlossene Firmen am Ende separat auflisten
(Firmenname – Ort – Grund).

**Ausgabeformat Trello:** Kartenname nur der Firmenname. Adresse als eigene Zeile direkt unter der 🌐-Zeile:
„📍 Straße Hausnummer, PLZ Ort“ (nur Ort: „📍 PLZ Ort“, nichts: „📍 Adresse nicht gefunden“), Quelle Impressum,
dann Datenschutzerklärung, dann Kontaktseite – nichts raten. CSV mit allen Feldern in Anführungszeichen, UTF-8,
„&“ statt „\u0026“ oder „&amp;“.

**CRM-Format (Auftraggeber, 26.09., gilt für jede Lead-Liste; ersetzt Trello-CSV und Excel als Liefersatz):**
CSV, UTF-8, Trennzeichen `;`, Kopfzeile genau
`firma;person;rolle;handynummer;zentrale;email;website;strasse;plz;ort;branche;groesse;koepfe_belegt;ki_hebel;quelle;weitere_personen`.
Felder mit `;`, `"` oder Zeilenumbruch in Anführungszeichen, `"` verdoppeln. Eine Zeile = eine Firma, keine Firma doppelt,
höchstens 5000 Zeilen je Datei. Unbekanntes leer lassen, nie Platzhalter („-“, „k. A.“, „n/a“, „unbekannt“).
- firma mit Rechtsform wie im Impressum; person = wichtigste Person (Geschäftsführer/Inhaber vor Prokurist vor allen
  anderen), rolle genau dieser Person; handynummer nur von der Firma selbst veröffentlicht (Impressum, Kontakt, Team),
  Format „0170 1234567“, jede Nummer nur einmal in der Datei; zentrale „040 1234560“; email = allgemeine Adresse (info@…);
  website ohne „https://“ und ohne Unterseite; plz immer fünfstellig als Text; koepfe_belegt = Zahl namentlich genannter
  Personen (nur zählen); quelle = URL der Angaben (Pflicht, DSGVO-Auskunft); weitere_personen „Name (Rolle) Nummer“,
  getrennt mit „ / “.
- branche, groesse und ki_hebel nur aus `config/crm_katalog.json` (Branchenliste, Größenklassen und je Branche genau
  sechs KI-Hebel; auf Wunsch des Auftraggebers selbst erstellt), im Zweifel leer; ki_hebel getrennt mit „ | “.
- Nur geschäftliche, selbst veröffentlichte Angaben. Werbewidersprüche im Impressum führen NICHT zum Ausschluss
  (Auftraggeber, 26.09.: „das ist egal, mach es so wie davor“) – weder der Standardsatz noch andere Formulierungen.
- Die Datei ohne Erklärungen davor oder danach ausliefern.

## Arbeitsweise
- Vor jedem Commit: `pytest -q` und `ruff check src tests && ruff format src tests`.
- `LEADSCRAPER_CONCURRENCY` höchstens 12. Der ausgehende Verkehr läuft über einen Relay, der bei 24
  gleichzeitigen Verbindungen Tunnel abbricht (`ws_closed_mid_exchange` unter
  `curl -sS "$HTTPS_PROXY/__agentproxy/status"`); ein Lauf bleibt dann stehen, ohne Fehler zu melden.
  Gemessen: 12 Verbindungen ≈ 1,0 Seiten/s, 6 ≈ 0,8, 24 ≈ 0.
- Der API-Key steht in `.env` und gehört nie in einen Commit oder eine Ausgabe.
- Nach Änderungen an den Extraktoren wirken diese über `leadscraper rebuild` (liest aus dem HTML-Cache,
  keine Google-Anfragen) rückwirkend auf bereits abgearbeitete Orte; `leadscraper refresh` bewertet nur neu.
- Google-Anfragen kosten Geld. Der Auftraggeber will dafür nichts bezahlen, deshalb bremst
  `LEADSCRAPER_GOOGLE_MONATSLIMIT` (Vorgabe 1000) jede bezahlte Anfrage: Der Zähler steht in
  `output/google_verbrauch.json`, `leadscraper kosten` zeigt den Stand, und oberhalb der Grenze wird
  nichts mehr gesendet. Vor dem Erhöhen das eigene Freikontingent in der Google Cloud Console nachsehen.
  Ein Ort kostet zwei Textsuchen plus ein Geocoding. Treffer aus dem Zwischenspeicher kosten nichts.
- Ohne Google geht es auch: `leadscraper enrich-list <datei.csv>` schickt eine eigene Firmenliste
  (Spalten Firma, Website, optional Telefon, Straße, PLZ, Ort) durch dieselbe Pipeline. Für neue
  Branchen ist das der bevorzugte Weg, `leadscraper rebuild` und `refresh` arbeiten ohnehin
  ausschließlich aus dem Zwischenspeicher.
