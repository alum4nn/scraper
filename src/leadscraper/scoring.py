"""Lead-Score (0-100): Wie gut lässt sich diese Firma terminieren?"""

from __future__ import annotations

from leadscraper.models import Lead, SearchSpec

_DECIDERS = {"geschaeftsfuehrung", "inhaber", "vorstand"}


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
            score += 40
            reasons.append(f"Entscheider mit Handy: {decider_with_mobile.name}")
        elif mobiles:
            if est is not None and est <= 10:
                score += 30
                reasons.append("Handynummer (Kleinbetrieb – vermutlich Inhaber)")
            else:
                score += 25
                reasons.append("Handynummer ohne Namenszuordnung")
        if deciders and not decider_with_mobile:
            score += 15
            reasons.append(f"Entscheider bekannt: {deciders[0].name}")
        if hr:
            score += 10
            reasons.append(f"HR/Ausbildung: {hr[0].name}")

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
            score += 5
            reasons.append("E-Mail")
        if enr.linkedin_url or enr.xing_url:
            score += 3
            reasons.append("LinkedIn/XING")

    return max(0, min(100, score)), reasons


def sort_key(lead: Lead) -> tuple:
    return (-lead.score, lead.company.name.lower())
