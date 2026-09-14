from leadscraper.extract.impressum import detect_rechtsform, is_impressum_page, parse_impressum

GMBH = """Impressum
Angaben gemäß § 5 DDG
Rheinblick Immobilien GmbH
Rheinuferstraße 12
50667 Köln
Vertreten durch die Geschäftsführer: Thomas Berger, Dr. Anna Schmidt
Kontakt
Telefon: 0221 5550000
E-Mail: info@rheinblick-immobilien.de
Registereintrag
Registergericht: Amtsgericht Köln
Registernummer: HRB 123456
Umsatzsteuer-ID
Umsatzsteuer-Identifikationsnummer gemäß § 27 a UStG: DE 123 456 789
Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV
Thomas Berger
Haftungsausschluss
Haftung für Inhalte
Realisierung
Pixelwerk Digital GmbH, Geschäftsführer: Lena Hoffmann""".split("\n")


def test_gmbh_two_gf_register_ust_address():
    d = parse_impressum(GMBH, "https://x.de/impressum")
    assert d.legal_name == "Rheinblick Immobilien GmbH"
    assert d.rechtsform == "GmbH"
    assert [(p.name, p.role_category) for p in d.people] == [
        ("Thomas Berger", "geschaeftsfuehrung"),
        ("Anna Schmidt", "geschaeftsfuehrung"),
    ]
    assert d.register == "HRB 123456"
    assert d.amtsgericht == "Amtsgericht Köln"
    assert d.ustid == "DE123456789"
    assert (d.street, d.plz, d.city) == ("Rheinuferstraße 12", "50667", "Köln")
    assert all(p.source_url == "https://x.de/impressum" for p in d.people)
    assert not any(p.name == "Lena Hoffmann" for p in d.people)  # Web-Agentur-Block ignoriert


def test_gmbh_co_kg_with_komplementaer_gmbh():
    lines = """Muster Logistik GmbH & Co. KG
Industriestraße 5
44135 Dortmund
Persönlich haftende Gesellschafterin: Muster Verwaltungs GmbH, Sitz Dortmund
diese vertreten durch den Geschäftsführer Klaus Muster
Registergericht: Amtsgericht Dortmund, HRA 9876
Komplementär-GmbH: HRB 5432 B""".split("\n")
    d = parse_impressum(lines)
    assert d.rechtsform == "GmbH & Co. KG"
    assert [(p.name, p.role_category) for p in d.people] == [("Klaus Muster", "geschaeftsfuehrung")]
    assert d.register == "HRA 9876"
    assert d.amtsgericht == "Amtsgericht Dortmund"


def test_einzelunternehmen_inhaberin():
    lines = [
        "Impressum",
        "Elektro Kaminski",
        "Inhaber: Peter Kaminski",
        "Hauptstraße 3",
        "51063 Köln",
        "Tel. 0221 5550789",
    ]
    d = parse_impressum(lines)
    assert d.people[0].name == "Peter Kaminski" and d.people[0].role_category == "inhaber"
    assert d.rechtsform == "Einzelunternehmen"
    assert d.legal_name == "Peter Kaminski"


def test_ag_vorstand_and_aufsichtsrat_ignored():
    lines = """Beispiel Wohnen AG
Vorstand: Maria Vogel (Vorsitzende), Jan Petersen
Aufsichtsratsvorsitzender: Heinrich Alt
Sitz der Gesellschaft: Hamburg
Handelsregister: Amtsgericht Hamburg HRB 112233""".split("\n")
    d = parse_impressum(lines)
    assert [(p.name, p.role_category) for p in d.people] == [
        ("Maria Vogel", "vorstand"),
        ("Jan Petersen", "vorstand"),
    ]
    assert d.rechtsform == "AG"


def test_partg_partner_and_mstv_no_duplicate():
    lines = """Weber & Lind Steuerberater PartG mbB
Partner: Dipl.-Kfm. Markus Weber, Steuerberater; Sonja Lind, Steuerberaterin
Verantwortlich i.S.d. § 18 Abs. 2 MStV: Markus Weber
Partnerschaftsregister: Amtsgericht Essen PR 321""".split("\n")
    d = parse_impressum(lines)
    assert [(p.name, p.role_category) for p in d.people] == [
        ("Markus Weber", "geschaeftsfuehrung"),
        ("Sonja Lind", "geschaeftsfuehrung"),
    ]
    assert d.rechtsform == "PartG mbB"
    assert d.register == "PR 321"


