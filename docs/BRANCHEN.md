# Wo morgen anrufen: Zielbranchenentscheidung für die geförderte KI-Weiterbildung nach § 82 SGB III

Stand: 15.09.2026. Grundlage: sechs Rechercheblickwinkel, fünf vertiefte Branchenurteile und eine Auswertung der eigenen Scraper-Ergebnisse aus `/home/user/scraper/output`.

## Kurzfassung

**Rufen Sie ab morgen in zwei Branchen an: ambulante Pflegedienste und Steuerberatungskanzleien** – und zwar über die Zentrale, nicht über ein Handy. In beiden Branchen steht auf der Website eine Telefonanlage mit Durchwahlen und keine Mobilnummer (0 von 11 geprüften Kanzleiwebsites; bei Pflegediensten ist die Mobilnummer das Rufbereitschaftshandy der diensthabenden Pflegekraft, keine Nummer für Werbung). Das Werkzeug liefert dafür seit heute Liste B. Die Begründung ist Betriebsgröße plus Anlass: Pflegedienste haben im Schnitt 28,7 Beschäftigte [8] und mit der Pflicht zum digitalen Leistungsnachweis ab 01.12.2026 einen datierten Schmerzpunkt in elf Wochen [29]; Steuerkanzleien haben den höchsten selbst geäußerten KI-Druck aller geprüften Branchen (rund drei Viertel der Sozietätspartner erwarten starke Veränderung durch KI [13]) und die beste Impressum- und Teamseiten-Datenlage. Am Makler-Ansatz war nicht das Telefonskript falsch, sondern die Grundgesamtheit: Im Grundstücks- und Wohnungswesen haben 96,8 % der Niederlassungen unter zehn Beschäftigte [1], die Umsatzträger sind selbstständige Handelsvertreter [4], und die einzige Fortbildungspflicht der Branche wurde am 24.07.2026 ersatzlos gestrichen [5]. Eine Aussage der Recherche musste dabei korrigiert werden: In den Rohdateien der Läufe tragen 1.407 Betriebe noch den Premium-Stempel einer älteren Regelfassung, 1.377 davon ohne jeden Belegschaftsnachweis – **ausgeliefert wurde das nie**. Jede übergebene Datei (75, 114, 186 und zuletzt 254 Zeilen) enthält ausschließlich Betriebe mit mindestens fünf belegten Beschäftigten; nachgerechnet am 15.09.2026 über alle vier Excel-Dateien. Die Absagen kamen also nicht von einer schlechten Liste, sondern von der Branche und vom Produktzuschnitt – das macht den Befund unten wichtiger, nicht harmloser. Erwartung dämpfen: Keine Branche im Feld hat mehr als 6 von 10 Punkten bekommen, der härteste Einwand („ich kriege niemanden frei“) kehrt überall wieder – deshalb Testcharge mit definiertem Abbruchkriterium, keine Kampagne.

## Warum Immobilienmakler nicht funktionieren

Vier strukturelle Gründe, keiner davon durch ein besseres Skript heilbar.

1. **Es gab fast nirgends fünf förderfähige Beschäftigte.** Abschnitt L (Grundstücks- und Wohnungswesen) hat 246.287 Niederlassungen, davon nur 7.121 (2,9 %) mit 10–49 Beschäftigten – gegenüber 13,5 % im Durchschnitt aller Branchen [1]. Destatis zählt 27.365 Maklerunternehmen mit rund 70.000 tätigen Personen, davon nur 42.013 Arbeitnehmer, also 2,56 tätige Personen je Büro [2]; der ZIA weist für Vermittlung und Verwaltung 53.329 Unternehmen mit 159.510 sozialversicherungspflichtig Beschäftigten aus, rechnerisch 3,0 je Unternehmen [3].
2. **Das Provisionsmodell schiebt die Arbeitskraft aus der Lohnliste.** Handelsvertreter nach § 84 HGB sind selbstständige Gewerbetreibende und nach § 82 SGB III nicht förderfähig [4], [45]. Ein Büro mit 20 Maklern ist arbeitsrechtlich oft ein Betrieb mit zwei Angestellten.
3. **Der regulatorische Anlass ist seit acht Wochen weg.** Die Weiterbildungspflicht nach § 34c Abs. 2a GewO (20 Stunden in drei Jahren) wurde am 11.06.2026 vom Bundestag aufgehoben, verkündet am 23.07.2026, in Kraft seit 24.07.2026 [5]. Für Wohnimmobilienverwalter besteht sie fort – aber 20 Stunden sind billig bedient und erzeugen keinen 120-Stunden-Bedarf.
4. **Die Branche bildet ohnehin kaum weiter.** Im ersten Halbjahr 2025 förderten nur 35 % der Betriebe unter zehn Beschäftigten Weiterbildung, gegenüber 93 % ab 500 Beschäftigten [6]. Weiterbildungsbeteiligung ist primär eine Funktion der Betriebsgröße.

**Der Befund aus den eigenen Daten ist deutlicher als jede Statistik.** Auswertung von `output/de*.jsonl` (bundesweiter Lauf, dedupliziert über `place_id`):

| Stufe | Betriebe | Anteil |
|---|---:|---:|
| Geprüfte Maklerbetriebe | 13.826 | 100 % |
| mit Website | 10.916 | 79,0 % |
| mit Impressum | 8.256 | 59,7 % |
| mit erkanntem Entscheider | 6.478 | 46,9 % |
| mit irgendeiner Handynummer | 4.799 | 34,7 % |
| Handynummer namentlich/eindeutig zugeordnet | 1.752 | 12,7 % |
| **mit mindestens fünf belegten Beschäftigten** | **175** | **1,3 %** |
| Entscheider **und** ≥ 5 belegte Beschäftigte | 169 | 1,22 % |
| alle drei Kriterien (heutige Regel) | 31 | 0,22 % |
| Premium-Stempel in den Rohdateien (alte Regelfassung, nicht ausgeliefert) | 1.407 | 10,2 % |

