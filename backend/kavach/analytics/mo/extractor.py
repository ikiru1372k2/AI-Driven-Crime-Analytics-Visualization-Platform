"""MO extraction from BriefFacts (MO-002/#38).

Pipeline per case:

    narrative -> deterministic lexicon pass  (values + spans)
              -> Zia pass, when available    (corroboration + Number entities)
              -> schema validation           (whole-rejection, ADR-006)
              -> MoProfile

Design rule — a value must be anchored to a span of the actual narrative:

* the lexicon sets vocabulary values from phrases it can point at;
* Zia keyword/keyphrase output can only *corroborate* a value the lexicon
  already found, never introduce one. Free-form output therefore cannot
  become analytical truth (ADR-006), and narrative text that mimics
  instructions has nothing to inject into;
* the one value Zia may originate is offender_count, and only from a NER
  *Number* entity, which carries its own offsets and confidence — evidence,
  not generation. It is still bounded by the schema (int 1..100).

Invalid assembled output is rejected whole (EXTRACTION_FAILED); a partial
profile is never persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from kavach.analytics.mo import lexicon
from kavach.analytics.mo.schema import (
    UNKNOWN,
    MoProfile,
    MoValidationError,
    validate_extraction,
)
from kavach.analytics.mo.zia import ZiaSignal

#: Bumped when extraction behaviour changes; profiles are idempotent per
#: (case_master_id, model_version), so a bump re-extracts rather than
#: silently mixing outputs.
MODEL_VERSION = "mo-extract-1.0.0"
METHOD_NAME = "zia_lexicon_mo_extraction"

EXTRACTOR_ZIA = "ZIA_TEXT_ANALYTICS"
EXTRACTOR_RULES = "RULE_BASED"

#: Narratives shorter than this carry no usable MO signal (#38 edge case:
#: "empty/1-word BriefFacts -> skip, count").
MIN_NARRATIVE_CHARS = 12

#: Fields assembled from the lexicon tables, in schema order.
_LEXICON_FIELDS = (
    "mobility",
    "approach_method",
    "crime_action",
    "target_type",
    "time_context",
    "weapon_involved",
)


class ExtractionSkipped(Exception):
    """Narrative too short/empty to extract from — counted, not an error."""


@dataclass(frozen=True)
class ExtractionResult:
    profile: MoProfile
    extractor: str
    zia_corroborations: int


def _attribute(match: lexicon.Match, signal: ZiaSignal | None) -> dict:
    """One schema attribute dict, with Zia corroboration applied."""
    confidence = match.confidence
    corroborated = False
    if signal is not None and match.phrase and signal.mentions(match.phrase):
        confidence = min(lexicon.CONFIDENCE_CEILING, confidence + lexicon.ZIA_CORROBORATION_BONUS)
        corroborated = True
    attr: dict = {"value": match.value, "confidence": round(confidence, 4)}
    if match.span != (0, 0):
        attr["source_span"] = list(match.span)
    return attr if not corroborated else {**attr, "confidence": round(confidence, 4)}


def _offender_count_attribute(
    text: str, signal: ZiaSignal | None
) -> tuple[dict, bool]:
    """offender_count, preferring a Zia NER Number anchored in the text.

    Returns (attribute, used_zia). Falls back to the deterministic pattern,
    then to UNKNOWN.
    """
    pattern_match = lexicon.find_offender_count(text)

    if signal is not None:
        for entity in signal.numbers():
            token = entity.token.strip().lower()
            value = lexicon.NUMBER_WORDS.get(token)
            if value is None:
                try:
                    value = int(token)
                except ValueError:
                    continue
            if not 1 <= value <= 100:
                continue
            # only trust a Number that the deterministic pass also read as an
            # offender count — keeps "2 mobile phones" from becoming 2 offenders
            if pattern_match is None or pattern_match.value != value:
                continue
            return (
                {
                    "value": value,
                    "confidence": round(
                        min(lexicon.CONFIDENCE_CEILING, max(entity.confidence, lexicon.NUMERIC)),
                        4,
                    ),
                    "source_span": [entity.start, entity.end],
                },
                True,
            )

    if pattern_match is not None:
        return _attribute(pattern_match, signal), False
    return _attribute(lexicon.unknown_match(), None), False


def extract(
    case_master_id: int,
    narrative: str,
    signal: ZiaSignal | None = None,
    *,
    extracted_at: str | None = None,
) -> ExtractionResult:
    """Extract one validated MoProfile from a narrative.

    Raises ExtractionSkipped for unusable narratives and MoValidationError if
    the assembled payload violates schema v1 (never partially persisted).
    """
    text = (narrative or "").strip()
    if len(text) < MIN_NARRATIVE_CHARS:
        raise ExtractionSkipped(f"narrative too short ({len(text)} chars)")

    corroborations = 0
    raw: dict = {
        "case_master_id": case_master_id,
        "extractor": EXTRACTOR_ZIA if signal is not None else EXTRACTOR_RULES,
        "model_version": MODEL_VERSION,
        "extracted_at": extracted_at or datetime.now(UTC).isoformat(),
    }

    offender_attr, used_zia_number = _offender_count_attribute(text, signal)
    raw["offender_count"] = offender_attr
    if used_zia_number:
        corroborations += 1

    for field_name in _LEXICON_FIELDS:
        match = lexicon.find_matches(text, lexicon.FIELD_LEXICONS[field_name])
        if match is None:
            raw[field_name] = _attribute(lexicon.unknown_match(), None)
            continue
        if signal is not None and match.phrase and signal.mentions(match.phrase):
            corroborations += 1
        raw[field_name] = _attribute(match, signal)

    escape = lexicon.find_escape_direction(text)
    raw["escape_direction"] = _attribute(escape or lexicon.unknown_match(), None)

    profile = validate_extraction(raw)  # raises MoValidationError -> caller marks FAILED
    return ExtractionResult(
        profile=profile,
        extractor=raw["extractor"],
        zia_corroborations=corroborations,
    )


def unknown_rate(profiles: list[MoProfile]) -> dict[str, float]:
    """Per-attribute UNKNOWN rate — the drift indicator #38 asks for."""
    if not profiles:
        return {}
    fields = ("offender_count", *_LEXICON_FIELDS)
    out: dict[str, float] = {}
    for name in fields:
        unknowns = sum(1 for p in profiles if getattr(p, name).value == UNKNOWN)
        out[name] = round(unknowns / len(profiles), 4)
    return out


__all__ = [
    "EXTRACTOR_RULES",
    "EXTRACTOR_ZIA",
    "METHOD_NAME",
    "MODEL_VERSION",
    "ExtractionResult",
    "ExtractionSkipped",
    "MoValidationError",
    "extract",
    "unknown_rate",
]
