"""Mitarbeiterzahl schätzen – aus Website-Text, Team-Seite, Rechtsform und (schwach) Google-Bewertungen."""

from __future__ import annotations

import re
from dataclasses import dataclass

from leadscraper.models import SizeEstimate

# Starke Einheiten: Wer „12 Mitarbeiter“ schreibt, meint die Belegschaft.
_STRONG_UNITS = (
    r"mitarbeiter(?:n|innen|\*innen|:innen|_innen|/innen)?|mitarbeitende[nr]?|beschäftigte[nr]?|"
    r"angestellte[nr]?|kolleg(?:en|innen|\*innen|:innen)|teammitglieder[n]?|festangestellte[n]?|"
    r"vollzeitkräfte[n]?|arbeitnehmer(?:n|innen)?"
)
# Schwache Einheiten: Auf einer Makler-Website steht „5 Makler“ auch in Kundenstimmen und
# Vergleichsportalen („1.271 Urteile wurden für die 17 Makler berücksichtigt“). Sie zählen nur mit
# Besitzbezug – „unsere 17 Makler“, „mein Team aus 5 Beratern“.
_WEAK_UNITS = (
    r"fachkräfte[n]?|expert(?:en|innen)|köpfe[n]?|berater(?:n|innen)?|anwält(?:e|en|innen)|"
    r"steuerberater(?:n|innen)?|makler(?:n|innen)?|monteure[n]?|gesellen"
)
_UNITS = rf"{_STRONG_UNITS}|{_WEAK_UNITS}"
_BESITZ = r"(?:unser|unsere[nmrs]?|mein|meine[nmrs]?|im\s+team|team\s+aus|team\s+von)\s+(?:\w+\s+){0,2}"
# „Personen/Leute/Menschen“ nur mit Team-Kontext (s. _PATTERNS), sonst „optimal für 4 Personen“
_TEAM_UNITS = rf"{_UNITS}|leute[n]?|personen|menschen|köpfe[n]?"

_STRONG_UNIT_RE = re.compile(
    r"mitarbeit|beschäftigt|angestellt|kolleg|teammitglied|fachkr|expert|köpfe|berater|anwält|makler|monteur|"
    r"gesellen|arbeitnehmer|vollzeit",
    re.I,
)
_NUM = r"(\d{1,3}(?:[.\s]\d{3})+|\d{1,5})"
_WORDNUMS = {
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fünf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
    "elf": 11,
    "zwölf": 12,
    "fünfzehn": 15,
    "zwanzig": 20,
    "dreißig": 30,
    "vierzig": 40,
    "fünfzig": 50,
    "sechzig": 60,
    "siebzig": 70,
    "achtzig": 80,
    "neunzig": 90,
    "hundert": 100,
}
_WORDNUM = "|".join(_WORDNUMS)
# „weniger als 10 Beschäftigte“ ist eine Obergrenze, keine Belegschaftsgröße – solche Angaben stammen
# meist aus Pflichttexten (Kleinunternehmer, Barrierefreiheit) und dürfen keine Kopfzahl belegen.
_UPPER_BOUND = r"weniger\s+als|unter|maximal|höchstens|nicht\s+mehr\s+als|bis\s+zu"
_QUAL = (
    rf"(?P<qual>über|mehr\s+als|rund|ca\.?|circa|etwa|knapp|fast|nahezu|gut|~|>|inzwischen|mittlerweile|"
    rf"aktuell|derzeit|heute|insgesamt|zurzeit|momentan|{_UPPER_BOUND})?"
)