Von diesen 1.407 Einträgen mit altem Premium-Stempel haben 30 fünf oder mehr belegte Beschäftigte, 1.377 haben null. Dieser Stempel steht nur in den Rohdateien der Läufe: Die Auslieferung entstand aus `output/snapshot/`, also nach `rebuild` und `refresh` mit der strengen Regel. Geprüft: In allen vier übergebenen Excel-Dateien hat jede Zeile mindestens fünf belegte Beschäftigte (Median 8). Die Erklärung für die drei ergebnislosen Stunden liegt deshalb nicht in der Datenqualität, sondern in der Branche selbst – und im Zuschnitt des Produkts, siehe „Was am Pitch zu ändern ist“.

**Zwei Nebenbefunde aus denselben Daten, die für die Neuausrichtung wichtiger sind als alles andere:**

- **Der Suchbegriff entschied über den Faktor 15.** Im selben Lauf lieferte „Immobilienbüro“ 0,7 % Betriebe mit ≥ 5 belegten Beschäftigten, „Immobilienmakler“ 1,0–1,9 % – „Hausverwaltung“ dagegen 15,0–18,5 %.
- **Das Handy-Kriterium vernichtet die guten Leads.** Im Hausverwaltungs-Lauf (`output/hv*.jsonl`, 3.169 Betriebe) haben 685 (21,6 %) mindestens fünf belegte Beschäftigte und 647 zusätzlich einen Entscheider im Impressum – nach Anwendung des Handy-Kriteriums bleiben 75 übrig, ein Verlust von 88 %. Das ist die adverse Selektion in Zahlen: Eine Mobilnummer im Impressum ist rechtlich zulässig, weil ein Festnetzanschluss „kleinere Unternehmen und Einzelunternehmer unverhältnismäßig belasten“ würde [7] – sie ist damit ein Marker für genau die Betriebe, die zu klein für die Förderung sind. Die beiden Pflichtkriterien „Handynummer“ und „mindestens fünf SV-Beschäftigte“ arbeiten systematisch gegeneinander.

## Rangliste der Branchen

| # | Branche | Betriebe 5–49 | Fördernutzung heute | KI-Druck | Chef erreichbar | Website-Datenlage | Urteil |
|---|---|---|---|---|---|---|---|
| 1 | **Ambulante Pflegedienste** | ca. 8.000–9.500 private Dienste; 15.549 Dienste, Ø 28,7 Beschäftigte [8], 68,5 % privat [9] | Hoch: 2025 rd. 30.000 geförderte Pflege-Weiterbildungen, 9 von 10 als Beschäftigtenqualifizierung [10] | Niedrig: 13–15 % generative KI im Gesundheitswesen [11] | Mittel: PDL/Inhaber Di–Do 11–13:30 im Büro | Gut bei Entscheider und Team, Mobilnummer = Rufbereitschaft [31] | **Testen. Einziger Fall mit belegter Förderroutine + Frist.** |
| 2 | **Steuerberatungskanzleien** | 15.000–19.000 von 53.932 Praxen (Herleitung) [12], [13], [14] | Niedrig: modulare kaufmännische Fortbildung ist Bildungsziel, Instrument beim KMU unbekannt [20] | Hoch: ~75 % der Sozietätspartner, ~⅔ der Einzelkanzleien erwarten starke Veränderung [13]; Kammer leitet Fortbildungspflicht aus Art. 4 KI-VO ab [34] | Mittel: 11.–20. des Monats, Di–Do; Empfang filtert | Beste Impressum-/Teamseitenlage; **0 von 11 mit Mobilnummer** | **Testen. Bester Anlass, schlechteste Handy-Lage.** |
| 3 | Speditionen/Logistik | 7.000–12.000 (Herleitung); Abschnitt H: 21.972 Einheiten mit 10–49 [15], Ø 22,3 je Betrieb [1] | Mittel: Fahrerqualifizierung eingespielt, BALM-Parallelprogramm [38] | Widersprüchlich: 51 % (Bitkom, ab 20 MA) [17] vs. 13–15 % (IAB, repräsentativ) [11] | Mittel: Disposition wimmelt ab, GF in 8/10 namentlich | Sehr gut (6/10 persönliche Postfächer), **0 von 10 mit Mobilnummer** | Reserve. Höchste Insolvenzquote der Wirtschaft [37] |
| 4 | Autohäuser/freie Kfz-Werkstätten | ca. 18.000–22.000; 36.030 Betriebe, 428.000 Beschäftigte [18], 63 % der Beschäftigten in Betrieben unter 50 [19] | Mittel: Automotive ist Förderschwerpunkt, aber HV-/Markenschulung ist nicht förderfähig | Mittel: ZDK-Studie mit 64 Anwendungen [34a] | Gut: Chef an der Betriebsadresse | Beste Belegschaftslage im Feld (22–85 Namen), **0 von 8 mit Mobilnummer** | Reserve. Nur 2–3 Bürokräfte je Betrieb |
| 5 | Zahnarztpraxen | ca. 22.000–25.000; 37.423 Praxen, Ø 8,13 Beschäftigte [20] bzw. 10,1 tätige Personen [21] | Niedrig | Mittel: ePA-Pflicht seit 01.10.2025 [46] | **Schlecht**: Arzt behandelt, Empfang filtert; BVerwG-Urteil betraf genau diese Kaltakquise [47] | Gut bei Team, Mobilnummer = Notdienst | Nicht empfohlen |
| – | Metallbau/Schlosserei | 53 % der Innungsbetriebe mit 5–25 Beschäftigten [22] | Niedrig | Niedrig (Handwerk: 4 % KI-Nutzung) [28] | **Sehr gut**: Meister an der Betriebsadresse, Handy üblich | **Nicht geprüft** – kein Website-Test | Billigster Zusatztest, wenn 1 und 2 kippen |
| – | Elektro/SHK | ca. 40–45 %; 49.113 E-Betriebe mit 451.050 SV-Beschäftigten [24], 48.000 SHK mit 390.000 [25] | Niedrig | Niedrig: 4 % KI-Nutzung, 76 % sehen Digitalkompetenzlücke [28] | Gut (Notdienst-Handy) | Handy häufig, Belegschaft dünn | Nur Innendienst adressierbar |
| – | Apotheken | 16.601 Betriebe, knapp 10 Beschäftigte [26] | Niedrig | Gering belegt | Mittel | Handy selten | Nachrangig |
| – | Architektur-/Ingenieurbüros | 7.558 von 34.986 Büros (21,6 %) [27] | Niedrig | Hoch: 77 % wünschen KI-Fortbildung [27a] | Gut | Mittel | Zu kleinteilig |
| – | *Referenz: Immobilienmakler* | *7.121 von 246.287 (2,9 %) [1]; eigene Messung 1,3 %* | *keine* | *keine* | *sehr gut* | *Handy gut, Belegschaft nicht vorhanden* | *erledigt* |

