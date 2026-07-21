"""Catalyst Zia text-analytics adapter for MO extraction (MO-002/#38).

Zia is the Catalyst-native NLP service (ADR-001) — no external LLM is used.
Verified live against project AI-KSP on 2026-07-21:

    POST /ml/text-analytics/keyword-extraction
      -> {"keyword_extractor": {"keywords": [...], "keyphrases": [...]}}
    POST /ml/text-analytics/ner
      -> {"ner": {"general_entities": [
             {"token": "Two", "ner_tag": "Number",
              "start_index": "0", "end_index": "3",
              "confidence_score": "100"}]}}

Two things matter for provenance: NER returns character offsets, so a value
derived from it is anchored to the narrative; and it returns a confidence
score, so that confidence is Zia's own rather than one we invented (#38
forbids fabricated confidences).

Unavailability is normal — the service may be disabled on a plan, or the
runtime may lack Catalyst request headers. Every failure raises ZiaUnavailable
and the caller degrades to the deterministic extractor.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

#: Zia is called per narrative; anything longer is truncated (documented
#: window, #38 edge case "very long narratives").
MAX_NARRATIVE_CHARS = 4000


class ZiaUnavailable(RuntimeError):
    """Zia could not be reached, is disabled, or returned an unusable payload."""


@dataclass(frozen=True)
class ZiaEntity:
    token: str
    tag: str
    start: int
    end: int
    confidence: float  # 0..1 (Zia reports 0..100)


@dataclass(frozen=True)
class ZiaSignal:
    """What Zia observed in one narrative."""

    keywords: tuple[str, ...] = ()
    keyphrases: tuple[str, ...] = ()
    entities: tuple[ZiaEntity, ...] = ()

    def mentions(self, phrase: str) -> bool:
        """Whether Zia independently surfaced this phrase (corroboration)."""
        needle = phrase.lower().strip()
        if not needle:
            return False
        return any(
            needle in term.lower() or term.lower() in needle
            for term in (*self.keywords, *self.keyphrases)
        )

    def numbers(self) -> list[ZiaEntity]:
        return [e for e in self.entities if e.tag.lower() == "number"]


@dataclass
class ZiaClient:
    """Calls Zia through the Catalyst SDK, using the request's headers.

    The SDK has no ambient credential on AppSail — it must be initialised with
    the incoming Catalyst headers (the same constraint documented for
    /health/datastore), so callers pass them through.
    """

    headers: dict[str, str] = field(default_factory=dict)

    def _component(self):
        try:
            import zcatalyst_sdk  # type: ignore[import-not-found]
        except ImportError as exc:  # local dev without the SDK
            raise ZiaUnavailable("zcatalyst-sdk not installed") from exc
        try:
            app = (
                zcatalyst_sdk.initialize(req=self.headers)
                if self.headers
                else zcatalyst_sdk.initialize()
            )
            return app.zia()
        except Exception as exc:  # noqa: BLE001 - SDK raises broad errors
            raise ZiaUnavailable(f"zia init failed: {type(exc).__name__}: {exc}") from exc

    def analyse(self, text: str) -> ZiaSignal:
        """Keyword extraction + NER for one narrative."""
        snippet = text[:MAX_NARRATIVE_CHARS]
        zia = self._component()
        try:
            kw = zia.get_keyword_extraction([snippet])
            ner = zia.get_NER_prediction([snippet])
        except Exception as exc:  # noqa: BLE001
            raise ZiaUnavailable(f"zia call failed: {type(exc).__name__}: {exc}") from exc
        return parse_signal(kw, ner)


def _first_payload(data, key: str) -> dict:
    """Zia returns a list with one entry per submitted document."""
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        return {}
    inner = data.get(key, data)
    return inner if isinstance(inner, dict) else {}


def parse_signal(keyword_payload, ner_payload) -> ZiaSignal:
    """Normalise raw Zia responses into a ZiaSignal.

    Tolerant by design: a shape change degrades to fewer signals (weaker
    corroboration) rather than failing extraction, because Zia only ever
    corroborates values the deterministic pass already found.
    """
    kw = _first_payload(keyword_payload, "keyword_extractor")
    keywords = tuple(str(k) for k in kw.get("keywords", []) if str(k).strip())
    keyphrases = tuple(str(k) for k in kw.get("keyphrases", []) if str(k).strip())

    entities: list[ZiaEntity] = []
    ner = _first_payload(ner_payload, "ner")
    for raw in ner.get("general_entities", []) or []:
        try:
            entities.append(
                ZiaEntity(
                    token=str(raw["token"]),
                    tag=str(raw["ner_tag"]),
                    start=int(raw["start_index"]),
                    end=int(raw["end_index"]),
                    confidence=min(1.0, max(0.0, float(raw.get("confidence_score", 0)) / 100.0)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed entity, keep the rest
    return ZiaSignal(keywords=keywords, keyphrases=keyphrases, entities=tuple(entities))
