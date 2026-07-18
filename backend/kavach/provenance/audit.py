"""Append-only audit logging for sensitive actions (PROV-003/#26, ADR-004).

Records identity-review decisions, sensitive case-detail access (narratives/
names visible), alert review actions and report generation — with actor,
role, scope, timestamp and target refs. Audit rows contain IDs only, never
names or narratives. There is NO update or delete path: SQLite triggers
abort both at the DB level, and the repository exposes no mutating API.

Actor identity: until Catalyst Authentication (CAT-003/#19) lands, the
actor/role arrive through explicit parameters (the same enforcement seam as
scope_district_id in the graph API); #19 binds them to the authenticated
session without changing this module.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

#: Role vocabulary (subset of #19's STATE/DISTRICT/UNIT model + admin).
SYSTEM_ADMIN = "SYSTEM_ADMIN"


class AuditEventType(StrEnum):
    IDENTITY_REVIEW_DECISION = "IDENTITY_REVIEW_DECISION"
    SENSITIVE_CASE_ACCESS = "SENSITIVE_CASE_ACCESS"
    ALERT_REVIEW = "ALERT_REVIEW"
    REPORT_GENERATION = "REPORT_GENERATION"


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    audit_id: int | None = None  # assigned by the store
    event_type: AuditEventType
    actor_id: str
    actor_role: str
    scope_district_id: int | None = None
    scope_unit_id: int | None = None
    target_refs: tuple[str, ...] = ()  # IDs only (CaseMasterID:…, candidate:…)
    detail: dict = {}  # structured, PII-free (guarded below)
    occurred_at: datetime | None = None  # server-side


#: Keys that must never appear in audit detail payloads (PII guard).
_PROHIBITED_DETAIL_KEYS = {"name", "names", "accused_name", "victim_name", "narrative",
                           "brief_facts", "brieffacts", "complainant_name"}

_DDL = """CREATE TABLE IF NOT EXISTS AuditEvent (
    audit_id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    scope_district_id INTEGER,
    scope_unit_id INTEGER,
    target_refs TEXT NOT NULL,
    detail TEXT NOT NULL,
    occurred_at TEXT NOT NULL
)"""

#: DB-level append-only enforcement: any UPDATE or DELETE aborts.
_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON AuditEvent
       BEGIN SELECT RAISE(ABORT, 'audit rows are append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON AuditEvent
       BEGIN SELECT RAISE(ABORT, 'audit rows are append-only'); END""",
]


class AuditError(RuntimeError):
    """Raised on PII in detail payloads or unauthorized audit queries."""


class AuditRepository:
    """Append + query only. No update/delete methods exist by design."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        conn.execute(_DDL)
        for trg in _TRIGGERS:
            conn.execute(trg)

    def record(self, event: AuditEvent) -> AuditEvent:
        lowered = {k.lower() for k in event.detail}
        banned = lowered & _PROHIBITED_DETAIL_KEYS
        if banned:
            raise AuditError(f"audit detail must be PII-free; prohibited keys: {sorted(banned)}")
        occurred = datetime.now(UTC)  # server-side, never caller-supplied
        cur = self._conn.execute(
            "INSERT INTO AuditEvent (event_type, actor_id, actor_role, "
            "scope_district_id, scope_unit_id, target_refs, detail, occurred_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_type.value,
                event.actor_id,
                event.actor_role,
                event.scope_district_id,
                event.scope_unit_id,
                json.dumps(list(event.target_refs)),
                json.dumps(event.detail),
                occurred.isoformat(),
            ),
        )
        return event.model_copy(update={"audit_id": cur.lastrowid, "occurred_at": occurred})

    def query(
        self,
        *,
        requester_role: str,
        event_type: AuditEventType | None = None,
        actor_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Audit reads are restricted to SYSTEM_ADMIN (#26 AC3)."""
        if requester_role != SYSTEM_ADMIN:
            raise AuditError("audit query requires SYSTEM_ADMIN role")
        sql = "SELECT * FROM AuditEvent"
        clauses, params = [], []
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type.value)
        if actor_id is not None:
            clauses.append("actor_id = ?")
            params.append(actor_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY audit_id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [
            AuditEvent(
                audit_id=r["audit_id"],
                event_type=AuditEventType(r["event_type"]),
                actor_id=r["actor_id"],
                actor_role=r["actor_role"],
                scope_district_id=r["scope_district_id"],
                scope_unit_id=r["scope_unit_id"],
                target_refs=tuple(json.loads(r["target_refs"])),
                detail=json.loads(r["detail"]),
                occurred_at=datetime.fromisoformat(r["occurred_at"]),
            )
            for r in rows
        ]


# -- route-handler helpers ----------------------------------------------
def record_identity_review(
    repo: AuditRepository,
    *,
    actor_id: str,
    actor_role: str,
    candidate_id: str,
    decision: str,
    scope_district_id: int | None = None,
) -> AuditEvent:
    """Exactly one audit event per identity-review decision (ADR-004)."""
    return repo.record(
        AuditEvent(
            event_type=AuditEventType.IDENTITY_REVIEW_DECISION,
            actor_id=actor_id,
            actor_role=actor_role,
            scope_district_id=scope_district_id,
            target_refs=(f"candidate:{candidate_id}",),
            detail={"decision": decision},
        )
    )


def record_sensitive_case_access(
    repo: AuditRepository,
    *,
    actor_id: str,
    actor_role: str,
    case_master_ids: list[int],
    surface: str,
    scope_district_id: int | None = None,
) -> AuditEvent:
    """Case-detail access where PII (names/narratives) is visible."""
    return repo.record(
        AuditEvent(
            event_type=AuditEventType.SENSITIVE_CASE_ACCESS,
            actor_id=actor_id,
            actor_role=actor_role,
            scope_district_id=scope_district_id,
            target_refs=tuple(f"CaseMasterID:{c}" for c in case_master_ids),
            detail={"surface": surface, "case_count": len(case_master_ids)},
        )
    )


def record_report_generation(
    repo: AuditRepository,
    *,
    actor_id: str,
    actor_role: str,
    report_ref: str,
    scope_district_id: int | None = None,
) -> AuditEvent:
    return repo.record(
        AuditEvent(
            event_type=AuditEventType.REPORT_GENERATION,
            actor_id=actor_id,
            actor_role=actor_role,
            scope_district_id=scope_district_id,
            target_refs=(f"report:{report_ref}",),
            detail={},
        )
    )
