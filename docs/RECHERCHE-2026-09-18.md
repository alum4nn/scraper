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
