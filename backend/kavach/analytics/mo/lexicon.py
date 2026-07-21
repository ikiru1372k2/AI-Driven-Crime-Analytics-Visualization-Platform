"""Narrative phrase -> MO vocabulary mapping (MO-002/#38).

Every value the extractor produces must be anchored to a span of the actual
BriefFacts text. This module owns that anchoring: it finds phrases and maps
them to the controlled vocabularies in schema.py, returning the character
span that justified each value so the UI can highlight it.

Why a lexicon rather than free-form model output: ADR-006 forbids
unvalidated generated text becoming analytical truth. Catalyst Zia returns
keywords and entities, not schema fields, so the mapping to vocabulary is
deterministic and reviewable here, and Zia's role is to corroborate (see
extractor.py). A narrative that tries to inject instructions cannot invent
an attribute, because only phrases in these tables can set one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from kavach.analytics.mo.schema import UNKNOWN

#: Match strength -> confidence. Documented rather than invented (#38 forbids
#: fabricated per-attribute confidences):
#:   STRONG — an unambiguous phrase for exactly one vocabulary value
#:            ("gold chain", "motorcycle")
#:   WEAK   — a phrase that usually but not always implies the value
#:            ("chain" alone, "vehicle")
STRONG = 0.90
WEAK = 0.60
#: Value derived from a Zia NER Number token (span-anchored, model-scored).
NUMERIC = 0.85
#: No supporting phrase found. Means "no evidence in the narrative", NOT
#: "the attribute is absent in reality".
UNKNOWN_CONFIDENCE = 0.50
#: Corroboration bonus when Zia independently surfaces the matched phrase.
ZIA_CORROBORATION_BONUS = 0.05
CONFIDENCE_CEILING = 0.95

#: phrase -> (vocabulary value, strength). Order within a field matters only
#: for readability; the longest match wins (see find_matches).
MOBILITY: dict[str, tuple[str, float]] = {
    "motorcycle": ("motorcycle", STRONG),
    "motor cycle": ("motorcycle", STRONG),
    "two-wheeler": ("motorcycle", STRONG),
    "two wheeler": ("motorcycle", STRONG),
    "bike": ("motorcycle", WEAK),
    "scooter": ("motorcycle", STRONG),
    "car": ("car", STRONG),
    "autorickshaw": ("autorickshaw", STRONG),
    "auto rickshaw": ("autorickshaw", STRONG),
    "bicycle": ("bicycle", STRONG),
    "on foot": ("on_foot", STRONG),
    "walking": ("on_foot", WEAK),
    "bus": ("public_transport", WEAK),
    "train": ("public_transport", WEAK),
}

APPROACH: dict[str, tuple[str, float]] = {
    "came from behind": ("mobile_approach", STRONG),
    "approached": ("mobile_approach", WEAK),
    "travelling on": ("mobile_approach", WEAK),
    "riding": ("mobile_approach", WEAK),
    "waylaid": ("stationary_ambush", STRONG),
    "stopped": ("stationary_ambush", WEAK),
    "lying in wait": ("stationary_ambush", STRONG),
    "broke open": ("entry_breakin", STRONG),
    "broke into": ("entry_breakin", STRONG),
    "trespassed": ("entry_breakin", STRONG),
    "promising": ("deception", WEAK),
    "posing as": ("deception", STRONG),
    "quarrel": ("confrontation", STRONG),
    "altercation": ("confrontation", STRONG),
    "obstructed": ("confrontation", WEAK),
}

ACTION: dict[str, tuple[str, float]] = {
    "snatched": ("snatching", STRONG),
    "snatching": ("snatching", STRONG),
    "robbed": ("robbery", STRONG),
    "by force": ("robbery", WEAK),
    "committed theft": ("theft", STRONG),
    "stole": ("theft", STRONG),
    "theft": ("theft", WEAK),
    "burglary": ("burglary", STRONG),
    "assaulted": ("assault", STRONG),
    "attacked": ("assault", STRONG),
    "threatened": ("threat", STRONG),
    "under threat": ("threat", STRONG),
    "cheated": ("fraud", STRONG),
    "failed to return": ("fraud", WEAK),
}

TARGET: dict[str, tuple[str, float]] = {
    "gold chain": ("gold_chain", STRONG),
    "chain": ("gold_chain", WEAK),
    "mangalsutra": ("gold_chain", STRONG),
    "mobile phone": ("mobile_phone", STRONG),
    "cellphone": ("mobile_phone", STRONG),
    "mobile": ("mobile_phone", WEAK),
    "cash": ("cash", STRONG),
    "money": ("cash", WEAK),
    "two-wheeler": ("vehicle", WEAK),
    "vehicle": ("vehicle", WEAK),
    "jewellery": ("jewelry", STRONG),
    "jewelry": ("jewelry", STRONG),
    "ornaments": ("jewelry", STRONG),
    "valuables": ("property", WEAK),
    "property": ("property", WEAK),
}

TIME_CONTEXT: dict[str, tuple[str, float]] = {
    "during the night": ("night", STRONG),
    "at night": ("night", STRONG),
    "midnight": ("night", STRONG),
    "late hours": ("night", WEAK),
    "morning": ("day", STRONG),
    "afternoon": ("day", STRONG),
    "daytime": ("day", STRONG),
    "during the day": ("day", STRONG),
    "dawn": ("dawn_dusk", STRONG),
    "dusk": ("dawn_dusk", STRONG),
    "early hours": ("dawn_dusk", WEAK),
}

WEAPON: dict[str, tuple[str, float]] = {
    "knife": ("yes", STRONG),
    "machete": ("yes", STRONG),
    "weapon": ("yes", STRONG),
    "firearm": ("yes", STRONG),
    "pistol": ("yes", STRONG),
    "stick": ("yes", WEAK),
    "rod": ("yes", WEAK),
    "at knifepoint": ("yes", STRONG),
    "unarmed": ("no", STRONG),
    "without any weapon": ("no", STRONG),
}

#: field name -> lexicon table. Drives the extraction loop.
FIELD_LEXICONS: dict[str, dict[str, tuple[str, float]]] = {
    "mobility": MOBILITY,
    "approach_method": APPROACH,
    "crime_action": ACTION,
    "target_type": TARGET,
    "time_context": TIME_CONTEXT,
    "weapon_involved": WEAPON,
}

#: Number words the narratives use for offender counts. Zia NER tags these as
#: Number tokens; this converts them to the integer the schema requires.
NUMBER_WORDS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

#: Phrases that indicate offenders when adjacent to a count.
_OFFENDER_NOUNS = r"(?:persons?|men|women|accused|assailants?|miscreants?|individuals?|youths?)"
_OFFENDER_COUNT_RE = re.compile(
    rf"\b({'|'.join(NUMBER_WORDS)}|\d{{1,2}})\b(?:\s+\w+){{0,3}}?\s+{_OFFENDER_NOUNS}\b",
    re.IGNORECASE,
)

#: Escape direction is display-only (excluded from similarity by the schema).
_ESCAPE_RE = re.compile(
    r"(?:escap\w+|fled|sped away|ran away)\s+"
    r"(?:in the direction of|towards|toward)\s+([^.,;]{2,60})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Match:
    """One vocabulary hit anchored to the narrative."""

    value: str | int
    confidence: float
    span: tuple[int, int]
    phrase: str


def find_matches(text: str, lexicon: dict[str, tuple[str, float]]) -> Match | None:
    """Best vocabulary match in `text`, or None.

    Longest phrase wins, then higher strength — so "gold chain" beats "chain"
    and never yields the weaker reading of the same sentence.
    """
    lowered = text.lower()
    best: Match | None = None
    for phrase, (value, strength) in lexicon.items():
        idx = lowered.find(phrase)
        if idx == -1:
            continue
        candidate = Match(value, strength, (idx, idx + len(phrase)), text[idx : idx + len(phrase)])
        if best is None or (len(phrase), strength) > (len(best.phrase), best.confidence):
            best = candidate
    return best


def find_offender_count(text: str) -> Match | None:
    """Offender count from a '<number> <noun>' construction."""
    m = _OFFENDER_COUNT_RE.search(text)
    if not m:
        return None
    token = m.group(1).lower()
    value = NUMBER_WORDS.get(token)
    if value is None:
        try:
            value = int(token)
        except ValueError:
            return None
    if not 1 <= value <= 100:  # schema bound; refuse rather than clamp
        return None
    return Match(value, NUMERIC, (m.start(1), m.end(1)), m.group(1))


def find_escape_direction(text: str) -> Match | None:
    """Free-text escape direction (display-only, never used for similarity)."""
    m = _ESCAPE_RE.search(text)
    if not m:
        return None
    direction = m.group(1).strip()
    return Match(direction, WEAK, (m.start(1), m.start(1) + len(direction)), direction)


def unknown_match() -> Match:
    """The absence-of-evidence value, with its documented confidence."""
    return Match(UNKNOWN, UNKNOWN_CONFIDENCE, (0, 0), "")
