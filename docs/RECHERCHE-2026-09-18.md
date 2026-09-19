# Recherchelauf 18.09.2026 – Entscheider-Handynummern, 10–50 Mitarbeitende

Manueller Rechercheauftrag: deutsche Unternehmen mit 10–50 Mitarbeitenden, bei denen eine
**Mobilnummer des Geschäftsführers/Inhabers** öffentlich auf der **eigenen** Website steht
und ein Bedarf für KI-Weiterbildung plausibel ist.

Ergebnisdaten liegen unter `output/` (gitignored, siehe *Datenschutz* unten).

## Vorgehen

1. Kandidatengewinnung über Websuche (Branche × Region) und über **Verbands-/Innungs-
   Mitgliederlisten** (Bauverband MV, SHK-Innungen, Kreishandwerkerschaften). Verzeichnisse
   dienten nur als Quelle für Firmen-URLs – belegt wurde jede Nummer ausschließlich auf der
   Unternehmenswebsite selbst.
2. Prüfung mit `tools/impressum_probe.py`: Impressum/Kontakt/Team/Ansprechpartner laden,
   Nummern strikt per `phonenumbers` als MOBILE klassifizieren, Textkontext mitschneiden.
3. Manuelle Bestätigung jeder Nummer an der Quelle (Rolle, Namensnähe, Fundstellen-URL).
4. Mitarbeiterzahl getrennt belegen (Website-Angabe oder Zählung namentlicher Teameinträge).

Geprüft wurden rund **320 Firmendomains**. Voll verifiziert: **3 Unternehmen** (4 Personen).

## Warum die Ausbeute niedrig ist

Die beiden Kriterien wirken gegeneinander: Betriebe, die die Handynummer des Chefs
veröffentlichen, sind überwiegend Kleinstbetriebe (< 10 Mitarbeitende); Betriebe mit 10–50
Mitarbeitenden veröffentlichen typischerweise nur eine Zentrale-Festnetznummer. Die Schnittmenge
findet sich fast ausschließlich auf **Team-/Ansprechpartner-Seiten** (nicht im Impressum) –
dort, wo Betriebe ihre Mitarbeitenden einzeln mit Durchwahl und Mobil listen. Genau darauf
sollte die Kandidatenauswahl künftig zielen.

## Aussortiert – und warum (Negativwissen)

| Unternehmen | Grund |
|---|---|
| Ingenieurbüro UTEK GmbH | GF-Mobilnummern öffentlich, aber **119 Festangestellte** (Personalstand 01.09.2026) → zu groß |
| Spedition Messing | GF-Mobil öffentlich, aber **160 Mitarbeitende** laut eigener Website → zu groß |
| IGB Construct | ~17 MA, aber der Geschäftsführende Gesellschafter hat nur Festnetz-Durchwahl; die Mobilnummern gehören Bauleitern |
| P.S.A. Bauunternehmung | GF ohne veröffentlichte Mobilnummer, nur Bauleiter |
| Bendgens, SL Versicherungsmakler, complus-media | Mobilnummer steht im **Footer jeder Seite** = allgemeine Firmennummer, nicht personenbezogen zuordenbar |

Fünf weitere Betriebe mit sauber zugeordneter GF-Mobilnummer scheiterten ausschließlich an der
**nicht belegbaren Mitarbeiterzahl** (siehe `output/leads-nicht-verifiziert-*.csv`).

## Beobachtung zum bestehenden Extraktor

`leadscraper enrich` gegen eine echte Steuerberater-Website lieferte Nummern wie `09538 60`
oder `04676 19` mit Personen wie „Feststellung Auswirkungen“ – also aus Fließtext (Paragrafen,
Jahreszahlen) zusammengesetzte Treffer inklusive falscher Namenszuordnung. Für die
Premium-Auswahl sollte `extract/phones.py` Kandidaten ohne Label (`Tel`/`Mobil`/`tel:`-Link)
und mit unplausibler Länge verwerfen.

## Datenschutz

Die Leaddateien enthalten personenbezogene Daten (Name + Mobilnummer identifizierbarer
Personen). Sie liegen bewusst unter `output/` und damit **außerhalb der Git-Historie**: Ein
Widerspruch nach Art. 21 DSGVO bzw. eine Löschung nach Art. 17 DSGVO lässt sich in einer
Git-Historie praktisch nicht mehr umsetzen. Leaddaten gehören daher nicht in dieses Repository.

Zur Nutzung gilt der Rahmen aus dem README (§ 7 UWG: Telefonwerbung B2B nur bei mutmaßlicher
Einwilligung; Art. 14/21 DSGVO: Informationspflicht beim Erstkontakt). Kalt-E-Mails, SMS und
WhatsApp-Nachrichten an diese Kontakte sind ohne ausdrückliche Einwilligung unzulässig.

## Zweiter Durchgang: Workflow-Lauf (Fan-out über 34 Branchen-/Regions-Slices)

Nach dem manuellen Lauf wurde die Suche als Multi-Agenten-Workflow wiederholt.

