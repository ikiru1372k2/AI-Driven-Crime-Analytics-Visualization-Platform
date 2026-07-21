"""Batch MO extraction under a provenance run (MO-002/#38).

Extracts every case narrative inside
`intelligence_run(IntelligenceType.MO_PROFILE, ...)`, emitting one evidence
row per profile citing its source FIR, so an analyst can walk
attribute -> method -> narrative -> case.

Run metrics (processed / skipped / failed / per-attribute UNKNOWN rate) are
recorded as factors and limitations — the drift indicator #38 asks for.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime

from kavach.analytics.mo.extractor import (
    METHOD_NAME,
    MODEL_VERSION,
    ExtractionSkipped,
    extract,
    unknown_rate,
)
from kavach.analytics.mo.repository import MoRepository
from kavach.analytics.mo.schema import MoValidationError
from kavach.analytics.mo.zia import ZiaClient, ZiaUnavailable
from kavach.provenance import (
    DataClassification,
    Factor,
    IntelligenceType,
    ProvenanceRepository,
    intelligence_run,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractionRunResult:
    run_id: str
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    zia_used: int = 0
    zia_unavailable_reason: str | None = None
    unknown_rates: dict[str, float] = field(default_factory=dict)

    @property
    def extractor_mix(self) -> str:
        if self.zia_used == 0:
            return "RULE_BASED (Zia unavailable)"
        return f"ZIA_TEXT_ANALYTICS on {self.zia_used}/{self.processed}"


def run_extraction(
    conn: sqlite3.Connection,
    provenance: ProvenanceRepository,
    narratives: dict[int, str],
    *,
    zia: ZiaClient | None = None,
    limit: int | None = None,
) -> ExtractionRunResult:
    """Extract MO for every narrative, persisting only validated profiles.

    `zia=None` runs the deterministic path only — the documented fallback when
    Zia is unavailable (#38 AC4). A per-case Zia failure degrades that case to
    the deterministic path rather than failing the run.
    """
    repo = MoRepository(conn)
    items = sorted(narratives.items())
    if limit is not None:
        items = items[:limit]

    result = ExtractionRunResult(run_id="")
    profiles = []
    now = datetime.now(UTC)

    with intelligence_run(
        provenance,
        intelligence_type=IntelligenceType.MO_PROFILE,
        method_name=METHOD_NAME,
        method_version=MODEL_VERSION,
        model_version=MODEL_VERSION,
        analysis_window_from=now,
        analysis_window_to=now,
    ) as run:
        result.run_id = run.run_id

        for case_id, narrative in items:
            signal = None
            if zia is not None:
                try:
                    signal = zia.analyse(narrative)
                except ZiaUnavailable as exc:
                    # first failure decides the run's story; keep extracting
                    if result.zia_unavailable_reason is None:
                        result.zia_unavailable_reason = str(exc)
                        logger.warning("Zia unavailable, using deterministic path: %s", exc)
                    zia = None

            try:
                extraction = extract(case_id, narrative, signal)
            except ExtractionSkipped:
                result.skipped += 1
                continue
            except MoValidationError as exc:
                # whole-rejection: nothing partial is ever stored (ADR-006)
                result.failed += 1
                repo.record_failure(case_id, MODEL_VERSION, str(exc), run.run_id)
                continue

            repo.save(extraction.profile, run.run_id)
            profiles.append(extraction.profile)
            result.processed += 1
            if extraction.extractor == "ZIA_TEXT_ANALYTICS":
                result.zia_used += 1

            run.emit(
                result_ref=f"mo:{case_id}",
                evidence_case_ids=[case_id],
                factors=[
                    Factor(
                        name=name,
                        contribution=float(getattr(extraction.profile, name).confidence),
                    )
                    for name in ("crime_action", "target_type", "mobility")
                ],
                limitations=(
                    "AI_DERIVED from the FIR narrative only; not a finding of fact",
                    "synthetic data (ADR-011)",
                ),
                classification=DataClassification.AI_DERIVED,
            )

        result.unknown_rates = unknown_rate(profiles)

        if items:
            run.emit(
                result_ref=f"mo-run:{run.run_id}",
                evidence_case_ids=(
                    sorted(p.case_master_id for p in profiles) or [i[0] for i in items]
                ),
                factors=[
                    Factor(name="processed", contribution=float(result.processed)),
                    Factor(name="skipped", contribution=float(result.skipped)),
                    Factor(name="failed", contribution=float(result.failed)),
                    Factor(name="zia_extractions", contribution=float(result.zia_used)),
                ],
                limitations=[
                    f"extractor: {result.extractor_mix}",
                    *(
                        [f"Zia unavailable: {result.zia_unavailable_reason}"]
                        if result.zia_unavailable_reason
                        else []
                    ),
                    *(
                        f"UNKNOWN rate {name}: {rate:.0%}"
                        for name, rate in sorted(result.unknown_rates.items())
                    ),
                ],
                classification=DataClassification.DERIVED_METRIC,
            )

    return result