### Platz 1: Ambulante Pflegedienste

Die stärksten Belege: Die Betriebsgröße stimmt als einzige Branche wirklich – 15.549 Dienste mit 446.425 Beschäftigten, also Ø 28,7 je Dienst [8], davon 68,5 % in privater, meist inhabergeführter Trägerschaft [9]; der Markt ist so fragmentiert, dass die 15 größten Betreiber zusammen 5,4 % Marktanteil halten [30a]. Die Förderung ist hier keine Behauptung, sondern Routine: 2025 förderte die BA rund 30.000 Weiterbildungen in Pflegeberufen, rund 9 von 10 davon als Beschäftigtenqualifizierung nach § 82, und das größte Einzelsegment sind 13.500 nicht abschlussorientierte berufsbezogene Weiterbildungen – genau der Maßnahmetyp, in den ein 120-Stunden-KI-Lehrgang fällt [10]. Die Zählregel arbeitet ausnahmsweise für Sie: Teilzeitkräfte zählen bei der Betriebsgröße nur mit 0,25 bis 0,75, Minijobber gar nicht [32] – bei 52,7 % Teilzeitanteil bleibt praktisch jeder private Dienst unter der 50er-Schwelle und bekommt 100 % Lehrgangskosten und 75 % Arbeitsentgeltzuschuss. Und es gibt einen datierten Anlass: Ab 01.12.2026 müssen ambulante Leistungsnachweise digital erfasst werden, sonst gibt es für Leistungen nach § 105 SGB XI keine Vergütung [29].

**Das K.-o.-Kriterium: die Freistellung.** Der Arbeitsentgeltzuschuss entsteht nur, soweit wegen der Teilnahme tatsächlich Arbeitsleistung ausfällt und der Arbeitgeber unter Entgeltfortzahlung freistellt; asynchrones Selbstlernen zählt seit der Fachlichen Weisung mit Stand 01.01.2026 ausdrücklich nicht als Unterricht [32], [33]. 120 Stunden heißen also gestrichene Touren – in einer Branche, in der 2026 monatlich 28 bis 71 Dienste dauerhaft schließen, rund 80 % davon private Träger [30]. Gegenmittel im Gespräch: nicht die Pflegefachkraft auf der Tour anbieten, sondern Abrechnung, Qualitätsmanagement, Verwaltung und stellvertretende PDL. Existiert diese Rolle im angerufenen Betrieb nicht, ist der Lead wertlos.

### Platz 2: Steuerberatungskanzleien

Die stärksten Belege: echte Lohnliste statt Provisionsnetz – in WZ 69.2 stehen 372.395 abhängig Beschäftigten nur 77.161 tätige Inhaber gegenüber, der Personalaufwand macht 61 % der Aufwendungen aus [14]. Der KI-Druck ist vom Berufsstand selbst quantifiziert: Rund drei Viertel der Partner in Berufsausübungsgesellschaften und knapp zwei Drittel der Einzelkanzleien erwarten, dass KI den Beruf sehr stark verändert; 88,8 % der Gesellschaften halten Prozessdigitalisierung für überlebensnotwendig [13]. Die eigene Kammer liefert den Aufhänger: „Kanzleiinhaber müssen aktiv dafür sorgen, dass Mitarbeitende und sie selbst KI-Kompetenz aufbauen“ [34]. Der Verkaufshebel ist aber nicht KI, sondern Personal: Nur 23,2 % der Kanzleien konnten zuletzt alle offenen Stellen besetzen, in Einzelkanzleien bleiben 59,1 % der Vakanzen unbesetzt [13]. Anders als bei Maklern gibt es keinen billigen Pflichtstundenkatalog, der das Thema sättigt – § 57 Abs. 2a StBerG normiert die Fortbildungspflicht ohne feste Stundenzahl [35].