_PATTERNS = [
    # "zwischen 20 und 30 Mitarbeitern", "20-30 Mitarbeiter", "20 bis 30 Mitarbeiter"
    re.compile(rf"(?:zwischen\s+)?{_NUM}\s*(?:-|–|bis|und)\s*{_NUM}\s+(?:{_UNITS})\b", re.I),
    # "über 100 Mitarbeiter", "rund 40 Mitarbeitende", "12 Kollegen"
    re.compile(
        rf"{_QUAL}\s*{_NUM}\s+(?:erfahrene[n]?\s+|engagierte[n]?\s+|qualifizierte[n]?\s+|"
        rf"motivierte[n]?\s+|feste[n]?\s+)?(?:{_STRONG_UNITS})\b",
        re.I,
    ),
    # "unsere 17 Makler", "mein Team aus 5 Beratern" – schwache Einheiten nur mit Besitzbezug
    re.compile(
        rf"{_BESITZ}{_QUAL}\s*{_NUM}\s+(?:erfahrene[n]?\s+|engagierte[n]?\s+|qualifizierte[n]?\s+|"
        rf"motivierte[n]?\s+|feste[n]?\s+)?(?:{_WEAK_UNITS})\b",
        re.I,
    ),
    # "Team von 12", "Team aus 12 Mitarbeitern", "12-köpfiges Team", "wir sind 8"
    re.compile(
        rf"team\s+(?:von|aus|mit|besteht\s+aus|umfasst|zählt)\s+{_QUAL}\s*(?:{_NUM}|({_WORDNUM}))"
        rf"(?:\s+(?:{_TEAM_UNITS}))?\b",
        re.I,
    ),
    re.compile(rf"{_NUM}[-\s]?köpfige[sn]?\s+team", re.I),
    re.compile(
        rf"wir\s+sind\s+(?:ein\s+team\s+(?:von|aus)\s+)?{_QUAL}\s*{_NUM}(?:\s+(?:{_TEAM_UNITS}))?", re.I
    ),
    # "Mitarbeiterzahl: 25", "Beschäftigte: 48", "Mitarbeiter: ca. 30"
    re.compile(rf"(?:{_UNITS})(?:zahl|anzahl)?\s*:\s*{_QUAL}\s*{_NUM}\b", re.I),
    # Zahlwörter: "zwölf Mitarbeiter"
    re.compile(rf"{_QUAL}\s*(?P<word>{_WORDNUM})\s+(?:{_UNITS})\b", re.I),
]
# Rangangaben/Auszeichnungen: „TOP-5 Makler Köln“, „Platz 3“, „Nr. 1 Makler“, „Top 100 Makler“
_RANK_BEFORE_RE = re.compile(
    r"(?:\btop|\bplatz|\brang|\bnr\.?|#|\bbeste[nr]?|\bkategorie)\s*[-–:]?\s*$", re.I
)
# Bewertungsportale und Quoten: „4,5/5 Mitarbeiter Zufriedenheit“, „100 % Weiterempfehlung“, „4,8 Sterne“
_RATING_RE = re.compile(
    r"\d\s*[.,]\d\s*/\s*\d|\d\s*/\s*5\b|kununu|proven\s?expert|trustpilot|zufriedenheit|"
    r"weiterempfehlung|sterne|bewertungen|erfahrungen|score",
    re.I,
)
_GROUP_RE = re.compile(
    r"weltweit|global|konzern|gruppe|unternehmensgruppe|holding|international|europaweit|bundesweit|deutschlandweit",
    re.I,
)
_ANTI_RE = re.compile(
    r"jahr|seit|kunden|projekt|standort|filial|prozent|%|€|eur\b|stunde|uhr|quadratmeter|m²|referenz|bewertung|"
    r"abt\.|abteilung|aktenzeichen|\baz\.|ordnungsamt|amtsgericht|paragraf|§|"
    r"urteile|berücksichtigt|vergleich|verglichen|getestet|rangliste|ranking|testsieger|"
    r"fahrzeug|objekt|wohnung|einheit|immobilien\s+verkauft|verkauft|vermietet|verwaltet|mio|milliard|umsatz|"
    r"tonnen|kilometer|km\b|artikel|produkte|sterne|stern\b|folge|abonn|likes",
    re.I,
)
_FORM_PRIOR: dict[str, tuple[int, int, int]] = {  # rechtsform -> (min, max, point)
    "e.K.": (1, 9, 4),
    "GbR": (1, 9, 3),
    "Einzelunternehmen": (1, 9, 3),
    "Freiberufler": (1, 9, 3),
    "UG": (1, 9, 3),
    "PartG": (3, 30, 8),
    "PartG mbB": (5, 60, 15),
    "GmbH": (5, 49, 12),
    "gGmbH": (5, 99, 20),
    "GmbH & Co. KG": (10, 99, 30),
    "KG": (5, 49, 15),
    "OHG": (3, 30, 8),
    "eG": (5, 200, 30),
    "e.V.": (1, 50, 8),
    "AG": (50, 5000, 200),
    "SE": (200, 20000, 1000),
    "KGaA": (200, 20000, 1000),
}


@dataclass
class _Hit:
    lo: int
    hi: int
    point: int
    group: bool
    unit_quality: int  # 2 = Mitarbeiter/Beschäftigte, 1 = Team von, 0 = sonstiges
    snippet: str
    url: str


def _to_int(s: str) -> int | None:
    if s.lower() in _WORDNUMS:
        return _WORDNUMS[s.lower()]
    digits = re.sub(r"[.\s]", "", s)
    return int(digits) if digits.isdigit() else None


def _sentence(text: str, start: int, end: int) -> str:
    """Satz (bzw. Zeile) um die Fundstelle – Kontext für Gruppen-/Anti-Muster."""
    lo = max(text.rfind(ch, 0, start) for ch in ".!?\n") + 1
    ends = [text.find(ch, end) for ch in ".!?\n"]
    hi = min((e for e in ends if e != -1), default=len(text))
    return text[max(lo, start - 120) : min(hi, end + 120)]


