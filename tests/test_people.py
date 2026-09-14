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
    lines = ["Aktuelles", "Peter Kaminski", "hat uns super beraten", "Sabine Klein", "Geschäftsführerin"]
    people = find_people(lines, [], source_url="https://x.de/aktuelles", page_kind="sonstige")
    assert [p.name for p in people] == ["Sabine Klein"]


def test_nobody_is_taken_from_a_references_block():
    """Unter „Referenzen“ stehen Kunden – auch wenn dort eine Geschäftsführerin genannt wird."""
    lines = ["Referenzen", "Peter Kaminski", "hat uns super beraten", "Sabine Klein", "Geschäftsführerin"]
    assert find_people(lines, [], source_url="https://x.de/referenzen", page_kind="sonstige") == []


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


def test_role_label_line_outside_impressum():
    """Auf Kontaktseiten steht die Funktion oft in derselben Zeile wie der Name."""
    lines = ["Lang Immobilien", "Inhaber: Rainer Lang", "rainer.lang@l-immobilien.de"]
    people = find_people(lines, [], source_url="https://x.de/kontakt", page_kind="kontakt")
    assert [(p.name, p.role_category) for p in people] == [("Rainer Lang", "inhaber")]


def test_owner_named_in_prose_on_about_page():
    lines = [
        "Seit 2007 ist Thomas Steffens Gründer und Inhaber der Steffens & Roth Immobilien Unternehmung.",
        "Seit Ende 2021 verstärkt Sohn Christoph Steffens das Team von insgesamt fünf Mitarbeitern.",
        "Geschäftsführerin Sabine Klein leitet den Innendienst.",
    ]
    found = find_people(lines, [], source_url="https://x.de/ueber-uns", page_kind="team")
    people = {p.name: p for p in found}
    assert people["Thomas Steffens"].role_category in ("inhaber", "geschaeftsfuehrung")
    assert people["Sabine Klein"].role_category == "geschaeftsfuehrung"


def test_staff_from_team_cards_without_running_text():
    """Team-Karten bestehen oft nur aus Foto und Link – die Namen müssen trotzdem gezählt werden."""
    from leadscraper.extract.people import staff_from_links_and_images

    links = [
        Link(href="https://x.de/team/anna-schmidt/", text="", kind="internal"),
        Link(href="https://x.de/team/max-weber/", text="Mehr erfahren", kind="internal"),
        Link(href="https://x.de/team/", text="Zurück zum Team", kind="internal"),
        Link(href="https://x.de/leistungen/bewertung/", text="Immobilienbewertung", kind="internal"),
        Link(href="https://x.de/vcard/lena-fischer.vcf", text="Lena Fischer", kind="vcard"),
    ]
    alts = ["Anna Schmidt", "Tim Brandt, Immobilienkaufmann", "Logo der Firma", "Außenansicht Bürogebäude"]
    people = staff_from_links_and_images(links, alts, source_url="https://x.de/team/")
    assert sorted(p.name for p in people) == ["Anna Schmidt", "Lena Fischer", "Max Weber", "Tim Brandt"]


def test_reviewers_and_partners_are_not_staff():
    """Die häufigste Fehlerquelle laut Prüfung an echten Seiten: Kundenstimmen und Partnerlisten."""
    lines = [
        "Unser Team",
        "Torben Domaser",
        "Immobilienberater",
        "Das sagen unsere Kunden",
        "Patrick Atzor",
        "Sehr gute Beratung, immer erreichbar",
        "Joseph Kachichian",
        "Top Service",
        "Unsere Kooperationspartner",
        "Alexander Tibelius",
        "Elektrotechnik",
        "Ihre Ansprechpartner",
        "Katharina Lilienthal",
        "Vermietung",
        "Freie Mitarbeiter",
        "Bernd Meyer",
        "Repräsentant Rheinland",
    ]
    namen = {p.name for p in find_people(lines, [], source_url="https://x.de/team", page_kind="team")}
    assert namen == {"Torben Domaser", "Katharina Lilienthal"}


def test_review_widget_images_are_not_staff():
    from leadscraper.extract.people import staff_from_links_and_images

    alts = ["Anna Schmidt", "Patrick Atzor profile picture", "ProvenExpert Siegel 4,9 von 5"]
    namen = {p.name for p in staff_from_links_and_images([], alts, source_url="https://x.de/")}
    assert namen == {"Anna Schmidt"}


def test_group_photo_caption_is_not_staff():
    """„v.l.n.r.: …“ unter einem Gruppenfoto zeigt bei Genossenschaften den Aufsichtsrat."""
    lines = [
        "Unser Team",
        "Mandy Schwarz",
        "Sachbearbeiterin",
        "Aufsichtsrat",
        "v.l.n.r.: Hermann Emmerich, Walburga Krahl, Wolfgang Teichmann, Rosemarie Pottin",
    ]
    namen = {p.name for p in find_people(lines, [], source_url="https://x.de/team", page_kind="team")}
    assert namen == {"Mandy Schwarz"}

    from leadscraper.extract.people import staff_from_links_and_images

    alts = ["Anna Schmidt", "v.l.n.r. Hermann Emmerich, Walburga Krahl"]
    gefunden = {p.name for p in staff_from_links_and_images([], alts, source_url="https://x.de/")}
    assert gefunden == {"Anna Schmidt"}
