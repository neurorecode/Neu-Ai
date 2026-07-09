"""Tamil / English / Tanglish detection.

Three-way classification of a text span:
  - "tamil"    : written predominantly in Tamil script (U+0B80-U+0BFF)
  - "english"  : Latin script, no romanized-Tamil markers
  - "tanglish" : code-mixed — Tamil script mixed with Latin, or romanized
                 Tamil words written in Latin script (e.g. "seri", "panrom")
"""

import re
from collections import Counter

TAMIL_BLOCK = re.compile(r"[஀-௿]")
LATIN_WORD = re.compile(r"[A-Za-z']+")

# Frequent Tamil words/particles as they appear when romanized. Matching any of
# these inside Latin text is a strong signal of Tanglish. Kept lowercase.
ROMAN_TAMIL_WORDS = {
    "vanakkam", "nandri", "seri", "sari", "illa", "illai", "iruku", "irukku",
    "irukken", "irukkum", "venum", "vendam", "veno", "enna", "yenna", "epdi",
    "eppadi", "yaru", "yaar", "enga", "enga", "inga", "anga", "appo", "ippo",
    "aana", "aprom", "apram", "podu", "pannu", "panna", "pannunga", "panrom",
    "panren", "pannalam", "mudiyum", "mudiyala", "mudichu", "sollu", "sollunga",
    "solren", "pesalam", "pesu", "paru", "paaru", "paakalam", "parkalam",
    "vaanga", "vanga", "poganum", "polam", "poitu", "vandhu", "vantha",
    "konjam", "romba", "rombha", "nalla", "nallairuku", "super", "semma",
    "machan", "machi", "thala", "anna", "akka", "thambi", "amma", "appa",
    "naan", "naanga", "neenga", "ninga", "avan", "aval", "avanga", "adhu",
    "idhu", "andha", "indha", "onnu", "rendu", "moonu", "naalu", "anju",
    "velai", "vela", "kaasu", "panam", "veedu", "ooru", "saptiya", "sapadu",
    "saptu", "thookam", "kandippa", "kandipa", "nija", "nijama", "unmai",
    "porumai", "kavala", "kavalai", "santhosham", "magizhchi", "vazhthukkal",
    "aagum", "aagudhu", "aaguthu", "aachu", "achu", "aayidum", "aayiduchu",
    "bodhu", "podhu", "pothu", "appuram", "ellarum", "ellam", "elaam",
    "innum", "ippove", "kulla", "kudunga", "kudu", "vaangikko", "eduthukko",
    "mudichitten", "mudichiduven", "panniduven", "pannuren", "panniyacha",
    "pannitiya", "irundhuchu", "irundha", "irundhen", "pesanum", "sollanum",
    "paakanum", "seiyanum", "edhavadhu", "yedhavadhu", "edhuvum", "onnum",
    "vera", "vere", "matha", "adutha", "porandhu", "varen", "varuven",
    "vanthutan", "poren", "poven", "polama", "seekiram", "metuva", "nikka",
    "da", "di", "pa", "ma", "nga", "la", "ku", "oda", "kitta", "kooda",
    "mattum", "than", "dhan", "thaan", "dhaan", "um", "ah", "nu", "nnu",
}

# Short particles that are too ambiguous alone; require >=2 distinct hits
# or one strong (longer) word before calling it Tanglish.
WEAK_MARKERS = {"da", "di", "pa", "ma", "la", "ku", "um", "ah", "nu", "than", "oda"}


def detect_language(text: str) -> str:
    """Classify a text span as tamil / english / tanglish."""
    if not text or not text.strip():
        return "english"

    tamil_chars = len(TAMIL_BLOCK.findall(text))
    latin_words = [w.lower() for w in LATIN_WORD.findall(text)]

    if tamil_chars and latin_words:
        return "tanglish"
    if tamil_chars:
        return "tamil"
    if not latin_words:
        return "english"

    hits = {w for w in latin_words if w in ROMAN_TAMIL_WORDS}
    strong_hits = hits - WEAK_MARKERS
    if strong_hits or len(hits) >= 2:
        # Mostly-Tamil-in-Latin vs a sprinkle of Tamil in English — both are
        # code-mixed from the product's point of view.
        return "tanglish"
    return "english"


def dominant_language(languages: list[str]) -> str:
    """Roll segment-level labels up to a meeting-level label."""
    if not languages:
        return "english"
    counts = Counter(languages)
    if len(counts) == 1:
        return next(iter(counts))
    if counts.get("tanglish"):
        return "tanglish"
    # Both tamil and english present without explicit code-mixing
    if counts.get("tamil") and counts.get("english"):
        return "mixed"
    return counts.most_common(1)[0][0]


def language_breakdown(languages: list[str]) -> dict[str, float]:
    """Percentage share of each language across segments."""
    if not languages:
        return {}
    counts = Counter(languages)
    total = sum(counts.values())
    return {lang: round(100 * n / total, 1) for lang, n in counts.most_common()}
