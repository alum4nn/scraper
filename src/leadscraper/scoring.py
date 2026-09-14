"""Lead-Score (0-100): Wie gut lässt sich diese Firma terminieren?"""

from __future__ import annotations

from leadscraper.models import Lead, SearchSpec

_DECIDERS = {"geschaeftsfuehrung", "inhaber", "vorstand"}
_OWNER_FORMS = {"e.K.", "GbR", "Einzelunternehmen", "Freiberufler", "PartG mbB", "PartG"}


def _surname(name: str) -> str:
    tokens = [t for t in name.replace(",", " ").split() if t and not t.endswith(".")]
    return tokens[-1].lower() if tokens else ""


def owner_signal(lead: Lead) -> str | None:
    """Inhabergeführt? Nachname eines Entscheiders im Firmennamen oder personenbezogene Rechtsform."""
    enr = lead.enrichment
    if not enr:
        return None
    haystack = " ".join(filter(None, [lead.company.name, enr.legal_name])).lower()
    for p in enr.decision_makers:
        if p.role_category not in _DECIDERS:
            continue
        sn = _surname(p.name)
        if len(sn) >= 4 and sn in haystack:
            return f"inhabergeführt: „{p.name}“ im Firmennamen"
    if enr.rechtsform in _OWNER_FORMS:
        return f"inhabergeführt: Rechtsform {enr.rechtsform}"
    return None


def in_target_size(lead: Lead, spec: SearchSpec) -> bool | None:
    if not lead.enrichment:
        return None
    return lead.enrichment.size.in_range(spec.min_employees, spec.max_employees)


def score_lead(lead: Lead, spec: SearchSpec) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    enr = lead.enrichment
    company = lead.company

    if company.business_status and company.business_status != "OPERATIONAL":
        score -= 40
        reasons.append(f"Google-Status {company.business_status}")

    if not company.website:
        score -= 20
        reasons.append("keine Website")
    elif enr and not enr.pages_crawled:
        score -= 20
        reasons.append("Website nicht erreichbar")

    if enr:
        deciders = [p for p in enr.decision_makers if p.role_category in _DECIDERS]
        hr = [p for p in enr.decision_makers if p.role_category in ("hr", "ausbildung")]
        mobiles = enr.mobiles
        decider_with_mobile = next((p for p in deciders if p.mobile), None)
        est = enr.size.point_estimate or enr.size.employees_max

        if decider_with_mobile:
            score += 50
            reasons.append(f"Entscheider mit Handy: {decider_with_mobile.name}")
        elif mobiles:
            if est is not None and est <= 10:
                score += 25
                reasons.append("Handynummer (Kleinbetrieb – vermutlich Inhaber)")
            else:
                score += 20
                reasons.append("Handynummer ohne Namenszuordnung")
        if deciders and not decider_with_mobile:
            score += 10
            reasons.append(f"Entscheider bekannt: {deciders[0].name}")
        if hr:
            score += 5
            reasons.append(f"HR/Ausbildung: {hr[0].name}")
        owner = owner_signal(lead)
        if owner:
            score += 10 if mobiles else 5
            reasons.append(owner)

        fit = enr.size.in_range(spec.min_employees, spec.max_employees)
        conf = enr.size.confidence
        if fit is True:
            bonus = {"high": 20, "medium": 12, "low": 5}.get(conf, 0)
            score += bonus
            reasons.append(f"Größe passt ({est} MA, {conf})")
        elif fit is False:
            malus = {"high": 30, "medium": 15, "low": 5}.get(conf, 0)
            score -= malus
            reasons.append(f"Größe außerhalb ({enr.size.employees_min}-{enr.size.employees_max} MA, {conf})")
        else:
            reasons.append("Größe unbekannt")

        if enr.emails:
            score += 3
            reasons.append("E-Mail")
        if enr.linkedin_url or enr.xing_url:
            score += 2
            reasons.append("LinkedIn/XING")

    return max(0, min(100, score)), reasons


def sort_key(lead: Lead) -> tuple:
    return (-lead.score, lead.company.name.lower())


def premium_check(lead: Lead, spec: SearchSpec) -> list[str]:
    """Premium = sofort terminierbar. Liefert die Liste der NICHT erfüllten Kriterien (leer = Premium).

    Kriterien:
    1. Betrieb aktiv (Google-Status OPERATIONAL oder unbekannt) und Website erreichbar
    2. Entscheider (Geschäftsführung/Inhaber/Vorstand) aus dem Impressum bekannt
    3. Handynummer namentlich diesem Entscheider zugeordnet (Team-/Objektseite, vCard, tel:-Link) –
       eine anonyme Firmen-Handynummer reicht nicht
    4. Mitarbeiterzahl belegt (explizite Angabe oder Team-Seite, Konfidenz hoch/mittel) und im Zielbereich
    """
    missing: list[str] = []
    company = lead.company
    enr = lead.enrichment
    if company.business_status and company.business_status != "OPERATIONAL":
        missing.append(f"Google-Status {company.business_status}")
    if not enr or not enr.pages_crawled:
        missing.append("Website nicht erreichbar/keine Website")
        return missing
    deciders = [p for p in enr.decision_makers if p.role_category in _DECIDERS]
    if not deciders:
        missing.append("kein Entscheider im Impressum erkannt")
    elif not any(p.mobile for p in deciders):
        missing.append("keine Handynummer namentlich beim Entscheider")
    size = enr.size
    if size.confidence not in ("high", "medium"):
        missing.append("Mitarbeiterzahl nicht belegt")
    elif size.in_range(spec.min_employees, spec.max_employees) is not True:
        missing.append(f"Mitarbeiterzahl außerhalb {spec.min_employees}–{spec.max_employees}")
    return missing
