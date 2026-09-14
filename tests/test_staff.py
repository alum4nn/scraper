from leadscraper.extract.staff import count_staff, extension_count, personal_mailboxes
from leadscraper.models import Person, PhoneNumber


def _phone(number: str, kind: str = "landline", source: str = "kontakt") -> PhoneNumber:
    return PhoneNumber(raw=number, e164=number, national=number, kind=kind, source=source)


def test_personal_mailboxes_ignores_role_addresses():
    people = [Person(name="Anna Schmidt"), Person(name="Max Weber")]
    mails = [
        "info@x.de",
        "buchhaltung@x.de",
        "karriere@x.de",
        "a.schmidt@x.de",
        "max.weber@x.de",
        "tim.brandt@x.de",
        "schmidt@x.de",  # dieselbe Person wie a.schmidt@ → eine Identität
    ]
    found = personal_mailboxes(mails, people)
    assert sorted(found) == ["brandt", "schmidt", "weber"]


def test_extensions_need_a_shared_trunk():
    """Mehrere Nummern unter einem Anschluss sind eigene Arbeitsplätze, verstreute Nummern nicht."""
    phones = [_phone(f"+4922155501{i}") for i in range(1, 6)]
    count, evidence = extension_count(phones)
    assert count == 5 and "Durchwahlen" in evidence
    fremd = [_phone("+492215550011"), _phone("+4930999888777"), _phone("+498912345678")]
    assert extension_count(fremd)[0] == 0
    # Google-Nummern zählen nicht mit, sie stammen nicht von der Website
    assert extension_count([_phone("+492215550011", source="places")])[0] == 0


def test_headcount_merges_identities_instead_of_adding_them():
    people = [Person(name="Anna Schmidt"), Person(name="Max Weber"), Person(name="Lena Fischer")]
    mails = ["info@x.de", "a.schmidt@x.de", "max.weber@x.de", "l.fischer@x.de"]
    evidence = count_staff(people, mails, [])
    assert evidence.named == 3 and evidence.mailboxes == 3
    assert evidence.headcount == 3  # dieselben drei Menschen, nicht sechs

    mit_weiteren = count_staff(people, [*mails, "tim.brandt@x.de", "nina.koch@x.de"], [])
    assert mit_weiteren.headcount == 5


def test_stated_number_wins_and_is_first_evidence():
    evidence = count_staff(
        [Person(name="Anna Schmidt")],
        ["a.schmidt@x.de"],
        [],
        stated=14,
        stated_evidence="Text: „Team aus 14 Mitarbeitern“ (https://x.de/)",
    )
    assert evidence.headcount == 14 and evidence.stated == 14
    assert evidence.evidence[0].startswith("Text: „Team aus 14")


def test_empty_input_is_zero():
    assert count_staff([], [], []).headcount == 0


def test_decision_makers_count_as_staff():
    """Auch der Chef arbeitet im Betrieb – er gehört in die Kopfzahl."""
    from leadscraper.models import Person as P

    gf = P(name="Robin Brandes", role="Inhaber & Geschäftsführer", role_category="inhaber")
    prokurist = P(name="Ralf Brandes", role="Prokurist", role_category="prokura")
    team = [P(name="Bianca Bertram"), P(name="Timo Tchoulah"), P(name="Dirk Krause")]
    evidence = count_staff(team, [], [], all_people=[gf, prokurist, *team])
    # drei aus dem Team plus die Familie Brandes – gleicher Nachname zählt nur einmal
    assert evidence.headcount == 4
    # Ohne Funktion im Betrieb zählt eine Person aus dem Impressum nicht mit
    datenschutz = P(name="Jens Wagner", role="Datenschutzbeauftragter", role_category="sonstige")
    assert count_staff(team, [], [], all_people=[datenschutz, *team]).headcount == 3


def test_self_employed_partners_do_not_count():
    """§ 82 SGB III fördert keine Selbstständigen – ihre Rollenbezeichnung schließt sie aus."""
    from leadscraper.models import Person as P

    team = [
        P(name="Ralf Hilger", role="selbständiger Immobilienmakler"),
        P(name="Klaus Schmitz", role="selbstständiger Immobilienmakler"),
        P(name="Bernd Meyer", role="Freier Mitarbeiter, Repräsentant Rheinland"),
        P(name="Anna Weber", role="Immobilienkauffrau"),
        P(name="Tim Brandt", role="Innendienst"),
    ]
    evidence = count_staff(team, [], [])
    assert evidence.headcount == 2
    assert "Anna Weber" in evidence.evidence[0] and "Tim Brandt" in evidence.evidence[0]
