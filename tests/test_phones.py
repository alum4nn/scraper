from leadscraper.extract.htmlutil import Link
from leadscraper.extract.phones import classify_number, find_phones, parse_vcard, parse_whatsapp_link
from leadscraper.models import Person


def _phones(lines, links=(), known=None, source="team"):
    return find_phones(
        list(lines), list(links), source=source, source_url="https://x.de/p", known_people=known
    )


def test_classify_number_kinds():
    assert classify_number("0171 5550123").kind == "mobile"
    assert classify_number("+49 (0) 221 5550000").kind == "landline"
    assert classify_number("0221/55 50 00 0").e164 == "+492215550000"
    assert classify_number("0800 1234567").kind == "unknown"
    assert classify_number("12345") is None
    assert classify_number("Musterstraße 12") is None
    assert classify_number("0171 5550123").national == "0171 5550123"


def test_makler_team_card_mobile_attributed_to_decider():
    known = [Person(name="Thomas Berger", role_category="geschaeftsfuehrung")]
    lines = [
        "Unser Team",
        "Thomas Berger",
        "Geschäftsführer",
        "Tel.: 0221 5550000",
        "Mobil: 0171 5550123",
        "Julia Kranz",
        "Immobilienmaklerin",
        "Mobil 0172 5550456",
        "E-Mail: kranz@x.de",
    ]
    result = {p.e164: p for p in _phones(lines, known=known)}
    assert result["+491715550123"].kind == "mobile"
    assert result["+491715550123"].person == "Thomas Berger"
    assert result["+491715550123"].label == "Mobil"
    assert result["+492215550000"].kind == "landline"
    assert result["+492215550000"].person == "Thomas Berger"
    assert result["+491725550456"].person == "Julia Kranz"


def test_handwerker_line_with_two_numbers_and_fax():
    lines = ["Tel. 0221/5550789 · Mobil 0176-5550321 · Fax 0221/5550790"]
    result = _phones(lines, source="kontakt")
    assert {p.e164 for p in result} == {"+492215550789", "+491765550321"}
    mobile = next(p for p in result if p.kind == "mobile")
    assert mobile.label == "Mobil" and mobile.source == "kontakt"


def test_label_on_previous_line_and_international_format():
    lines = ["Mobil", "+49 (0) 171 5550123", "WhatsApp:", "0151 22334455"]
    result = {p.e164: p for p in _phones(lines)}
    assert result["+491715550123"].label == "Mobil"
    assert result["+4915122334455"].label == "WhatsApp"


def test_false_positives_excluded():
    lines = [
        "IBAN DE02 1203 0000 0000 2020 51",
        "Handelsregister: HRB 0123456 B",
        "USt-IdNr.: DE 012345678",
        "Steuernummer 0215/5555/0123",
        "Stand: 12.03.2024",
        "Musterstraße 12, 01067 Dresden",
        "Tel. 0351 5550000",
    ]
    result = _phones(lines, source="impressum")
    assert [p.e164 for p in result] == ["+493515550000"]


def test_tel_link_and_whatsapp_link():
    links = [
        Link(href="tel:+49 171 5550123", text="Jetzt anrufen", kind="tel"),
        Link(href="tel:0221%205550000", text="Zentrale", kind="tel"),
        Link(href="https://wa.me/491765550321?text=Hallo", text="WhatsApp", kind="whatsapp"),
        Link(href="https://api.whatsapp.com/send?phone=4915155509991", text="Chat", kind="whatsapp"),
    ]
    result = {
        p.e164: p for p in _phones(["Ihr Ansprechpartner: Peter Kaminski", "Mobil 0171 5550123"], links)
    }
    assert result["+491715550123"].person == "Peter Kaminski"  # tel-Link auf Nummer im Text
    assert result["+491715550123"].label == "Mobil"
    assert result["+492215550000"].kind == "landline" and result["+492215550000"].label == "Tel"
    assert result["+491765550321"].source == "whatsapp" and result["+491765550321"].kind == "mobile"
    assert result["+4915155509991"].label == "WhatsApp"


