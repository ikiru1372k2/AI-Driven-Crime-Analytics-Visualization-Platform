"""Evidence & Provenance browser API + persisted decisions (design review 1h).

The judge-facing differentiator: any AI output → its method (+version,
window, limitations) → the source FIRs behind it — plus the decision/audit
trail that makes human-in-the-loop real (decisions survive reload, every
one is recorded through the append-only audit framework, PROV-003/#26).

Actor/role arrive via X-KAVACH-ACTOR / X-KAVACH-ROLE headers until
Catalyst Authentication (#19) binds them to the session — the same seam
as scope_district_id in the graph API.
"""

from __future__ import annotations

import threading
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from kavach.api.audit_routes import audit_repo
from kavach.api.graph_store import graph_context
from kavach.provenance import IntelligenceType, RunStatus
from kavach.provenance.audit import (
    AuditEvent,
    AuditEventType,
    record_identity_review,
)

router = APIRouter(prefix="/api/v1", tags=["evidence"])

_lock = threading.Lock()

_DECISION_DDL = """CREATE TABLE IF NOT EXISTS Decision (
    target_ref TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    decision TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    decided_at TEXT NOT NULL
)"""


def _decision_conn():
    """Decisions live beside the audit store (same LOCAL SQLite conn)."""
    conn = audit_repo()._conn
    conn.execute(_DECISION_DDL)
    return conn


# -- evidence browsing ----------------------------------------------------
@router.get("/evidence/runs")
def list_runs() -> dict:
    """All intelligence runs, newest first — the browser's outputs pane."""
    ctx = graph_context()
    with _lock:
        rows = ctx.provenance._conn.execute(
            "SELECT * FROM IntelligenceRun ORDER BY generated_at DESC, rowid DESC LIMIT 200"
        ).fetchall()
    return {
        "synthetic": True,
        "runs": [
            {
                "run_id": r["run_id"],
                "intelligence_type": r["intelligence_type"],
                "method_name": r["method_name"],
                "method_version": r["method_version"],
                "model_version": r["model_version"],
                "window_from": r["analysis_window_from"],
                "window_to": r["analysis_window_to"],
                "status": r["status"],
                "error": r["error"],
                "generated_at": r["generated_at"],
                "record_count": r["record_count"],
            }
            for r in rows
        ],
    }


@router.get("/evidence/runs/{run_id}")
def run_evidence(run_id: str, limit: int = 100) -> dict:
    """One run's method card + its evidence rows (result → factors → FIRs)."""
    ctx = graph_context()
    with _lock:
        run = ctx.provenance.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"unknown run {run_id}")
        evidence = ctx.provenance.evidence_for_run(run_id)
    return {
        "synthetic": True,
        "run": {
            "run_id": run.run_id,
            "intelligence_type": run.intelligence_type.value,
            "method_name": run.method_name,
            "method_version": run.method_version,
            "model_version": run.model_version,
            "window_from": run.analysis_window_from.isoformat(),
            "window_to": run.analysis_window_to.isoformat(),
            "status": run.status.value,
            "record_count": run.record_count,
            "generated_at": run.generated_at.isoformat(),
        },
        "evidence_count": len(evidence),
        "evidence": [
            {
                "result_ref": e.result_ref,
                "classification": e.classification.value,
                "evidence_case_ids": list(e.evidence_case_ids[:50]),
                "evidence_case_total": len(e.evidence_case_ids),
                "factors": [f.model_dump() for f in e.factors],
                "limitations": list(e.limitations),
            }
            for e in evidence[:limit]
        ],
        "evidence_truncated": max(0, len(evidence) - limit),
    }


@router.get("/evidence/latest")
def latest_runs_by_type() -> dict:
    """Latest completed run per intelligence type — the EXPLAIN landing view."""
    ctx = graph_context()
    out = []
    with _lock:
        for itype in IntelligenceType:
            run = ctx.provenance.latest_completed_run(itype)
            if run is not None:
                out.append(
                    {
                        "intelligence_type": itype.value,
                        "run_id": run.run_id,
                        "method_name": run.method_name,
                        "method_version": run.method_version,
                        "generated_at": run.generated_at.isoformat(),
                        "record_count": run.record_count,
                    }
                )
    return {"synthetic": True, "latest": out}


