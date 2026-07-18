"""PROV-001/#24 acceptance tests: lifecycle, enforcement, failure semantics."""

import sqlite3
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from kavach.provenance import (
    DataClassification,
    Factor,
    IntelligenceEvidence,
    IntelligenceType,
    ProvenanceError,
    ProvenanceRepository,
    RunStatus,
    intelligence_run,
)
from kavach.repositories.dev_fixture import connect

WINDOW = {
    "analysis_window_from": datetime(2025, 1, 1, tzinfo=UTC),
    "analysis_window_to": datetime(2025, 3, 1, tzinfo=UTC),
}
HOTSPOT_ARGS = {
    "intelligence_type": IntelligenceType.HOTSPOT,
    "method_name": "dbscan_haversine",
    "method_version": "1.0.0",
    **WINDOW,
}


@pytest.fixture()
def repo() -> ProvenanceRepository:
    return ProvenanceRepository(connect())


def test_completed_run_lifecycle(repo):
    with intelligence_run(repo, **HOTSPOT_ARGS) as run:
        ev = run.emit(
            result_ref="hotspot:1",
            evidence_case_ids=[101, 102, 103],
            factors=[Factor(name="case_density", contribution=0.8, direction="UP")],
            limitations=["synthetic data (ADR-011)"],
            classification=DataClassification.STATISTICAL_INFERENCE,
        )
        assert ev.evidence_id is not None
    stored = repo.get_run(run.run_id)
    assert stored.status is RunStatus.COMPLETED
    assert stored.record_count == 1
    assert stored.generated_at is not None


def test_failed_run_persists_error_and_removes_partial_evidence(repo):
    with pytest.raises(ValueError, match="engine exploded"):
        with intelligence_run(repo, **HOTSPOT_ARGS) as run:
            run.emit(
                result_ref="hotspot:1",
                evidence_case_ids=[101],
                classification=DataClassification.STATISTICAL_INFERENCE,
            )
            raise ValueError("engine exploded")
    stored = repo.get_run(run.run_id)
    assert stored.status is RunStatus.FAILED
    assert "engine exploded" in stored.error
    assert repo.evidence_for_run(run.run_id) == []  # no partial COMPLETED evidence


def test_emit_outside_run_context_raises(repo):
    with intelligence_run(repo, **HOTSPOT_ARGS) as run:
        pass
    with pytest.raises(ProvenanceError, match="closed"):
        run.emit(
            result_ref="late",
            evidence_case_ids=[1],
            classification=DataClassification.FACT,
        )


def test_direct_insert_without_running_run_raises(repo):
    """Repository-level enforcement: no evidence outside an open run."""
    with intelligence_run(repo, **HOTSPOT_ARGS) as run:
        pass  # run is now COMPLETED
    with pytest.raises(ProvenanceError):
        repo.insert_evidence(
            IntelligenceEvidence(
                run_id=run.run_id,
                result_ref="sneaky",
                evidence_case_ids=(1,),
                classification=DataClassification.FACT,
            )
        )
    with pytest.raises(ProvenanceError, match="unknown run_id"):
        repo.insert_evidence(
            IntelligenceEvidence(
                run_id="no-such-run",
                result_ref="sneaky",
                evidence_case_ids=(1,),
                classification=DataClassification.FACT,
            )
        )


def test_case_backed_types_require_evidence_case_ids(repo):
    with pytest.raises(ProvenanceError, match="case-backed"):
        with intelligence_run(repo, **HOTSPOT_ARGS) as run:
            run.emit(
                result_ref="hotspot:1",
                evidence_case_ids=[],
                classification=DataClassification.STATISTICAL_INFERENCE,
            )
    # the violating run itself is FAILED, not silently completed
    assert repo.get_run(run.run_id).status is RunStatus.FAILED


def test_aggregate_only_type_may_emit_without_case_ids(repo):
    args = {**HOTSPOT_ARGS, "intelligence_type": IntelligenceType.AREA_RISK}
    with intelligence_run(repo, **args) as run:
        run.emit(
            result_ref="district:44",
            classification=DataClassification.DERIVED_METRIC,
        )
    assert repo.get_run(run.run_id).status is RunStatus.COMPLETED