**Das K.-o.-Kriterium: die Handynummer – und dahinter wieder die Freistellung.** In einer Stichprobe von elf Kanzleiwebsites (Startseite, Impressum, Kontakt, Team) fand sich **keine einzige Mobilnummer**, ausschließlich Zentralnummern mit Sammelanschluss. Bleibt die Handynummer Pflichtfeld, liefert der Scraper hier fast nur Einzelkanzleien unter fünf Beschäftigten, also exakt den Fehler der Maklerliste. Zweitens sind 120 Stunden drei Vollzeitwochen aus einem nachweislich unterbesetzten Team, und der Angerufene kennt das Förderinstrument besser als der Anrufer – er macht die Lohnabrechnung seiner Mandanten. Drittens ist der Bedarf teilweise gratis gedeckt: DATEV gibt den Copilot als kostenfreie Lizenz aus [36].

### Platz 3: Speditionen und Logistikdienstleister

Die stärksten Belege: Die Betriebsgrößenstruktur ist achtfach besser als bei Maklern – 21.972 rechtliche Einheiten in Abschnitt H mit 10–49 Beschäftigten [15], auf Niederlassungsebene Ø 22,3 Beschäftigte je Betrieb dieser Klasse [1]. Die Arbeit ist Bildschirmarbeit (Disposition, Zollanmeldung, Frachtabrechnung), also stundenweise über Monate freistellbar, und die Belegschaftsbelege sind exzellent: In einem Test über zehn Speditionswebsites war der Geschäftsführer in 8 von 10 Fällen namentlich im Impressum, in 6 von 10 Fällen fanden sich persönliche Postfächer nach dem Muster `vorname.nachname@`. Zusätzlich ein Zeitargument: Das konkurrierende BALM-Programm „Weiterbildung“ hatte 2026 die Antragsfrist 14.01.–31.08.2026 [39] – das Fenster ist seit zwei Wochen zu, § 82 läuft ganzjährig.

**Das K.-o.-Kriterium: die wirtschaftliche Lage plus null Handynummern.** Verkehr und Lagerei hat mit 71,6 Insolvenzen je 10.000 Unternehmen die höchste Insolvenzhäufigkeit der gesamten deutschen Wirtschaft [37]; ein Geschäftsführer in Existenzsorge trifft keine Zwölf-Wochen-Qualifizierungsentscheidung, auch nicht bei 100 % Förderung. In derselben Zehner-Stichprobe wurde **keine einzige Mobilnummer** gefunden. Dazu: Nur 30 % der Betriebe der Branche sind überhaupt ausbildungsberechtigt, der zweitniedrigste Wert aller Branchen [40], und nur 37 % verlangen Deutsch auf B2-Niveau [41] – Fahrpersonal und Lager fallen als Teilnehmer praktisch aus.

### Wo die Quellen sich widersprechen

- **KI-Nutzung Logistik:** Bitkom misst 51 % [17], das IAB 13–15 % [11]. Bitkom hat nur Betriebe **ab 20 Beschäftigten** befragt, das IAB repräsentativ alle Betriebe mit mindestens einem SV-Beschäftigten. Für die Zielgruppe 5–49 ist der IAB-Wert der belastbarere.
- **Steuerkanzleien im Korridor 5–49:** Die Blickwinkel-Recherche kam über die Kammerzahlen auf über 30.000 Kanzleien, die Vertiefung über die Destatis-Größenklassen auf 15.000–19.000 [14], [12]. Grund: „Tätige Personen“ enthält Inhaber, Minijobber (11,7 %) und Azubis (6,8 %), die alle nicht förderfähig sind – eine Einheit braucht rund sieben tätige Personen für fünf förderfähige. Rechnen Sie mit der niedrigeren Zahl.
- **Handwerksanteil 5–49:** Handwerkszählung 2023 ergibt 37,5 % [42], Handwerkszählung 2024 ergibt 40,8 % [23]. Unterschiedliche Stichtage, gleiche Größenordnung.
- **Zahl der Pflegedienste:** Destatis 15.549 zum 15.12.2023 [8], pflegemarkt.com 17.938 Standorte 2025/26 [30a]. Standorte ≠ Unternehmen.
- **Beschäftigte je Zahnarztpraxis:** KZBV 8,13 ohne Inhaber [20], Destatis 10,1 tätige Personen inklusive Inhaber [21]. Kein Widerspruch, unterschiedliche Abgrenzung.
- **Amtliche Lücke, die bleibt:** Eine veröffentlichte Tabelle „Betriebe nach WZ-Fünfsteller und Beschäftigtengrößenklasse“ existiert für keine dieser Branchen; die BA-Tabelle bricht nur bis zum Wirtschaftsabschnitt herunter, GENESIS verlangt ein Konto. **Alle Zahlen zur Klasse 5–49 in diesem Bericht sind Herleitungen, keine Messwerte.**

## Gegenprobe: Das Handwerk ist nicht die Rettung

Die telefonische Erreichbarkeit im Handwerk wurde im Blickwinkel „Entscheidungsweg“ als beste im Feld bewertet.
Statt darauf zu vertrauen, wurde sie mit demselben Verfahren gegengeprüft, das auch das Werkzeug benutzt:
Startseite laden, Impressum, Kontakt und Team folgen, Text auswerten. 66 Betriebswebsites angesteuert, davon 47
auswertbar, gezogen über Emsland, Ostwestfalen, Mittelfranken, Schwäbische Alb, Mecklenburg, Sachsen und
Schleswig-Holstein – bewusst keine Großstadtstichprobe.

