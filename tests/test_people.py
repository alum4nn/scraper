from leadscraper.extract.htmlutil import Link
from leadscraper.extract.people import attach_phones, categorize_role, find_people, merge_people
from leadscraper.models import Person, PhoneNumber


def test_categorize_role():
    assert categorize_role("Geschäftsführerin") == "geschaeftsfuehrung"
    assert categorize_role("Inhaber & Immobilienmakler") == "inhaber"
    assert categorize_role("Leitung Personal") == "hr"
    assert categorize_role("Head of HR") == "hr"
    assert categorize_role("Ausbildungsleiter") == "ausbildung"
    assert categorize_role("Prokuristin") == "prokura"
    assert categorize_role("Niederlassungsleiter Köln") == "betriebsleitung"
    assert categorize_role("Immobilienmaklerin") == "sonstige"
    assert categorize_role(None) == "sonstige"


def test_team_cards_with_roles_and_emails():
    lines = [
        "Unser Team",
        "Thomas Berger",
        "Geschäftsführer",
        "Julia Kranz",
        "Immobilienmaklerin",
        "Anja Roth",
        "Leitung Personal",
        "Kai Sonst",
        "Impressum",
        "Musterstraße 1",
    ]
    links = [
        Link(href="mailto:t.berger@x.de", text="", kind="mailto"),
        Link(href="mailto:kranz@x.de", text="", kind="mailto"),
        Link(href="mailto:info@x.de", text="", kind="mailto"),
    ]
    people = {p.name: p for p in find_people(lines, links, source_url="https://x.de/team", page_kind="team")}
    assert people["Thomas Berger"].role_category == "geschaeftsfuehrung"
    assert people["Thomas Berger"].email == "t.berger@x.de"
    assert (
        people["Julia Kranz"].role == "Immobilienmaklerin"
        and people["Julia Kranz"].role_category == "sonstige"
    )
    assert people["Julia Kranz"].email == "kranz@x.de"
    assert people["Anja Roth"].role_category == "hr"
    assert people["Kai Sonst"].role is None  # Team-Seite: Name ohne Rolle wird aufgenommen


def test_no_roleless_people_on_other_pages():
    lines = ["Referenzen", "Peter Kaminski", "hat uns super beraten", "Sabine Klein", "Geschäftsführerin"]
    people = find_people(lines, [], source_url="https://x.de/referenzen", page_kind="sonstige")
    assert [p.name for p in people] == ["Sabine Klein"]


def test_ansprechpartner_pattern():
    lines = ["Ihr Ansprechpartner: Thomas Berger, Geschäftsführer", "Kontakt: Julia Kranz"]
    people = find_people(lines, [], source_url="https://x.de/objekt/1", page_kind="sonstige")
    assert [(p.name, p.role_category) for p in people] == [
        ("Thomas Berger", "geschaeftsfuehrung"),
        ("Julia Kranz", "sonstige"),
    ]


def test_merge_people_prefers_impressum_role_and_merges_phones():
    m = PhoneNumber(
        raw="0171 5550123", e164="+491715550123", national="0171 5550123", kind="mobile", source="team"
    )
    imp = [Person(name="Thomas Berger", role="Geschäftsführer", role_category="geschaeftsfuehrung")]
    team = [
        Person(
            name="Dipl.-Kfm. Thomas Berger",
            role="Inhaber",
            role_category="inhaber",
            phones=[m],
            email="t@x.de",
        )
    ]
    vcard = [Person(name="thomas berger", phones=[m])]
    merged = merge_people(imp, vcard, team)
    assert len(merged) == 1
    p = merged[0]
    assert p.name == "Thomas Berger" and p.role == "Geschäftsführer"
    assert [ph.e164 for ph in p.phones] == ["+491715550123"]
    assert p.email == "t@x.de"
    assert imp[0].phones == []  # Eingabe unverändert


def test_attach_phones_by_full_name_and_unique_surname():
    people = [Person(name="Thomas Berger", role_category="geschaeftsfuehrung"), Person(name="Julia Kranz")]
    phones = [
        PhoneNumber(
            raw="a", e164="+491715550123", national="a", kind="mobile", source="team", person="Berger"
        ),
        PhoneNumber(
            raw="b", e164="+491725550456", national="b", kind="mobile", source="team", person="Julia Kranz"
        ),
        PhoneNumber(raw="c", e164="+492215550000", national="c", kind="landline", source="impressum"),
        PhoneNumber(
            raw="d", e164="+491725550456", national="d", kind="mobile", source="vcard", person="J. Kranz"
        ),
    ]
    attach_phones(people, phones)
    assert [ph.e164 for ph in people[0].phones] == ["+491715550123"]
    assert [ph.e164 for ph in people[1].phones] == ["+491725550456"]


def test_team_page_ignores_layout_lines_and_slogans():
    """Reale Makler-Seiten: Zwei-Wort-Zeilen in Namensform sind meist Layout, keine Menschen."""
    lines = [
        "Bevorzugte Kontaktart",
        "Bevorzugte Zeit",
        "Stadtbezirk Hörde",
        "Immobilienmakler Dortmund Benninghofen",
        "Mein Konto",
        "Ihr Immobilienmakler in Dortmund, inhabergeführt seit 1968",
        "Kaufinteressenten Registrierung",
        "Eigentümer",
        "Proven Expert",
        "Lädt unsere Bewertungen von Proven Expert (Expert Systems AG).",
        "Backoffice, Fotos",
        "info@doernhoff-immobilien.de",
        "Oliver Penzel",
        "Geprüfter Immobilienmakler mit IHK Zertifikat",
        "Yüksel Turan",  # unbekannter Vorname, aber Kontaktdaten direkt darunter
        "Immobilienberater",
        "Mobil: 0176 5550001",
        "Hanna Stawinoga",  # bekannter Vorname ohne Rolle → auf Team-Seite aufnehmen
    ]
    people = {p.name: p for p in find_people(lines, [], source_url="https://x.de/team", page_kind="team")}
    assert set(people) == {"Oliver Penzel", "Yüksel Turan", "Hanna Stawinoga"}
    assert people["Oliver Penzel"].role_category == "sonstige"
    assert not any(p.role_category == "inhaber" for p in people.values())


def test_eigentuemer_is_customer_segment_not_role():
    assert categorize_role("Für Eigentümer") == "sonstige"
    assert categorize_role("inhabergeführt seit 1968") == "sonstige"
    assert categorize_role("Inhaberin") == "inhaber"
