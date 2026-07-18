"""Engine-facing provenance SDK (PROV-001/#24).

Usage — the ONLY sanctioned write-path for intelligence results:

    with intelligence_run(
        repo,
        intelligence_type=IntelligenceType.HOTSPOT,
        method_name="dbscan_haversine",
        method_version="1.0.0",
        analysis_window_from=start,
        analysis_window_to=end,
    ) as run:
        run.emit(
            result_ref="hotspot:3",
            evidence_case_ids=[101, 102],
            factors=[Factor(name="case_density", contribution=0.8)],
            limitations=["synthetic data (ADR-011)"],
            classification=DataClassification.STATISTICAL_INFERENCE,
        )

On normal exit the run is marked COMPLETED with record_count = emitted
results. On exception the run is marked FAILED with the error persisted,
its evidence rows are removed, and the exception propagates.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime

from kavach.provenance.models import (
    AGGREGATE_ONLY_TYPES,
    DataClassification,
    Factor,
    IntelligenceEvidence,
    IntelligenceRun,
    IntelligenceType,
)
from kavach.provenance.repository import ProvenanceError, ProvenanceRepository


class RunHandle:
    """Handle yielded by intelligence_run(); emit() persists evidence."""

    def __init__(self, repo: ProvenanceRepository, run: IntelligenceRun):
        self._repo = repo
        self._run = run
        self._closed = False
        self.emitted_count = 0

    @property
    def run_id(self) -> str:
        return self._run.run_id

    @property
    def run(self) -> IntelligenceRun:
        return self._run

    def emit(
        self,
        *,
        result_ref: str,
        evidence_case_ids: Iterable[int] = (),
        factors: Iterable[Factor] = (),
        limitations: Iterable[str] = (),
        classification: DataClassification,
    ) -> IntelligenceEvidence:
        """Persist evidence for one result of this run.

        Case-backed intelligence types must cite at least one evidence case;
        only AGGREGATE_ONLY_TYPES (documented whitelist) may emit without.
        """
        if self._closed:
            raise ProvenanceError(
                f"run {self.run_id!r} is closed — emit() only inside the run context"
            )
        case_ids = tuple(evidence_case_ids)
        if not case_ids and self._run.intelligence_type not in AGGREGATE_ONLY_TYPES:
            raise ProvenanceError(
                f"{self._run.intelligence_type.value} results are case-backed: "
                "emit() requires non-empty evidence_case_ids"
            )
        evidence = self._repo.insert_evidence(
            IntelligenceEvidence(
                run_id=self.run_id,
                result_ref=result_ref,
                evidence_case_ids=case_ids,
                factors=tuple(factors),
                limitations=tuple(limitations),
                classification=classification,
            )
        )
        self.emitted_count += 1
        return evidence


@contextmanager
def intelligence_run(
    repo: ProvenanceRepository,
    *,
    intelligence_type: IntelligenceType,
    method_name: str,
    method_version: str,
    analysis_window_from: datetime,
    analysis_window_to: datetime,
    model_version: str | None = None,
    scope_district_id: int | None = None,
    scope_unit_id: int | None = None,
) -> Iterator[RunHandle]:
    run = repo.create_run(
        intelligence_type=intelligence_type,
        method_name=method_name,
        method_version=method_version,
        model_version=model_version,
        analysis_window_from=analysis_window_from,
        analysis_window_to=analysis_window_to,
        scope_district_id=scope_district_id,
        scope_unit_id=scope_unit_id,
    )
    handle = RunHandle(repo, run)
    try:
        yield handle
    except BaseException as exc:
        handle._closed = True
        repo.mark_failed(run.run_id, error=f"{type(exc).__name__}: {exc}")
        raise
    else:
        handle._closed = True
        repo.mark_completed(run.run_id, record_count=handle.emitted_count)