def test_whatsapp_link_parsing():
    assert parse_whatsapp_link("https://wa.me/491715550123") == "+491715550123"
    assert parse_whatsapp_link("https://wa.me/message/ABCDEF") is None
    assert parse_whatsapp_link("whatsapp://send?phone=%2B491715550123") == "+491715550123"
    assert parse_whatsapp_link("https://example.de") is None


def test_unknown_person_nearest_name_before_number():
    lines = [
        "Ansprechpartner",
        "Sonja Lind",
        "Steuerberaterin",
        "0151 55509991",
        "Anja Roth",
        "Leitung Personal",
        "0221 5550001",
    ]
    result = {p.e164: p for p in _phones(lines)}
    assert result["+4915155509991"].person == "Sonja Lind"
    assert result["+492215550001"].person == "Anja Roth"


def test_dedupe_prefers_entry_with_person():
    lines = ["Zentrale: 0221 5550000", "Thomas Berger", "Durchwahl 0221 5550000"]
    result = _phones(lines)
    assert len(result) == 1 and result[0].person == "Thomas Berger"


def test_parse_vcard_cell_and_folding():
    vcf = (
        "BEGIN:VCARD\r\nVERSION:3.0\r\nN:Berger;Thomas;;Dipl.-Kfm.;\r\nFN:Dipl.-Kfm. Thomas Berger\r\n"
        "TITLE:Geschäftsführer\r\nORG:Rheinblick Immobilien GmbH\r\nTEL;TYPE=WORK,VOICE:+49 221 5550000\r\n"
        "TEL;TYPE=CELL:+49 171\r\n  5550123\r\nTEL;TYPE=FAX:+49 221 5550001\r\n"
        "EMAIL:t.berger@x.de\r\nEND:VCARD\r\n"
        "BEGIN:VCARD\r\nVERSION:2.1\r\nFN:Julia Kranz\r\nTEL;CELL:0172 5550456\r\nEND:VCARD\r\n"
    )
    people = parse_vcard(vcf, "https://x.de/berger.vcf")
    assert [p.name for p in people] == ["Thomas Berger", "Julia Kranz"]
    tb = people[0]
    assert tb.role_category == "geschaeftsfuehrung" and tb.email == "t.berger@x.de"
    assert {p.e164 for p in tb.phones} == {"+492215550000", "+491715550123"}
    assert tb.mobile.e164 == "+491715550123" and tb.mobile.person == "Thomas Berger"
    assert people[1].mobile.e164 == "+491725550456"


def test_number_with_en_dash_separator_is_found():
    """„Telefon: 02 21 – 160 37 0“ (Gedankenstrich statt Bindestrich) muss erkannt werden."""
    result = _phones(["Telefon: 02 21 – 160 37 0", "Telefax: 02 21 – 160 37 30"], source="impressum")
    assert [p.e164 for p in result] == ["+49221160370"]


def test_mobile_not_attributed_to_layout_text():
    """Ohne bekannte Person wird eine Nummer nur einem plausiblen Namen zugeordnet."""
    lines = ["Immobilienbewertung Frechen", "Mobil: 0176 5550002", "Anna Heck", "Mobil: 0176 5550003"]
    result = {p.e164: p.person for p in _phones(lines)}
    assert result["+491765550002"] is None
    assert result["+491765550003"] == "Anna Heck"


def test_surname_in_email_does_not_attribute_the_number():
    """„brandes@brandes-immobilien.de“ enthält den Nachnamen – das ist keine Personenzuordnung."""
    known = [Person(name="Robin Brandes", role_category="geschaeftsfuehrung")]
    lines = ["Kontakt", "Schreiben Sie an brandes@brandes-immobilien.de", "Mobil: 0171 6444518"]
    result = {p.e164: p.person for p in _phones(lines, known=known)}
    assert result["+491716444518"] is None


