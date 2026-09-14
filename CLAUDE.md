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

## Arbeitsweise
- Vor jedem Commit: `pytest -q` und `ruff check src tests && ruff format src tests`.
- Der API-Key steht in `.env` und gehört nie in einen Commit oder eine Ausgabe.
- Nach Änderungen an den Extraktoren wirken diese über `leadscraper rebuild` (liest aus dem HTML-Cache,
  keine Google-Anfragen) rückwirkend auf bereits abgearbeitete Orte; `leadscraper refresh` bewertet nur neu.
- Google-Anfragen kosten Geld: erst nachrechnen, dann starten. Ein Ort kostet zwei Textsuchen plus
  ein Geocoding.
