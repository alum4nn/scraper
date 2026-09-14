# Architektur

```
Google Places (Text Search)  ──►  Company
        │
        ▼
SiteCrawler (Website)  ──►  Pages (Impressum, Kontakt, Team, Karriere, Objekt-/Ansprechpartner-Seiten, vCards)
        │
        ├─► extract/impressum.py  → Rechtsform, Register, Entscheider (Geschäftsführer/Inhaber/Vorstand)
        ├─► extract/people.py     → weitere Personen + Rollen (HR, Ausbildung …) von Team-Seiten
        ├─► extract/phones.py     → ALLE Telefonnummern, klassifiziert (mobil/festnetz), Person zugeordnet
        ├─► extract/size.py       → Mitarbeiterzahl-Schätzung (Text, Team-Seite, Rechtsform, Bewertungen)
        ▼
funding.py (Förderquote §82 SGB III + Landesprogramm)  →  scoring.py  →  excel.py
```

## Kernidee "Entscheider-Handy"
1. Impressum lesen → Namen der Entscheider (z. B. `Geschäftsführer: Max Mustermann`).
2. Website gezielt nach Seiten durchsuchen, auf denen ein Entscheider-Nachname vorkommt
   (Team, Ansprechpartner, Objektseiten bei Maklern, Karriere) oder die `tel:`/`wa.me`/`.vcf`-Links enthalten.
3. Jede Mobilnummer (015x/016x/017x, `phonenumbers.number_type == MOBILE`) wird der nächsten
   Person im Text zugeordnet (gleiche Karte / ±4 Zeilen / vCard-Datensatz).
4. Lead-Score bevorzugt: Entscheider **mit** Handynummer > Firma mit Handynummer ohne Namen > nur Festnetz.

## Belegschaft: `extract/staff.py`
Für § 82 SGB III zählen nur sozialversicherungspflichtig Beschäftigte, und der Auftraggeber braucht
Betriebe ab fünf davon. Weil die Mitarbeiterzahl fast nie auf der Website steht, zählt `count_staff()`
**unterscheidbare Menschen** und führt sie über den Nachnamen zusammen (Namen, persönliche Postfächer,
eigene Durchwahlen). `Enrichment.staff.headcount` ist damit eine belastbare Untergrenze und die Grundlage
des Premium-Kriteriums; `SizeEstimate` bleibt die weichere Schätzung für Förderquote und Score.

Namen kommen aus drei Quellen, weil Team-Seiten unterschiedlich gebaut sind: Fließtext (`people.find_people`),
Bild-Alternativtexte und Links auf Personen-Unterseiten (`people.staff_from_links_and_images`).

## Betriebsgröße und Beschäftigte ohne Zahlenangabe
Die wenigsten Makler schreiben ihre Mitarbeiterzahl auf die Website. `extract/size.py` wertet deshalb
zuerst explizite Angaben („Team aus 14 Mitarbeitern“, Konfidenz *hoch*) und sonst Indizien
(`headcount_from_indicators`): namentliche Mitarbeitende auf Team-/Kontaktseiten, persönliche Postfächer
(`vorname.nachname@`), eigene Durchwahlen – die höchste dieser Zahlen ist die Untergrenze, Konfidenz
*mittel*. Bewertungsquoten („4,5/5 Mitarbeiter Zufriedenheit“), Auszeichnungen („TOP-5 Makler“) und
Haushaltsgrößen („optimal für 2 Personen“) sind ausgeschlossen.

`pipeline.employment_signal` beantwortet getrennt davon, ob es **sozialversicherungspflichtig**
Beschäftigte gibt (§ 82 SGB III fördert keine freien Handelsvertreter): Fundstellen wie Festanstellung,
Innendienst, Assistenz, Azubis – oder als Indiz mehrere Mitarbeitende neben der Geschäftsführung.

## Nachbearbeitung ohne neue Google-Anfragen
- `pipeline.refresh_lead` bewertet einen gespeicherten Lead neu (Indizien, Score, Premium, Zuordnung der
  Handynummer) – rein aus der JSONL-Datei, ohne Netz.
- `leadscraper rebuild` liest die Websites erneut aus (HTML-Cache, 14 Tage) und lässt damit auch
  Verbesserungen an Impressum-, Personen- und Telefon-Erkennung auf bereits abgearbeitete Orte wirken.

## Datenfluss / Verträge
Alle Module tauschen nur `leadscraper.models`-Typen aus. Siehe Docstrings in den Modulen.

## Google-Nutzungsbedingungen
- `place_id` darf dauerhaft gespeichert werden, andere Places-Felder max. 30 Tage (Cache-TTL).
- Die Excel-Datei ist das Arbeitsdokument des Vertriebs; Places-Daten darin werden nicht weiterverbreitet.

## Rechtlicher Rahmen (Kurz)
Siehe README → „Rechtlicher Rahmen“.