| Gewerk | geprüft | Entscheider | Handy überhaupt | Handy beim Entscheider | 5 Beschäftigte belegt | alle drei |
|---|---:|---:|---:|---:|---:|---:|
| Elektrotechnik | 9 | 6 | 3 | 1 | 3 | 0 |
| Sanitär, Heizung, Klima | 9 | 5 | 1 | 0 | 3 | 0 |
| Metallbau, Schlosserei | 10 | 8 | 2 | 1 | 6 | **1** |
| Garten- und Landschaftsbau | 9 | 8 | 0 | 0 | 3 | 0 |
| Zahntechnische Labore | 10 | 9 | 1 | 0 | 7 | 0 |
| **Summe** | **47** | **36 (77 %)** | **7 (15 %)** | **2 (4 %)** | **22 (47 %)** | **1 (2 %)** |

Die Kriterienkette multipliziert sich zu Tode: 77 % Entscheidername mal 47 % Belegschaftsnachweis wären zusammen
noch tragfähig (rund 40 %), der Faktor 4 % für ein Handy beim Entscheider zieht das Ergebnis auf rund 2 %. Von den
sieben gefundenen Mobilnummern sind vier ausdrücklich Notdienst-, Zentral- oder Außendienstnummern, zwei gehören
Kleinstbetrieben ohne Belegschaft.

**Zwei Gewinner für Liste B.** Metallbau hat die beste Belegschafts-Datenlage im Test (6 von 10, meist ausdrücklich
und in der richtigen Größenordnung: „2 Spengler-Meister, 8 Facharbeiter, 3 Auszubildende“). Zahntechnische Labore
liegen bei 9 von 10 für den Inhabernamen und 7 von 10 für die Belegschaft – die beste Quote des Tests, aber ohne
Handy, weil ein Labor ein ortsfester Betrieb ohne Außendienst ist.

**Zwei Fehler im eigenen Werkzeug, gefunden und behoben.** Weiche Trennstriche (`&shy;`) stehen auf vielen
Handwerkerseiten mitten in den Wörtern, „Geschäfts­führer“ war für jede Rollen-Regex unlesbar. Und die
Verbund-Systeme der Innungen schreiben den Geschäftsführer ihres eigenen Hauses in die Fußzeile jeder Kundenseite –
reihenweise Betriebe bekamen denselben fremden Entscheider zugeschrieben. Beides ist repariert und mit Tests
abgesichert. Dritter Befund ohne schnelle Lösung: 19 von 66 Websites waren nicht abrufbar, fast alle mit demselben
Fehler desselben Massenhosters für Handwerksbetriebe.

**Place-Types:** Nur `electrician` und `plumber` existieren in Table A. `locksmith` ist der Schlüsseldienst und
nicht die Schlosserei; für Metallbau, GaLaBau und Dentallabore gibt es keinen Typ, sie brauchen zwei bis drei
Textsuchen je Ort statt einer.

## Empfehlung für die nächsten zwei Wochen

### Schritt 0: erledigt – Liste B liegt vor

Die beiden Pflichtkriterien „Handynummer beim Entscheider“ und „mindestens fünf belegte Beschäftigte“ arbeiten
systematisch gegeneinander. Eine Handynummer im Impressum ist erlaubt, weil ein Festnetzanschluss Einzelunternehmer
unverhältnismäßig belasten würde [7] – sie ist damit ein Marker für genau die Betriebe, die zu klein für die
Förderung sind. Wer fünf Beschäftigte hat, hat eine Telefonanlage mit Durchwahlen und kein Handy auf der Seite.

Umgesetzt am 15.09.2026, ohne eine einzige Google-Anfrage, aus den bereits bezahlten Daten:

| Liste | Kriterien | Betriebe |
|---|---|---:|
| **A (Premium)** | Entscheider + namentliche Handynummer + ≥ 5 belegte Beschäftigte | 252 |
| **B (neu)** | Entscheider + ≥ 5 belegte Beschäftigte, Nummer der Zentrale | 1.698 |

Liste B ist damit fast siebenmal so groß wie die bisher gelieferte Liste und erfüllt dieselbe Förderbedingung –
der Unterschied ist ein Satz mehr am Empfang. Median der belegten Beschäftigten: 9. Die Premium-Definition selbst
bleibt unverändert, Liste B ist ein zusätzlicher Export (`leadscraper export --mit-belegschaft`).

Zwei Nebenkorrekturen dabei: Betriebe, deren belegte Kopfzahl schon über der Obergrenze liegt, fallen jetzt aus
Premium heraus (Netzwerke mit gemeinsamer Teamseite, etwa ein Sachverständigen-Verbund mit 148 Namen auf 32
Standorten), und die Spalte „Nummer“ fällt auf die Zentrale zurück, damit jede Zeile wählbar ist.

**Dateien:** `output/lieferung_liste_b/liste_a_premium.xlsx`, `liste_b_belegschaft.xlsx`, `trello_liste_b.csv`.

### Vorher zu klären: Der Google-Zugang ist tot

Seit dem 15.09.2026 beantwortet die Places API jede Anfrage mit `PERMISSION_DENIED`, die Geocoding-API meldet
„This API is not activated on your API project“. Derselbe Schlüssel hat gestern 13.826 Betriebe geliefert. Solange
das so bleibt, ist kein Pilotlauf in einer neuen Branche möglich – zu prüfen sind Abrechnungskonto, Projektstatus
und Schlüsselbeschränkungen in der Google Cloud Console. Liste B und alle Auswertungen aus dem HTML-Cache
funktionieren davon unabhängig weiter.

### Branche 1: Ambulante Pflegedienste

