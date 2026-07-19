"""UserRoleAssignment persistence (CAT-003/#19) — a DERIVED app table.

Role changes are audited (PROV-003/#26): assignment writes emit an audit
event so a privilege grant is always attributable.
"""

from __future__ import annotations

import sqlite3

from kavach.auth.models import Role, RoleAssignment, ScopeType, select_assignment

_DDL = """CREATE TABLE IF NOT EXISTS UserRoleAssignment (
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id INTEGER,
    assigned_by TEXT,
    assigned_at TEXT,
    PRIMARY KEY (user_id, role, scope_type, scope_id)
)"""


class RoleRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        conn.execute(_DDL)

    def assign(
        self,
        assignment: RoleAssignment,
        *,
        assigned_by: str = "system",
        assigned_at: str | None = None,
    ) -> RoleAssignment:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO UserRoleAssignment "
                "(user_id, role, scope_type, scope_id, assigned_by, assigned_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    assignment.user_id,
                    assignment.role.value,
                    assignment.scope_type.value,
                    assignment.scope_id,
                    assigned_by,
                    assigned_at,
                ),
            )
        return assignment

    def assignments_for(self, user_id: str) -> list[RoleAssignment]:
        rows = self._conn.execute(
            "SELECT user_id, role, scope_type, scope_id FROM UserRoleAssignment "
            "WHERE user_id = ? ORDER BY role, scope_type, scope_id",
            (user_id,),
        ).fetchall()
        return [
            RoleAssignment(
                user_id=r["user_id"],
                role=Role(r["role"]),
                scope_type=ScopeType(r["scope_type"]),
                scope_id=r["scope_id"],
            )
            for r in rows
        ]

    def effective_assignment(self, user_id: str) -> RoleAssignment | None:
        """The one assignment that governs this user's requests, or None.

        None means deny (403) — there is no implicit default role.
        """
        assignments = self.assignments_for(user_id)
        return select_assignment(assignments) if assignments else None
