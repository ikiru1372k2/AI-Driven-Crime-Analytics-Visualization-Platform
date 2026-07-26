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
        # The profile corpus is loaded once per process (see _store in
        # api/mo_routes.py) and only mutated by save(); every read endpoint
        # otherwise re-validated and re-serialized all ~16k rows on each
        # request, which timed the function out. Memoize the full-corpus reads
        # and drop the caches whenever a write lands.
        self._profiles_cache: dict[str | None, list[MoProfile]] = {}
        self._payload_cache: dict[str | None, list[dict]] = {}
        conn.execute(_DDL)
        conn.execute(_FAILED_DDL)

    def _invalidate(self) -> None:
        self._profiles_cache.clear()
        self._payload_cache.clear()

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
        self._invalidate()

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
        if model_version not in self._profiles_cache:
            sql = "SELECT profile_json FROM MoProfile"
            params: list = []
            if model_version:
                sql += " WHERE model_version = ?"
                params.append(model_version)
            sql += " ORDER BY case_master_id"
            self._profiles_cache[model_version] = [
                MoProfile.model_validate_json(r["profile_json"])
                for r in self._conn.execute(sql, params).fetchall()
            ]
        return self._profiles_cache[model_version]

    def failure_count(self, model_version: str | None = None) -> int:
        sql = "SELECT COUNT(*) AS n FROM MoExtractionFailure"
        params: list = []
        if model_version:
            sql += " WHERE model_version = ?"
            params.append(model_version)
        return int(self._conn.execute(sql, params).fetchone()["n"])

    def profile_count(self, model_version: str | None = None) -> int:
        """How many profiles exist — counted in SQL, without materializing them."""
        sql = "SELECT COUNT(*) AS n FROM MoProfile"
        params: list = []
        if model_version:
            sql += " WHERE model_version = ?"
            params.append(model_version)
        return int(self._conn.execute(sql, params).fetchone()["n"])

    def profile_payloads(self, model_version: str | None = None) -> list[dict]:
        """Profiles as plain dicts (API serialization).

        Read straight from the stored JSON: the rows were validated on save, so
        parsing the text once beats the model_validate_json -> model_dump_json
        -> json.loads round-trip this used to do over the whole corpus per
        request. Memoized because the corpus is immutable between writes.
        """
        if model_version not in self._payload_cache:
            sql = "SELECT profile_json FROM MoProfile"
            params: list = []
            if model_version:
                sql += " WHERE model_version = ?"
                params.append(model_version)
            sql += " ORDER BY case_master_id"
            self._payload_cache[model_version] = [
                json.loads(r["profile_json"])
                for r in self._conn.execute(sql, params).fetchall()
            ]
        return self._payload_cache[model_version]
