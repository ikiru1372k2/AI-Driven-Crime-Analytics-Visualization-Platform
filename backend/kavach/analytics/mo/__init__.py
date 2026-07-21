"""AI Modus Operandi extraction (EPIC-MO/#36).

Schema v1 (#37) is the validated contract; extraction (#38) fills it from
CaseMaster.BriefFacts using Catalyst Zia text analytics plus a deterministic
lexicon, with whole-rejection on invalid output (ADR-006).
"""

from kavach.analytics.mo.extractor import (
    EXTRACTOR_RULES,
    EXTRACTOR_ZIA,
    METHOD_NAME,
    MODEL_VERSION,
    ExtractionResult,
    ExtractionSkipped,
    extract,
    unknown_rate,
)
from kavach.analytics.mo.repository import MoRepository
from kavach.analytics.mo.runner import ExtractionRunResult, run_extraction
from kavach.analytics.mo.schema import (
    SCHEMA_VERSION,
    UNKNOWN,
    MoProfile,
    MoValidationError,
    validate_extraction,
)
from kavach.analytics.mo.zia import ZiaClient, ZiaSignal, ZiaUnavailable

__all__ = [
    "EXTRACTOR_RULES",
    "EXTRACTOR_ZIA",
    "METHOD_NAME",
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "UNKNOWN",
    "ExtractionResult",
    "ExtractionRunResult",
    "ExtractionSkipped",
    "MoProfile",
    "MoRepository",
    "MoValidationError",
    "ZiaClient",
    "ZiaSignal",
    "ZiaUnavailable",
    "extract",
    "run_extraction",
    "unknown_rate",
    "validate_extraction",
]
