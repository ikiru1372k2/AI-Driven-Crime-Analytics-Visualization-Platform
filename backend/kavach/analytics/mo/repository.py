"""MO profile persistence (MO-002/#38).

Process-local storage in the dev-fixture SQLite, mirroring
kavach/graph/repository.py. Durable Catalyst NoSQL persistence is MO-003/#39
and deliberately not pre-empted here.

Idempotent by (case_master_id, model_version) as #38 requires: re-running an
extraction replaces that pair rather than accumulating rows, and bumping
MODEL_VERSION produces a new row instead of silently mixing outputs.
"""

from __future__ import annotations

import json
import sqlite3

from kavach.analytics.mo.schema import MoProfile

_DDL = """CREATE TABLE IF NOT EXISTS MoProfile (
    case_master_id INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    extractor TEXT NOT NULL,
    extracted_at TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    run_id TEXT NOT NULL,
    PRIMARY KEY (case_master_id, model_version)
)"""

_FAILED_DDL = """CREATE TABLE IF NOT EXISTS MoExtractionFailure (
    case_master_id INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    reason TEXT NOT NULL,
    run_id TEXT NOT NULL,
    PRIMARY KEY (case_master_id, model_version)
)"""


class MoRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        conn.execute(_DDL)
        conn.execute(_FAILED_DDL)

    def save(self, profile: MoProfile, run_id: str) -> None:
        """Upsert one validated profile. Only called after validation."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO MoProfile (case_master_id, model_version, schema_version, "
                "extractor, extracted_at, profile_json, run_id) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(case_master_id, model_version) DO UPDATE SET "
                "schema_version=excluded.schema_version, extractor=excluded.extractor, "
                "extracted_at=excluded.extracted_at, profile_json=excluded.profile_json, "
                "run_id=excluded.run_id",
                (
                    profile.case_master_id,
                    profile.model_version,
                    profile.schema_version,
                    profile.extractor,
                    profile.extracted_at,
                    profile.model_dump_json(),
                    run_id,
                ),
            )

    def record_failure(
        self, case_master_id: int, model_version: str, reason: str, run_id: str
    ) -> None:
        """EXTRACTION_FAILED — the payload itself is never stored (ADR-006)."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO MoExtractionFailure (case_master_id, model_version, reason, run_id) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(case_master_id, model_version) DO UPDATE SET "
                "reason=excluded.reason, run_id=excluded.run_id",
                (case_master_id, model_version, reason[:500], run_id),
            )

    def get(self, case_master_id: int, model_version: str | None = None) -> MoProfile | None:
        sql = "SELECT profile_json FROM MoProfile WHERE case_master_id = ?"
        params: list = [case_master_id]
        if model_version:
            sql += " AND model_version = ?"
            params.append(model_version)
        sql += " ORDER BY extracted_at DESC LIMIT 1"
        row = self._conn.execute(sql, params).fetchone()
        return None if row is None else MoProfile.model_validate_json(row["profile_json"])

    def all_profiles(self, model_version: str | None = None) -> list[MoProfile]:
        sql = "SELECT profile_json FROM MoProfile"
        params: list = []
        if model_version:
            sql += " WHERE model_version = ?"
            params.append(model_version)
        sql += " ORDER BY case_master_id"
        return [
            MoProfile.model_validate_json(r["profile_json"])
            for r in self._conn.execute(sql, params).fetchall()
        ]

    def failure_count(self, model_version: str | None = None) -> int:
        sql = "SELECT COUNT(*) AS n FROM MoExtractionFailure"
        params: list = []
        if model_version:
            sql += " WHERE model_version = ?"
            params.append(model_version)
        return int(self._conn.execute(sql, params).fetchone()["n"])

    def profile_payloads(self, model_version: str | None = None) -> list[dict]:
        """Profiles as plain dicts (API serialization)."""
        return [json.loads(p.model_dump_json()) for p in self.all_profiles(model_version)]
