"""Provenance persistence (PROV-001/#24) over the dev fixture connection.

Catalyst Data Store backend lands with CAT-002/#18 behind this same
interface. Derived tables live alongside (never inside) the source ER
schema; DDL here mirrors docs/schema/derived-intelligence-schema.md.

Failure semantics: a FAILED run persists its error and its evidence rows
are removed — a FAILED run can never leave partial COMPLETED-looking
evidence behind (issue #24 acceptance criteria).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime

from kavach.provenance.models import (
    DataClassification,
    Factor,
    IntelligenceEvidence,
    IntelligenceRun,
    IntelligenceType,
    RunStatus,
)


class ProvenanceError(RuntimeError):
    """Raised when the enforced provenance write-path is violated."""


_DDL = [
    """CREATE TABLE IF NOT EXISTS IntelligenceRun (
        run_id TEXT PRIMARY KEY,
        intelligence_type TEXT NOT NULL,
        method_name TEXT NOT NULL,
        method_version TEXT NOT NULL,
        model_version TEXT,
        analysis_window_from TEXT NOT NULL,
        analysis_window_to TEXT NOT NULL,
        scope_district_id INTEGER,
        scope_unit_id INTEGER,
        status TEXT NOT NULL,
        error TEXT,
        generated_at TEXT NOT NULL,
        record_count INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS IntelligenceEvidence (
        evidence_id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES IntelligenceRun(run_id),
        result_ref TEXT NOT NULL,
        evidence_case_ids TEXT NOT NULL,
        factors TEXT NOT NULL,
        limitations TEXT NOT NULL,
        classification TEXT NOT NULL
    )""",
]


def _run_from_row(row: sqlite3.Row) -> IntelligenceRun:
    return IntelligenceRun(
        run_id=row["run_id"],
        intelligence_type=IntelligenceType(row["intelligence_type"]),
        method_name=row["method_name"],
        method_version=row["method_version"],
        model_version=row["model_version"],
        analysis_window_from=datetime.fromisoformat(row["analysis_window_from"]),
        analysis_window_to=datetime.fromisoformat(row["analysis_window_to"]),
        scope_district_id=row["scope_district_id"],
        scope_unit_id=row["scope_unit_id"],
        status=RunStatus(row["status"]),
        error=row["error"],
        generated_at=datetime.fromisoformat(row["generated_at"]),
        record_count=row["record_count"],
    )


def _evidence_from_row(row: sqlite3.Row) -> IntelligenceEvidence:
    return IntelligenceEvidence(
        evidence_id=row["evidence_id"],
        run_id=row["run_id"],
        result_ref=row["result_ref"],
        evidence_case_ids=tuple(json.loads(row["evidence_case_ids"])),
        factors=tuple(Factor(**f) for f in json.loads(row["factors"])),
        limitations=tuple(json.loads(row["limitations"])),
        classification=DataClassification(row["classification"]),
    )


class ProvenanceRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        for ddl in _DDL:
            conn.execute(ddl)

    # -- run lifecycle ---------------------------------------------------
    def create_run(
        self,
        *,
        intelligence_type: IntelligenceType,
        method_name: str,
        method_version: str,
        analysis_window_from: datetime,
        analysis_window_to: datetime,
        model_version: str | None = None,
        scope_district_id: int | None = None,
        scope_unit_id: int | None = None,
    ) -> IntelligenceRun:
        run = IntelligenceRun(
            run_id=uuid.uuid4().hex,
            intelligence_type=intelligence_type,
            method_name=method_name,
            method_version=method_version,
            model_version=model_version,
            analysis_window_from=analysis_window_from,
            analysis_window_to=analysis_window_to,
            scope_district_id=scope_district_id,
            scope_unit_id=scope_unit_id,
            status=RunStatus.RUNNING,
            generated_at=datetime.now(UTC),  # server-side, never engine-supplied
        )
        self._conn.execute(
            "INSERT INTO IntelligenceRun (run_id, intelligence_type, method_name, "
            "method_version, model_version, analysis_window_from, analysis_window_to, "
            "scope_district_id, scope_unit_id, status, error, generated_at, record_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run.run_id,
                run.intelligence_type.value,
                run.method_name,
                run.method_version,
                run.model_version,
                run.analysis_window_from.isoformat(),
                run.analysis_window_to.isoformat(),
                run.scope_district_id,
                run.scope_unit_id,
                run.status.value,
                run.error,
                run.generated_at.isoformat(),
                run.record_count,
            ),
        )
        return run

    def get_run(self, run_id: str) -> IntelligenceRun | None:
        row = self._conn.execute(
            "SELECT * FROM IntelligenceRun WHERE run_id = ?", (run_id,)
        ).fetchone()
        return None if row is None else _run_from_row(row)

    def mark_completed(self, run_id: str, *, record_count: int) -> None:
        self._require_status(run_id, RunStatus.RUNNING)
        self._conn.execute(
            "UPDATE IntelligenceRun SET status = ?, record_count = ? WHERE run_id = ?",
            (RunStatus.COMPLETED.value, record_count, run_id),
        )

    def mark_failed(self, run_id: str, *, error: str) -> None:
        """Persist the failure and remove the run's evidence (no partials)."""
        self._require_status(run_id, RunStatus.RUNNING)
        self._conn.execute("DELETE FROM IntelligenceEvidence WHERE run_id = ?", (run_id,))
        self._conn.execute(
            "UPDATE IntelligenceRun SET status = ?, error = ?, record_count = 0 "
            "WHERE run_id = ?",
            (RunStatus.FAILED.value, error, run_id),
        )

    def _require_status(self, run_id: str, expected: RunStatus) -> IntelligenceRun:
        run = self.get_run(run_id)
        if run is None:
            raise ProvenanceError(f"unknown run_id {run_id!r}")
        if run.status is not expected:
            raise ProvenanceError(
                f"run {run_id!r} is {run.status.value}, expected {expected.value}"
            )
        return run

    # -- evidence --------------------------------------------------------
    def insert_evidence(self, evidence: IntelligenceEvidence) -> IntelligenceEvidence:
        """Persist one evidence row. Only allowed while its run is RUNNING —
        engines cannot write evidence outside an open run context."""
        self._require_status(evidence.run_id, RunStatus.RUNNING)
        cur = self._conn.execute(
            "INSERT INTO IntelligenceEvidence (run_id, result_ref, evidence_case_ids, "
            "factors, limitations, classification) VALUES (?, ?, ?, ?, ?, ?)",
            (
                evidence.run_id,
                evidence.result_ref,
                json.dumps(list(evidence.evidence_case_ids)),
                json.dumps([f.model_dump() for f in evidence.factors]),
                json.dumps(list(evidence.limitations)),
                evidence.classification.value,
            ),
        )
        return evidence.model_copy(update={"evidence_id": cur.lastrowid})

    def evidence_for_run(self, run_id: str) -> list[IntelligenceEvidence]:
        rows = self._conn.execute(
            "SELECT * FROM IntelligenceEvidence WHERE run_id = ? ORDER BY evidence_id",
            (run_id,),
        ).fetchall()
        return [_evidence_from_row(r) for r in rows]

    def evidence_for_result(
        self, result_ref: str, *, run_id: str | None = None
    ) -> list[IntelligenceEvidence]:
        """Evidence by result_ref, optionally pinned to one run."""
        sql = "SELECT * FROM IntelligenceEvidence WHERE result_ref = ?"
        params: list[object] = [result_ref]
        if run_id is not None:
            sql += " AND run_id = ?"
            params.append(run_id)
        rows = self._conn.execute(sql + " ORDER BY evidence_id", params).fetchall()
        return [_evidence_from_row(r) for r in rows]

    # -- queries ----------------------------------------------------------
    def latest_completed_run(
        self,
        intelligence_type: IntelligenceType,
        *,
        scope_district_id: int | None = None,
        scope_unit_id: int | None = None,
    ) -> IntelligenceRun | None:
        """Latest COMPLETED run for a type/scope (concurrent runs of the same
        type/scope are allowed; they stay distinguishable by run_id)."""
        row = self._conn.execute(
            "SELECT * FROM IntelligenceRun WHERE intelligence_type = ? AND status = ? "
            "AND scope_district_id IS ? AND scope_unit_id IS ? "
            "ORDER BY generated_at DESC, rowid DESC LIMIT 1",
            (
                intelligence_type.value,
                RunStatus.COMPLETED.value,
                scope_district_id,
                scope_unit_id,
            ),
        ).fetchone()
        return None if row is None else _run_from_row(row)