def test_vertreten_durch_names_on_following_lines():
    lines = """Pixelwerk Digital GmbH
Vertreten durch:
Lena Hoffmann
Daniel Schuster
Registergericht: Amtsgericht Köln
Registernummer: HRB 654321""".split("\n")
    d = parse_impressum(lines)
    assert [p.name for p in d.people] == ["Lena Hoffmann", "Daniel Schuster"]


def test_ust_without_spaces_and_berlin_register_suffix():
    d = parse_impressum(
        [
            "Foo UG (haftungsbeschränkt)",
            "Geschäftsführerin: Eva Kurz",
            "HRB 123456 B",
            "USt-IdNr.: DE987654321",
        ]
    )
    assert d.rechtsform == "UG" and d.register == "HRB 123456 B" and d.ustid == "DE987654321"
    assert d.people[0].role == "Geschäftsführerin"


def test_mstv_person_only_as_sonstige_when_new():
    d = parse_impressum(
        ["Foo GmbH", "Geschäftsführer: Max Muster", "Verantwortlich i.S.d. § 55 RStV: Erika Redakteur"]
    )
    assert [(p.name, p.role_category) for p in d.people] == [
        ("Max Muster", "geschaeftsfuehrung"),
        ("Erika Redakteur", "sonstige"),
    ]


def test_detect_rechtsform():
    assert detect_rechtsform("Muster GmbH & Co. KG") == "GmbH & Co. KG"
    assert detect_rechtsform("Muster Verwaltungsgesellschaft mbH") == "GmbH"
    assert detect_rechtsform("Elektro Kaminski e.K.") == "e.K."
    assert detect_rechtsform("Weber & Lind PartG mbB") == "PartG mbB"
    assert detect_rechtsform("Müller und Söhne GbR") == "GbR"
    assert detect_rechtsform("Beispiel AG") == "AG"
    assert detect_rechtsform("Thomas Berger") is None
    assert detect_rechtsform("Musterstraße 12") is None


def test_is_impressum_page():
    assert is_impressum_page("https://x.de/impressum/", [])
    assert is_impressum_page("https://x.de/legal-notice", [])
    assert is_impressum_page("https://x.de/info", ["Impressum", "Foo GmbH", "HRB 1234"])
    assert not is_impressum_page("https://x.de/info", ["Impressum", "Foo GmbH"])
    assert not is_impressum_page("https://x.de/kontakt", ["Kontakt", "Tel 0221 1"])


def test_generic_representation_label_becomes_readable_role():
    """„Vertreten durch“ ist kein Funktionstitel – im Export soll die Funktion stehen."""
    data = parse_impressum(
        ["Muster Immobilien GmbH", "Vertreten durch: Thomas Berger", "HRB 12345"],
        "https://x.de/impressum",
    )
    person = next(p for p in data.people if p.name == "Thomas Berger")
    assert person.role == "Geschäftsführung" and person.role_category == "geschaeftsfuehrung"
    data2 = parse_impressum(["Inhaber: Claudia Sonnenhof"], "https://y.de/impressum")
    assert data2.people[0].role == "Inhaber"  # konkrete Bezeichnung bleibt erhalten


def test_decider_in_footer_after_legal_blocks():
    """Baukästen wiederholen die Geschäftsführung erst im Footer – hinter Haftung/Datenschutz."""
    lines = [
        "Impressum",
        "Ludewig Immobilien GmbH",
        "Musterweg 3",
        "70173 Stuttgart",
        "Vertreten durch:",
        "E-Mail: info@ludewig-immobilien.de",
        "Haftung für Inhalte",
        "Als Diensteanbieter sind wir für eigene Inhalte verantwortlich.",
        "Datenschutzerklärung",
        "Wir verarbeiten Daten nach der DSGVO.",
        "Ludewig Immobilien GmbH",
        "Geschäftsführer: Arne Ludewig",
        "Mobil: +49 (0) 152/29115639",
    ]
    data = parse_impressum(lines, "https://x.de/impressum/")
    assert [(p.name, p.role_category) for p in data.people] == [("Arne Ludewig", "geschaeftsfuehrung")]
    assert data.rechtsform == "GmbH"


def test_street_is_not_read_as_person():
    data = parse_impressum(
        ["Inhaltlich verantwortlich:", "Patrick Hoffmann", "Leidenhausener Str 12", "51147 Köln"],
        "https://y.de/impressum",
    )
    assert [p.name for p in data.people] == ["Patrick Hoffmann"]