# -- persisted decisions (loop closure) ------------------------------------
class DecisionIn(BaseModel):
    kind: Literal["ALERT_ACK", "IDENTITY"]
    target_ref: str  # alert key or identity cluster_id
    decision: str  # ACKNOWLEDGED | CONFIRMED | REJECTED
    scope_district_id: int | None = None


@router.post("/decisions")
def record_decision(
    body: DecisionIn,
    x_kavach_actor: str | None = Header(default=None),
    x_kavach_role: str | None = Header(default=None),
) -> dict:
    """Persist a human decision + write its audit event (ADR-004).

    Decisions survive reload; re-deciding the same target overwrites the
    decision state but every action stays in the append-only audit trail.
    """
    actor = x_kavach_actor or "demo-analyst"
    role = x_kavach_role or "STATE"
    repo = audit_repo()
    with _lock:
        if body.kind == "IDENTITY":
            event = record_identity_review(
                repo,
                actor_id=actor,
                actor_role=role,
                candidate_id=body.target_ref,
                decision=body.decision,
                scope_district_id=body.scope_district_id,
            )
        else:
            event = repo.record(
                AuditEvent(
                    event_type=AuditEventType.ALERT_REVIEW,
                    actor_id=actor,
                    actor_role=role,
                    scope_district_id=body.scope_district_id,
                    target_refs=(f"alert:{body.target_ref}",),
                    detail={"decision": body.decision},
                )
            )
        conn = _decision_conn()
        with conn:
            conn.execute(
                "INSERT INTO Decision (target_ref, kind, decision, actor_id, actor_role, "
                "decided_at) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(target_ref) DO UPDATE SET kind=excluded.kind, "
                "decision=excluded.decision, actor_id=excluded.actor_id, "
                "actor_role=excluded.actor_role, decided_at=excluded.decided_at",
                (
                    body.target_ref,
                    body.kind,
                    body.decision,
                    actor,
                    role,
                    event.occurred_at.isoformat(),
                ),
            )
    return {
        "recorded": True,
        "audit_id": event.audit_id,
        "target_ref": body.target_ref,
        "decision": body.decision,
        "decided_at": event.occurred_at.isoformat(),
    }


@router.get("/decisions")
def list_decisions() -> dict:
    """Current decision state per target (UI restore on load)."""
    with _lock:
        rows = _decision_conn().execute(
            "SELECT * FROM Decision ORDER BY decided_at DESC LIMIT 500"
        ).fetchall()
    return {
        "decisions": [
            {
                "target_ref": r["target_ref"],
                "kind": r["kind"],
                "decision": r["decision"],
                "actor_id": r["actor_id"],
                "decided_at": r["decided_at"],
            }
            for r in rows
        ]
    }


@router.get("/evidence/activity")
def recent_activity(limit: int = 30) -> dict:
    """Recent decision activity feed for the Evidence browser's audit rail.

    This is the decision feed (attributable actions), not the raw audit
    table — full audit queries stay SYSTEM_ADMIN-only (/api/v1/audit).
    """
    with _lock:
        rows = _decision_conn().execute(
            "SELECT * FROM Decision ORDER BY decided_at DESC LIMIT ?", (min(limit, 100),)
        ).fetchall()
    return {
        "activity": [
            {
                "text": f"{r['actor_id']} ({r['actor_role']}) — {r['kind']} "
                f"{r['decision']} · {r['target_ref']}",
                "kind": r["kind"],
                "decision": r["decision"],
                "when": r["decided_at"],
            }
            for r in rows
        ]
    }


#: Runs that never left RUNNING/FAILED still appear in /evidence/runs with
#: their status — the browser shows failures honestly (no silent success).
__all__ = ["router", "RunStatus"]