**Aufbau.** Pipeline statt Barriere: Jede Slice wird sofort nach Abschluss ihrer Suche geprüft
und gegengeprüft, damit laufend fertige Leads anfallen und ein Abbruch nicht das Ergebnis kostet.
Drei Phasen: Suche (WebSearch + `tools/impressum_probe.py` + eigene Tiefen-Sonden der Agenten),
Prüfung (Impressum und Fundstelle selbst laden, Footer-Gegenprobe, Mitarbeiterzahl wörtlich belegen),
Gegenprüfung (Skeptiker unter zwei Blickwinkeln: Zuordnung der Nummer / Unternehmensart und Größe;
im Zweifel gilt widerlegt).

**Ergebnis.** 15 von 34 Slices abgeschlossen, **32.512 Domains gescreent**, 44 Rohtreffer,
davon nach Prüfung und Gegenprüfung **34 bestätigte Kontakte in 26 Unternehmen**.
3 Kandidaten fielen in der Prüfung durch, 8 wurden von den Skeptikern gekippt.

**Trefferquote je Branche** (bestätigte Kontakte / gescreente Domains):
Immobilien und Hausverwaltung sowie Versicherung/Finanz tragen den Lauf. Steuerberatung und IT
liefern praktisch nichts: die Slice `stb-nrw` crawlte 337 Domains und 2.970 Seiten, fand dabei
14 Mobilnummern und musste jede einzelne verwerfen (Footer-Nummern, Fotografen aus dem
Bildnachweis, externe Datenschutzbeauftragte, Ein-Personen-Kanzleien).

**Betriebliche Lehren.**
- Die Maschine hat 4 CPUs, der Workflow läuft also mit Nebenläufigkeit 2. Prüfung und Skeptiker
  müssen je Slice gebündelt werden statt je Kandidat, sonst ist der Lauf nicht zu Ende zu bringen.
- Ein erster Anlauf lief ins Session-Limit und verlor dabei ausgerechnet alle Prüf-Agenten.
  Deshalb: Rohtreffer sofort auf Platte sichern und Prüfung vor weiterer Suche priorisieren.
- Dedup muss über die normalisierte Rufnummer laufen, nicht über Domain plus Nummer – dieselbe
  Firma wird von zwei Slices mit unterschiedlich geschriebener Website-URL gefunden.

**Offen.** 19 Such-Slices sind noch nicht gelaufen, darunter die laut Befund aussichtsreichen
Gewerke mit Außendienst-Geschäftsführern: Bau/Tiefbau, SHK, Elektro, Spedition, Metallbau,
GaLaBau, Produktion, Handel, Kfz, Gebäudereinigung, Facility Management.

## Stand beim Stopp am 19.09.2026

**Ergebnis: 41 verifizierte Kontakte in 32 Unternehmen** (`output/leads-gesamt-2026-09-19.csv`).
Davon 34 aus dem Workflow, 3 nachträglich über LinkedIn zurückgeholt, 4 aus dem manuellen Lauf.

**Warum abgebrochen.** Der dritte Durchgang war auf 50 Slices erweitert worden (18 offene Gewerke
plus 32 regional vertiefte Slices in den ergiebigen Branchen). Bei Nebenläufigkeit 2 entspricht das
rund einem Tag reiner Suchzeit; der Lauf wurde auf Wunsch gestoppt.

**Wo die Ausbeute verloren geht** (Auszählung über alle 15 Slice-Berichte aus Durchgang 1):
Footer-/allgemeine Firmennummer 46×, Nummer gehört einem Mitarbeiter statt dem Geschäftsführer 44×,
Firma zu klein bzw. Ein-Personen-Betrieb 39×, Verband/Portal/Franchise 24×, gar keine Mobilnummer 13×,
Firma zu groß 7×. Auf 44 akzeptierte Rohtreffer kommen also rund 130 Ablehnungen. Die Obergrenze von
50 Mitarbeitenden kostet praktisch nichts — der Engpass sitzt bei der Personenzuordnung und der
Untergrenze von 10.

**Fortsetzen.** Das Skript liegt unter
`~/.claude/projects/-home-user-scraper/.../workflows/scripts/gf-handynummern-kmu-wf_07a572da-14a.js`
mit 66 definierten und 50 aktiven Slices. Resume mit `resumeFromRunId: wf_07a572da-14a`; abgeschlossene
Agenten kommen aus dem Cache, nur Offenes läuft neu. Offene Rohtreffer ohne abgeschlossene Prüfung
stehen in `output/rohtreffer-offen-2026-09-19.csv` (u. a. Speedline Spedition und Multi Freight
Solutions aus der ersten Spedition-Slice).

**Ergiebigkeit je Branche** (Rohtreffer je Slice, Durchgang 1): Immobilien 11/5/4, Versicherung 6,
Finanz 6, Beratung 5, Kanzleien 3, Hausverwaltung 3 — gegenüber Steuerberatung 1/0 und IT 1/0/0.
Eine Fortsetzung sollte regional in den erstgenannten Branchen vertiefen, nicht neue Branchen raten.