- **Suchbegriffe:** „Ambulanter Pflegedienst“, „Pflegedienst“, „Häusliche Krankenpflege“, „Ambulante Pflege“. **Kein `included_type`** – Table A der Places API kennt keinen Typ für ambulante Pflege [44]; `home_health_care_service` existiert dort nicht, ein falscher Typ lässt die Textsuche leerlaufen. Nachfilter nötig gegen Pflegeheime, 24-Stunden-Betreuungsvermittler und Sanitätshäuser.
- **Orte zuerst:** Köln, Essen, Dortmund, Duisburg (höchste Dichte; in NRW kommt die Fortbildungspflicht der Pflegekammer von 70 Stunden in drei Jahren als Gesprächsanlass dazu [43]), dazu Hannover, Bremen, Leipzig, Nürnberg. Bewusst über mehrere Agenturbezirke streuen, weil die Mittel für die Beschäftigtenförderung regional bereits aufgebraucht sein können [48] – bundesweit breit, nicht regional tief.
- **Was das Werkzeug erwarten darf:** Geschäftsführer im Impressum (fast immer GmbH/UG, damit Pflichtangabe), Teamseiten mit namentlichen Mitarbeitenden als Branchenstandard, Dauerstellenanzeigen, Rufbereitschaftsseiten. Die gefundene Mobilnummer ist in der Regel **nicht** das Handy des Inhabers, sondern das Rufbereitschaftshandy der diensthabenden Pflegefachkraft [31] – diese Nummer nicht anrufen, sie ist eine Notfallleitung.
- **Gesprächseinstieg:** „Eine Frage zum 1. Dezember: Sie müssen die Leistungsnachweise dann digital abrechnen – wie viele Stunden gehen bei Ihnen aktuell noch für Doku, Tourenplanung und die MD-Vorbereitung drauf, die Ihnen keine Kasse bezahlt?“
- **Anrufzeit:** Dienstag bis Donnerstag, 11:00–13:30 Uhr. Vorher ist der Chef auf der Frühtour, nach 15 Uhr ist das Büro zu (typische Bürozeiten Mo–Do 8:30–15:00). Montag und Freitag meiden.

### Branche 2: Steuerberatungskanzleien

- **Suchbegriffe:** „Steuerberater“, „Steuerkanzlei“, „Steuerberatungsgesellschaft“, „Lohnbuchhaltung Büro“. **`included_type: accounting`** [44]. Der Begriff „Steuerberatungsgesellschaft“ ist der wichtigste – dort sitzen die Berufsausübungsgesellschaften mit Ø 32,8 Beschäftigten, während Einzelpraxen mit Ø 4,5 Beschäftigten unter der Schwelle liegen [13].
- **Orte zuerst:** Düsseldorf, Köln, Hannover, Nürnberg, Leipzig, Stuttgart, Dortmund, Bremen. Gesellschaften konzentrieren sich in Großstädten; Ketten für die Ausschlussliste: ETL (über 970 Kanzleien), Ecovis (über 150 Standorte).
- **Was das Werkzeug erwarten darf:** Berufsträger namentlich im Impressum (berufsrechtlich zwingend, in der Stichprobe 11 von 11), Teamseiten mit Namen und Funktion, teils mit ausdrücklicher Mitarbeiterzahl. **Nicht** erwarten: persönliche Postfächer (0 von 11 – Kanzleien verschleiern Adressen per JavaScript), Durchwahlen (2 von 11), Mobilnummern (0 von 11). `Enrichment.staff` muss hier über Namenslisten zählen.
- **Gesprächseinstieg:** „Wie viele Stellen haben Sie gerade offen, die Sie seit Monaten nicht besetzt kriegen? Genau deshalb rufe ich an: Ich helfe Kanzleien nicht beim Suchen, sondern dabei, die Leute, die schon da sind, so weit zu bringen, dass Belegverarbeitung und Kontierung nicht mehr die Hälfte des Tages fressen.“ Förderung, Stundenzahl und AZAV erst nennen, wenn der Schmerzpunkt bestätigt ist.
- **Anrufzeit:** Dienstag bis Donnerstag, **11. bis 20. des Monats**, 9:30–11:30 oder 14:00–16:00 Uhr. Bis zum 10. laufen Umsatzsteuer-Voranmeldung und Lohnsteueranmeldung, am Monatsende der SV-Beitragsnachweis. Heute ist Dienstag, der 15. – Sie sind mitten im besten Fenster, und September/Oktober ist neben Mai/Juni der beste Monatsblock des Jahres.

### Testplan und Abbruchkriterium

1. **Pilotlauf statt Kampagne** (sobald der Google-Zugang wieder steht)**.** `./pilot.sh pflegedienst "Ambulanter Pflegedienst" <8 Orte>` und `./pilot.sh steuerberatung "Steuerberatungsgesellschaft" <8 Orte>`. Kosten laut `pilot.sh`: eine Textsuche plus ein Geocoding je Ort, rund 4 Cent – 16 Ortsläufe also unter einem Euro. Auswertung mit `python pilot_bericht.py`, Vergleichsmaßstab ist der Makler-Trichter oben.
2. **Entscheidungsregel nach dem Pilot:** Liefert eine Branche unter 10 % Betriebe mit mindestens fünf belegten Beschäftigten, nicht weitermachen (Makler: 1,3 %, Hausverwaltung: 21,6 %).
3. **Danach 30 bis 50 Anrufe je Branche, und die Einwände zählen.** Lautet der dominierende Einwand „Ich kriege niemanden dafür frei“ und nicht „Was kostet das“, ist die Branche für dieses Produkt genauso tot wie die Makler – aus demselben Grund, Kapazität statt Geld, nur mit anderer Ursache. Dann als billigsten Zusatztest Metallbau/Schlosserei über Liste B nehmen: 53 % der Innungsbetriebe haben 5 bis 25 Beschäftigte [22], und in der eigenen Stichprobe belegten 6 von 10 Betrieben fünf oder mehr Beschäftigte – die beste Quote im Test. Die Handynummer steht dort allerdings genauso selten wie überall sonst, siehe die Gegenprobe oben.