def _quality(snippet: str) -> int:
    if _STRONG_UNIT_RE.search(snippet):
        return 2
    if re.search(r"team|köpfig|wir\s+sind", snippet, re.I):
        return 1
    return 0


def is_upper_bound(qual: str | None) -> bool:
    """„weniger als 10“, „bis zu 8“ – die Zahl ist eine Obergrenze, der Betrieb kann winzig sein."""
    return bool(qual and re.match(rf"\s*(?:{_UPPER_BOUND})", qual.strip(), re.I))


def _apply_qual(qual: str | None, n: int) -> tuple[int, int, int]:
    q = (qual or "").lower().strip()
    if is_upper_bound(q):
        return 1, n, max(1, n // 2)
    if q.startswith(("über", "mehr", ">", "gut")):
        return n, max(n + 1, int(n * 1.5)), max(n + 1, int(n * 1.2))
    if q.startswith(("knapp", "fast", "nahezu")):
        return max(1, int(n * 0.8)), n, max(1, int(n * 0.9))
    if q.startswith(("rund", "ca", "circa", "etwa", "~")):
        return max(1, int(n * 0.8)), int(n * 1.2) + 1, n
    return n, n, n


def _scan(url: str, text: str) -> list[_Hit]:
    hits: list[_Hit] = []
    spans: list[tuple[int, int]] = []
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            start, end = m.start(), m.end()
            if any(start < e and end > s0 for s0, e in spans):
                continue  # spezifischeres Muster (z. B. Bereich) hat diese Stelle schon erfasst
            window = _sentence(text, start, end)
            snippet = text[max(0, start - 30) : min(len(text), end + 30)].replace("\n", " ").strip()
            groups = m.groups()
            nums = [
                g
                for g in groups
                if g and (g.isdigit() or re.fullmatch(r"\d{1,3}(?:[.\s]\d{3})+", g) or g.lower() in _WORDNUMS)
            ]
            qual = m.groupdict().get("qual")
            if not nums:
                continue
            values = [v for v in (_to_int(n) for n in nums) if v is not None]
            if not values or max(values) > 200_000 or min(values) < 1:
                continue
            if _RANK_BEFORE_RE.search(text[max(0, start - 12) : start]):
                continue
            if _RATING_RE.search(window) or text[max(0, start - 1) : start] in ("/", ","):
                continue  # Bewertung/Quote, keine Kopfzahl
            if len(values) >= 2 and values[0] < values[1]:
                lo, hi, point = values[0], values[1], (values[0] + values[1]) // 2
            else:
                lo, hi, point = _apply_qual(qual, values[0])
            local_anti = _ANTI_RE.search(window)
            unit_direct = re.search(
                rf"\d\s+(?:erfahrene[n]?\s+|engagierte[n]?\s+|qualifizierte[n]?\s+|motivierte[n]?\s+|"
                rf"feste[n]?\s+)?(?:{_UNITS})\b",
                m.group(0),
                re.I,
            )
            if (
                local_anti
                and not unit_direct
                and not re.search(r"team|köpfig|wir\s+sind|zahl\s*:", m.group(0), re.I)
            ):
                continue
            if not unit_direct and len(values) == 1 and 1900 <= values[0] <= 2100:
                continue  # „wir sind 2019 umgezogen“ – Jahreszahl, keine Kopfzahl
            # Jahresangaben ("seit 1998", "1998 gegründet") in unmittelbarer Nähe der Zahl → verwerfen
            if (
                re.search(
                    r"(?:seit|gegründet|gründung|jahr)\D{0,12}$", text[max(0, start - 15) : start], re.I
                )
                and not unit_direct
            ):
                continue
            spans.append((start, end))
            # Eine Obergrenze belegt nichts – Konfidenz absenken, damit sie nicht als Zahl durchgeht
            qualitaet = 1 if is_upper_bound(qual) else _quality(m.group(0))
            hits.append(_Hit(lo, hi, point, bool(_GROUP_RE.search(window)), qualitaet, snippet, url))
    return hits


def _evidence(hit: _Hit) -> str:
    tag = " (Gruppe/weltweit)" if hit.group else ""
    return f"Text: „{hit.snippet}“{tag} ({hit.url})"


def is_rating_text(text: str) -> bool:
    """Stammt eine gespeicherte Fundstelle aus einer Portalbewertung statt aus einer Mitarbeiterangabe?"""
    return bool(_RATING_RE.search(text))


_EVIDENCE_SNIPPET_RE = re.compile(r"„(.+?)“")


def evidence_still_holds(evidence: str) -> bool:
    """Trägt eine gespeicherte Fundstelle die Kopfzahl auch nach den heutigen Regeln noch?

    So wirken Verschärfungen an der Texterkennung (Aktenzeichen, Vergleichsportale, schwache
    Berufsbezeichnungen) auch auf bereits ausgewertete Läufe, ohne jede Website erneut zu laden.
    """
    if not evidence.startswith("Text:"):
        return True  # Indizien-Belege (Namen, Postfächer, Durchwahlen) prüft count_staff selbst
    treffer = _EVIDENCE_SNIPPET_RE.search(evidence)
    if not treffer:
        return True
    return bool(_scan("", treffer.group(1)))


def headcount_from_indicators(
    team_member_count: int | None, staff_mailboxes: int | None, staff_phones: int | None
) -> tuple[int, str] | None:
    """Belegte Köpfe ohne Zahlenangabe auf der Website: namentliche Mitarbeitende, persönliche
    Postfächer (vorname.nachname@) und eigene Durchwahlen. Rückgabe: (Anzahl, Beleg) oder None."""
    candidates = [
        (team_member_count or 0, "{n} namentliche Mitarbeitende auf Team-/Kontaktseiten"),
        (staff_mailboxes or 0, "{n} persönliche E-Mail-Postfächer (vorname.nachname@)"),
        (staff_phones or 0, "{n} Personen mit eigener Telefonnummer/Durchwahl"),
    ]
    best, template = max(candidates, key=lambda c: c[0])
    if best < 2:
        return None
    return best, template.format(n=best)


def estimate_size(
    pages: list[tuple[str, str]],
    *,
    team_member_count: int | None = None,
    staff_mailboxes: int | None = None,
    staff_phones: int | None = None,
    rechtsform: str | None = None,
    user_rating_count: int | None = None,
) -> SizeEstimate:
    hits: list[_Hit] = []
    for url, text in pages:
        hits.extend(_scan(url, text or ""))

    local = [h for h in hits if not h.group]
    chosen: _Hit | None = None
    if local:
        best_q = max(h.unit_quality for h in local)
        cands = sorted((h for h in local if h.unit_quality == best_q), key=lambda h: h.point)
        chosen = cands[len(cands) // 2]  # Median
        est = SizeEstimate(
            employees_min=chosen.lo,
            employees_max=chosen.hi,
            point_estimate=chosen.point,
            confidence="high" if best_q == 2 else "medium",
        )
    elif hits:
        cands = sorted(hits, key=lambda h: h.point)
        chosen = cands[len(cands) // 2]
        est = SizeEstimate(
            employees_min=chosen.lo, employees_max=chosen.hi, point_estimate=chosen.point, confidence="medium"
        )
    else:
        est = SizeEstimate()

    evidence = [_evidence(h) for h in ([chosen] if chosen else [])]
    evidence += [_evidence(h) for h in hits if h is not chosen][:4]
    est.evidence = evidence[:5]

    indicator = headcount_from_indicators(team_member_count, staff_mailboxes, staff_phones)
    if chosen is None and indicator is not None:
        # Namentliche Mitarbeitende sind die Untergrenze: Innendienst/Backoffice steht selten auf der Website.
        n, why = indicator
        # Untergrenze: Innendienst, Buchhaltung und Azubis stehen fast nie auf der Website. Die Obergrenze
        # bleibt deshalb weit – die Schätzung soll niemanden ausschließen, nur einordnen.
        est = SizeEstimate(
            employees_min=n,
            employees_max=max(12, round(n * 2.5)),
            point_estimate=max(n, round(n * 1.4)),
            confidence="medium" if n >= 3 else "low",
            evidence=[f"Indiz: {why} (mindestens so viele Beschäftigte)"],
        )
    elif chosen is None and rechtsform in _FORM_PRIOR:
        lo, hi, point = _FORM_PRIOR[rechtsform]
        est = SizeEstimate(
            employees_min=lo,
            employees_max=hi,
            point_estimate=point,
            confidence="low",
            evidence=[f"Rechtsform {rechtsform} (typische Größe {lo}–{hi})"],
        )
    elif chosen is None and user_rating_count is not None:
        if user_rating_count < 10:
            lo, hi, point = 1, 9, 3
        elif user_rating_count <= 100:
            lo, hi, point = 3, 30, 8
        else:
            lo, hi, point = 10, 100, 25
        est = SizeEstimate(
            employees_min=lo,
            employees_max=hi,
            point_estimate=point,
            confidence="low",
            evidence=[f"{user_rating_count} Google-Bewertungen (schwaches Signal)"],
        )
    if chosen is not None and indicator is not None:
        est.evidence.append(f"Indiz: {indicator[1]}")
    return est
