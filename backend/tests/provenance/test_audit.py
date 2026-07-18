"""PROV-003/#26: append-only audit trail — recording, immutability, authz."""

import sqlite3

import pytest

from kavach.provenance.audit import (
    SYSTEM_ADMIN,
    AuditError,
    AuditEvent,
    AuditEventType,
    AuditRepository,
    record_identity_review,
    record_report_generation,
    record_sensitive_case_access,
)
from kavach.repositories.dev_fixture import connect


@pytest.fixture()
def repo() -> AuditRepository:
    return AuditRepository(connect())


def test_identity_review_writes_exactly_one_event(repo):
    record_identity_review(
        repo,
        actor_id="reviewer-7",
        actor_role="DISTRICT",
        candidate_id="cand-42",
        decision="CONFIRMED",
        scope_district_id=44,
    )
    events = repo.query(requester_role=SYSTEM_ADMIN)
    assert len(events) == 1
    (e,) = events
    assert e.event_type is AuditEventType.IDENTITY_REVIEW_DECISION
    assert e.actor_id == "reviewer-7"
    assert e.detail == {"decision": "CONFIRMED"}
    assert e.target_refs == ("candidate:cand-42",)
    assert e.occurred_at is not None


def test_sensitive_case_access_targets_are_ids_only(repo):
    record_sensitive_case_access(
        repo,
        actor_id="analyst-1",
        actor_role="STATE",
        case_master_ids=[101, 102],
        surface="case-detail",
    )
    (e,) = repo.query(requester_role=SYSTEM_ADMIN)
    assert e.target_refs == ("CaseMasterID:101", "CaseMasterID:102")
    assert e.detail == {"surface": "case-detail", "case_count": 2}


def test_no_update_or_delete_path_exists(repo):
    record_report_generation(
        repo, actor_id="a", actor_role="STATE", report_ref="weekly-1"
    )
    conn = repo._conn
    # DB level: triggers abort raw UPDATE/DELETE even outside the repository
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE AuditEvent SET actor_id = 'tampered'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM AuditEvent")
    # API level: the repository exposes no mutating methods at all
    mutating = [
        m for m in dir(repo)
        if not m.startswith("_") and any(v in m for v in ("update", "delete", "remove"))
    ]
    assert mutating == []


def test_detail_pii_guard(repo):
    with pytest.raises(AuditError, match="PII-free"):
        repo.record(
            AuditEvent(
                event_type=AuditEventType.SENSITIVE_CASE_ACCESS,
                actor_id="a",
                actor_role="STATE",
                detail={"accused_name": "someone"},
            )
        )
    assert repo.query(requester_role=SYSTEM_ADMIN) == []


def test_occurred_at_is_server_side(repo):
    from datetime import UTC, datetime

    forged = datetime(1999, 1, 1, tzinfo=UTC)
    stored = repo.record(
        AuditEvent(
            event_type=AuditEventType.ALERT_REVIEW,
            actor_id="a",
            actor_role="UNIT",
            occurred_at=forged,  # caller-supplied timestamps are ignored
        )
    )
    assert stored.occurred_at.year >= 2026


def test_query_requires_system_admin_and_filters(repo):
    record_identity_review(
        repo, actor_id="r1", actor_role="DISTRICT", candidate_id="c1", decision="REJECTED"
    )
    record_report_generation(repo, actor_id="r2", actor_role="STATE", report_ref="x")
    for role in ("STATE", "DISTRICT", "UNIT", ""):
        with pytest.raises(AuditError, match="SYSTEM_ADMIN"):
            repo.query(requester_role=role)
    only_reviews = repo.query(
        requester_role=SYSTEM_ADMIN,
        event_type=AuditEventType.IDENTITY_REVIEW_DECISION,
    )
    assert [e.actor_id for e in only_reviews] == ["r1"]
    assert [e.actor_id for e in repo.query(requester_role=SYSTEM_ADMIN, actor_id="r2")] == ["r2"]