## Was am Pitch zu ändern ist

1. **Nicht mit der Förderung öffnen, sondern mit dem Schmerzpunkt.** Bei den Maklern lief das Kostenargument ins Leere, weil das Problem nie Geld war. Die Förderung ist der letzte Satz des Gesprächs, nicht der erste.
2. **Die Freistellung zuerst lösen, nicht am Schluss.** Nennen Sie von sich aus die Rolle, die freigestellt werden kann: in der Pflege Abrechnung, QM, Verwaltung und stellvertretende PDL statt der Kraft auf der Tour; in der Kanzlei die Lohnbuchhaltung und die Steuerfachangestellte statt des Berufsträgers. Wenn es diese Rolle nicht gibt, beenden Sie das Gespräch selbst.
3. **Nicht „120 Stunden“ sagen, sondern die Lage nennen** – etwa sechs Stunden pro Woche über fünf Monate. Aber ehrlich bleiben: Seit der Fachlichen Weisung mit Stand 01.01.2026 zählen Selbstlern- und E-Learning-Anteile nicht als Unterricht, und der Arbeitsentgeltzuschuss setzt echten Arbeitsausfall mit Entgeltfortzahlung voraus [32], [33]. Das Abendformat als Rettung ist tot. Die Terminarchitektur ist damit Teil des Produkts.
4. **Keine Förderzusage machen.** § 82 SGB III ist Ermessensleistung ohne Rechtsanspruch [45], [32]. „Bis zu 100 %“, nie „Sie bekommen 100 %“ – und den Antrag stellt immer der Arbeitgeber vor Maßnahmebeginn.
5. **Vorqualifizieren statt später scheitern.** Fragen Sie im Erstgespräch nach: Berufsabschluss der Kandidaten mindestens zwei Jahre her, keine § 82-Förderung in den letzten zwei Jahren, keine Azubis, keine Minijobber, Betriebsgröße des **gesamten** Unternehmens inklusive verbundener Betriebe unter 50 [45].
6. **Den KI-VO-Einwand vorbereiten.** Wenn der Kanzleiinhaber sagt „dazu bin ich ohnehin verpflichtet“: Art. 4 der KI-Verordnung ist EU-Recht, der Förderausschluss des § 82 Abs. 1 Satz 2 SGB III greift nur bei bundes- oder landesrechtlichen Pflichten [45]. Umgekehrt den Lehrgang nicht als Pflichtschulung verkaufen – das würde ihn erst recht ausschließen.
7. **Den Kerngeschäftsbezug in den ersten zehn Sekunden herstellen.** Das BVerwG hat am 29.01.2025 entschieden, dass öffentlich zugängliche Telefonnummern keine mutmaßliche Einwilligung nach § 7 Abs. 2 Nr. 1 UWG begründen; es braucht konkrete Anhaltspunkte für ein sachliches Interesse [47], [49]. Die Belegschaftsbelege aus `Enrichment.staff` sind damit nicht nur Förderkriterium, sondern die Begründung des Anrufs.
8. **Sich hörbar von der Callcenter-Masche abgrenzen.** Alle Zielbranchen sind vorbelastet – Pflege durch Zeitarbeitsvermittler, Kanzleien durch Software, Speditionen durch Frachtenbörsen. Agentur für Arbeit, § 82 SGB III und AZAV im ersten Satz zu nennen ist der einzige Unterschied, der im ersten Moment trägt; und rufen Sie in der Pflege niemals die Rufbereitschaftsnummer an [31].

## Quellen