def test_classification_is_mandatory_model_and_db(repo):
    # model level: pydantic refuses evidence without classification
    with pytest.raises(ValidationError):
        IntelligenceEvidence(run_id="r", result_ref="x", evidence_case_ids=(1,))
    # DB level: NOT NULL constraint holds even for raw SQL writers
    conn = repo._conn
    run = repo.create_run(**HOTSPOT_ARGS)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO IntelligenceEvidence (run_id, result_ref, evidence_case_ids, "
            "factors, limitations, classification) VALUES (?, ?, '[]', '[]', '[]', NULL)",
            (run.run_id, "raw"),
        )


def test_method_version_not_null_at_db_level(repo):
    with pytest.raises(sqlite3.IntegrityError):
        repo._conn.execute(
            "INSERT INTO IntelligenceRun (run_id, intelligence_type, method_name, "
            "method_version, analysis_window_from, analysis_window_to, status, "
            "generated_at) VALUES ('x', 'HOTSPOT', 'm', NULL, 'a', 'b', 'RUNNING', 'now')"
        )


def test_evidence_round_trip_with_factors_and_limitations(repo):
    with intelligence_run(repo, **HOTSPOT_ARGS) as run:
        run.emit(
            result_ref="hotspot:7",
            evidence_case_ids=[5, 6],
            factors=[
                Factor(name="density", contribution=0.7, direction="UP"),
                Factor(name="recency", contribution=-0.2, direction="DOWN"),
            ],
            limitations=["window truncated"],
            classification=DataClassification.STATISTICAL_INFERENCE,
        )
    (ev,) = repo.evidence_for_result("hotspot:7")
    assert ev.run_id == run.run_id
    assert ev.evidence_case_ids == (5, 6)
    assert ev.factors[1].direction == "DOWN"
    assert ev.limitations == ("window truncated",)
    assert ev.classification is DataClassification.STATISTICAL_INFERENCE
    # pinned to a run
    assert repo.evidence_for_result("hotspot:7", run_id=run.run_id) == [ev]
    assert repo.evidence_for_result("hotspot:7", run_id="other") == []


def test_latest_completed_run_per_type_and_scope(repo):
    scoped = {**HOTSPOT_ARGS, "scope_district_id": 44}
    with intelligence_run(repo, **scoped) as first:
        first.emit(
            result_ref="a", evidence_case_ids=[1], classification=DataClassification.FACT
        )
    with intelligence_run(repo, **scoped) as second:
        second.emit(
            result_ref="b", evidence_case_ids=[2], classification=DataClassification.FACT
        )
    # a FAILED run never wins
    with pytest.raises(RuntimeError):
        with intelligence_run(repo, **scoped):
            raise RuntimeError("boom")
    # a RUNNING run never wins
    repo.create_run(**scoped)
    latest = repo.latest_completed_run(IntelligenceType.HOTSPOT, scope_district_id=44)
    assert latest.run_id == second.run_id
    # different scope is a different lineage
    assert repo.latest_completed_run(IntelligenceType.HOTSPOT) is None


def test_concurrent_runs_same_type_scope_are_distinguished(repo):
    a = repo.create_run(**HOTSPOT_ARGS)
    b = repo.create_run(**HOTSPOT_ARGS)
    assert a.run_id != b.run_id
    assert repo.get_run(a.run_id).status is RunStatus.RUNNING
    assert repo.get_run(b.run_id).status is RunStatus.RUNNING


def test_huge_evidence_list_preview_cap(repo):
    ids = tuple(range(1, 101))
    ev = IntelligenceEvidence(
        run_id="r",
        result_ref="x",
        evidence_case_ids=ids,
        classification=DataClassification.DERIVED_METRIC,
    )
    head, more = ev.evidence_preview()
    assert len(head) == 25 and more == 75
    # full list stays retrievable through the store
    with intelligence_run(repo, **HOTSPOT_ARGS) as run:
        run.emit(
            result_ref="big",
            evidence_case_ids=ids,
            classification=DataClassification.DERIVED_METRIC,
        )
    (stored,) = repo.evidence_for_result("big")
    assert stored.evidence_case_ids == ids


def test_derived_tables_never_touch_source_tables(repo):
    """Boundary rule 1/5: framework writes only its own DERIVED tables."""
    conn = repo._conn
    before = conn.execute("SELECT COUNT(*) FROM CaseMaster").fetchone()[0]
    with intelligence_run(repo, **HOTSPOT_ARGS) as run:
        run.emit(
            result_ref="hotspot:1",
            evidence_case_ids=[1],
            classification=DataClassification.STATISTICAL_INFERENCE,
        )
    assert conn.execute("SELECT COUNT(*) FROM CaseMaster").fetchone()[0] == before