def test_same_surname_twice_is_not_guessed():
    """Familienbetrieb: ohne Vornamen neben der Nummer bleibt die Zuordnung offen."""
    known = [
        Person(name="Robin Brandes", role_category="geschaeftsfuehrung"),
        Person(name="Ralf Brandes", role_category="prokura"),
    ]
    ambig = _phones(["Brandes Immobilien", "Mobil: 0171 6444518"], known=known)
    assert ambig[0].person is None
    # Mit vollem Namen in der Zeile ist es eindeutig
    klar = _phones(["Ralf Brandes, Prokurist", "Mobil: 0171 6444518"], known=known)
    assert klar[0].person == "Ralf Brandes"


def test_notdienstnummer_wird_keiner_person_zugeordnet():
    """27 von 237 geprüften „Entscheider-Handys“ trugen das Label Notdienst – die Bereitschaftsnummer
    des Chefs ist für einen Verkaufsanruf die falsche Nummer, auch wenn sein Name daneben steht."""
    from leadscraper.extract.phones import find_phones

    lines = ["Max Müller Geschäftsführer", "Notdienst: 0171 5550123", "Mobil: 0172 5550124"]
    phones = find_phones(lines, [], source="kontakt", source_url="https://x.de/kontakt")
    by_num = {p.national: p for p in phones}
    assert by_num["0171 5550123"].label == "Notdienst" and by_num["0171 5550123"].person is None
    assert by_num["0172 5550124"].person == "Max Müller"


def test_notdienst_in_der_zeile_darueber_sperrt_ebenfalls():
    from leadscraper.extract.phones import find_phones

    lines = ["Thomas Berg Inhaber", "24h Störungsdienst", "0160 5550125"]
    phones = find_phones(lines, [], source="kontakt", source_url="https://x.de/k")
    assert phones and phones[0].label == "Notdienst" and phones[0].person is None


def test_agenturblock_gibt_keine_personennummern():
    """Realisierung/Webdesign im Impressum: Die Nummern darunter gehören der Agentur, nicht dem Betrieb."""
    from leadscraper.extract.phones import find_phones

    lines = [
        "Anna Weber Geschäftsführerin",
        "Realisierung: Pixelwerk GmbH",
        "Jonas Klein",
        "Tel 0173 5550126",
    ]
    phones = find_phones(lines, [], source="impressum", source_url="https://x.de/impressum")
    assert phones[0].label == "Dienstleister" and phones[0].person is None


def test_whatsapp_kopfnummer_nur_bei_name_in_derselben_zeile():
    """WhatsApp-Nummern stehen im Seitenkopf als Firmennummer; ein Name zwei Zeilen darüber macht sie
    nicht zum Handy des Chefs (25 von 237 geprüften Fällen)."""
    from leadscraper.extract.phones import find_phones

    lines = ["Karl Vogt Inhaber", "Öffnungszeiten Mo–Fr 8–17 Uhr", "WhatsApp 0176 5550127"]
    phones = find_phones(lines, [], source="startseite", source_url="https://x.de/")
    assert phones[0].label == "WhatsApp" and phones[0].person is None
    lines = ["Karl Vogt Inhaber WhatsApp 0176 5550127"]
    phones = find_phones(lines, [], source="startseite", source_url="https://x.de/")
    assert phones[0].person == "Karl Vogt"


def test_telefonzentrale_und_datenschutzbeauftragter_geben_keine_personennummer():
    """„Telefonzentrale 0171 …“ neben dem Namen des Chefs ist die Firmennummer; der externe
    Datenschutzbeauftragte im Impressum gehört nicht zum Betrieb (Prüfung 17.09.2026)."""
    from leadscraper.extract.phones import find_phones

    lines = ["Tilo Keubler Geschäftsführung", "Telefonzentrale 0171 2020508"]
    phones = find_phones(lines, [], source="kontakt", source_url="https://x.de/k")
    assert phones[0].label == "Zentrale" and phones[0].person is None
    lines = ["Michael Eidenmüller Geschäftsführer", "Datenschutzbeauftragter: Jan Roth", "Mobil 0170 5550128"]
    phones = find_phones(lines, [], source="impressum", source_url="https://x.de/i")
    assert phones[0].label == "Dienstleister" and phones[0].person is None