1. https://www.destatis.de/DE/Themen/Branchen-Unternehmen/Unternehmen/Unternehmensregister/Tabellen/betriebe-beschaeftigtengroessenklassen-wz08.html
2. https://datenschutz.immobilien/wie-viele-immobilienmakler-gibt-es-in-deutschland/
3. https://zia-deutschland.de/project/bedeutung-der-immobilienbranche/
4. https://www.gesetze-im-internet.de/hgb/__84.html
5. https://www.ihk.de/hannover/hauptnavigation/recht/gewerberecht/weiterbildungspflicht-fuer-immobilienmakler-faellt-weg-7141450
6. https://iab-forum.de/betriebliche-weiterbildung-in-krisenzeiten-die-erhoffte-trendwende-bleibt-aus/
7. https://www.it-recht-kanzlei.de/handynummer-impressum.html
8. https://www.destatis.de/DE/Themen/Gesellschaft-Umwelt/Gesundheit/Pflege/Tabellen/personal-pflegeeinrichtungen.html
9. https://www.sozialpolitik-aktuell.de/files/sozialpolitik-aktuell/_Politikfelder/Gesundheitswesen/Datensammlung/PDF-Dateien/abbVI56_57.pdf
10. https://statistik.arbeitsagentur.de/DE/Statischer-Content/Statistiken/Themen-im-Fokus/Berufe/Generische-Publikationen/Arbeitsmarktsituation-in-Pflegeberufen.pdf?__blob=publicationFile
11. https://doku.iab.de/kurzber/2026/kb2026-08.pdf
12. https://www.bstbk.de/downloads/bstbk/ebooks/Berufsstatistik-2025.pdf
13. https://www.bstbk.de/downloads/bstbk/recht-und-berufsrecht/fachinfos/02_Sonderauswertungen_Digitalisierung_Fachkraeftemangel_STAX2024.pdf
14. https://www.destatis.de/DE/Themen/Branchen-Unternehmen/Dienstleistungen/Publikationen/Downloads-Dienstleistungen-Branchenberichte/rechts-steuer-unternehmensberatung-5474103187004.pdf?__blob=publicationFile&v=3
15. https://www.destatis.de/DE/Themen/Branchen-Unternehmen/Unternehmen/Unternehmensregister/Tabellen/unternehmen-beschaeftigtengroessenklassen-wz08.html
16. https://www.dslv.org/de/die-branche/umsatz-und-beschaeftigte
17. https://www.bitkom.org/Presse/Presseinformation/Die-Logistik-investiert-in-KI-doch-es-fehlt-Knowhow
18. https://www.kfzgewerbe.de/fileadmin/user_upload/Presse/Pressemeldungen/JPK_2025/2025_ohne_Sperrfrist/Grafik_Betriebe_und_Beschaeftigte_2024.pdf
19. https://www.boeckler.de/fpdf/HBS-006769/p_study_hbs_370.pdf
20. https://www.kzbv.de/wp-content/uploads/Seiten_145_bis_147_KZBVJB2025.pdf
21. https://www.destatis.de/DE/Presse/Pressemitteilungen/2025/07/PD25_269_52911.html
22. https://www.metallinnung.de/konjunkturumfrage-1-2026/
23. https://www.zdh.de/ueber-uns/fachbereich-wirtschaft-energie-umwelt/statistik/handwerkszaehlung/handwerkszaehlung-2024/
24. https://www.zveh.de/news/detailansicht/branchenkennzahlen-2025-fuer-e-handwerke-ein-jahr-der-stagnation-1.html
25. https://www.zvshk.de/presse/shk-handwerk-2025-umsatz-und-auftraege-ruecklaeufig-investitionsstau-bremst-branche
26. https://www.abda.de/fileadmin/user_upload/assets/Faktenblaetter/Faktenblatt_Arbeitgeber.pdf
27. https://bak.de/wp-content/uploads/2026/06/BAK_Die_Vermessung_der_Branche_200426.pdf
27a. https://bak.de/presse/pressemitteilungen/architektenbefragung-2025-ki-teilzeit-und-buerokratie-praegen-den-berufsalltag/
28. https://www.bitkom.org/sites/main/files/2026-01/bitkom-studienbericht-handwerk.pdf
29. https://apo-systeme.de/ratgeber/elnw-2026-pflegedienst
30. https://www.pflegemarkt.com/news/anzahl-statistik-schliessungen-insolvenzen-pflege-2026/
30a. https://www.pflegemarkt.com/fachartikel/top-betreiber/liste-15-groesste-pflegedienste-2026/
31. https://pqsg.de/seiten/openpqsg/mobil/hintergrund-standard-rufbereitschaft.htm
32. https://www.arbeitsagentur.de/datei/dok_ba031590.pdf
33. https://www.akr.services/neue-fachliche-weisung-2026-mit-klarstellung-zur-qualifizierung-beschaeftigter-%C2%A7-82-sgb-iii/
34. https://www.bstbk.de/downloads/bstbk/digitalisierung/BStBK_FAQ-KI_end.pdf
34a. https://www.kfzgewerbe.de/verband/verbandsarbeit/studie-gemeinsam-intelligenter-ki-bringt-mehrwert-ins-kfz-gewerbe
35. https://www.gesetze-im-internet.de/stberg/__57.html
36. https://www.datev.de/web/de/berufsgruppenuebergreifend/ueber-datev/innovation/kuenstliche-intelligenz
37. https://www.destatis.de/DE/Presse/Pressemitteilungen/2026/09/PD26_325_52411.html
38. https://www.balm.bund.de/DE/Themen/Foerderprogramme/Gueterkraftverkehr/Weiterbildung/weiterbildung_node.html
39. https://www.balm.bund.de/DE/Themen/Foerderprogramme/Gueterkraftverkehr/Weiterbildung/W_2026/w26_node.html
40. https://doku.iab.de/kurzber/2026/kb2026-13.pdf
41. https://doku.iab.de/kurzber/2026/kb2026-07.pdf
42. https://www.zdh.de/ueber-uns/fachbereich-wirtschaft-energie-umwelt/statistik/handwerkszaehlung/handwerkszaehlung-2023/
43. https://www.pflegekammer-nrw.de/bildung-und-anerkennung/weiterbildungsordnung/
44. https://developers.google.com/maps/documentation/places/web-service/place-types
45. https://www.gesetze-im-internet.de/sgb_3/__82.html
46. https://www.kzvnr.de/aktuelles/news/detail/verpflichtende-nutzung-der-epa-ab-1-oktober-2025-inklusive-befuellungspflichten-was-zahnarztpraxen-jetzt-wissen-muessen
47. https://www.bverwg.de/290125U6C3.23.0
48. https://www.bitkom.org/sites/main/files/2025-08/bitkom-leitfaden-qcg.pdf
49. https://www.gesetze-im-internet.de/uwg_2004/__7.html
50. https://iab-forum.de/nur-jeder-zehnte-betrieb-nutzt-die-weiterbildungsfoerderung-der-bundesagentur-fuer-arbeit/
51. https://www.arbeitsagentur.de/presse/2025-46-ba-haushalt-2026

Eigene Datenauswertung ohne externe Quelle: `/home/user/scraper/output/de*.jsonl` (13.826 deduplizierte Maklerbetriebe) und `/home/user/scraper/output/hv*.jsonl` (3.169 Hausverwaltungen), ausgewertet nach der Logik von `src/leadscraper/scoring.py::premium_check` und `pilot_bericht.py` am 15.09.2026.