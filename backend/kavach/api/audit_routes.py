"""Audit query API (PROV-003/#26) — reads restricted to SYSTEM_ADMIN.

Events are recorded server-side through kavach.provenance.audit helpers —
there is deliberately no write endpoint. The requester's role comes from
the authenticated Catalyst session (CAT-003/#19), never from a header.
"""

from __future__ import annotations

import functools
import threading

from fastapi import APIRouter, HTTPException, Query

from kavach.auth import CurrentUser
from kavach.provenance.audit import (
    AuditError,
    AuditEventType,
    AuditRepository,
)
from kavach.repositories.dev_fixture import connect

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

#: Serializes SQLite access across FastAPI worker threads (the connection is
#: shared with check_same_thread=False). Non-reentrant — never hold it while
#: calling another function that takes it.
_lock = threading.Lock()


@functools.lru_cache(maxsize=1)
def _repo() -> AuditRepository:
    """Process-wide audit store (LOCAL path; Data Store adapter via #18)."""
    return AuditRepository(connect(check_same_thread=False))


def audit_repo() -> AuditRepository:
    return _repo()


def reset_audit_repo() -> None:
    """Test hook."""
    _repo.cache_clear()


@router.get("")
def query_audit(
    auth: CurrentUser,
    event_type: AuditEventType | None = None,
    actor_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    """Audit trail query — SYSTEM_ADMIN only (#26 AC3).

    The role comes from the authenticated session (CAT-003/#19); it is no
    longer client-supplied, so a header can no longer claim SYSTEM_ADMIN.
    """
    try:
        with _lock:
            events = audit_repo().query(
                requester_role=auth.role.value,
                event_type=event_type,
                actor_id=actor_id,
                limit=limit,
            )
    except AuditError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {
        "count": len(events),
        "events": [e.model_dump(mode="json") for e in events],
    }
