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
