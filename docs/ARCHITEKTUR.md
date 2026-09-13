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

## Datenfluss / Verträge
Alle Module tauschen nur `leadscraper.models`-Typen aus. Siehe Docstrings in den Modulen.

## Google-Nutzungsbedingungen
- `place_id` darf dauerhaft gespeichert werden, andere Places-Felder max. 30 Tage (Cache-TTL).
- Die Excel-Datei ist das Arbeitsdokument des Vertriebs; Places-Daten darin werden nicht weiterverbreitet.

## Rechtlicher Rahmen (Kurz)
Siehe README → „Rechtlicher Rahmen“.
