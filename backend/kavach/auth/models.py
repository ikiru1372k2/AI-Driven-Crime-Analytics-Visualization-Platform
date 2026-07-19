"""Identity, role and scope model (CAT-003/#19).

Scope is resolved SERVER-SIDE from a stored role assignment — never from
anything the client sends. A district analyst cannot widen their own scope
by editing a query string or header, which is the whole point of SEC-001.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class Role(StrEnum):
    SCRB_STATE_ANALYST = "SCRB_STATE_ANALYST"
    DISTRICT_ANALYST = "DISTRICT_ANALYST"
    SUPERVISOR = "SUPERVISOR"
    INVESTIGATOR = "INVESTIGATOR"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class ScopeType(StrEnum):
    STATE = "STATE"
    DISTRICT = "DISTRICT"
    UNIT = "UNIT"


#: Explicit precedence for users holding several assignments (issue #19
#: edge case: "highest-privilege wins? No — explicit priority documented").
#: Order is by breadth of legitimate data access, most senior first. It is
#: a documented, reviewable list rather than an implicit max() over an enum.
ROLE_PRIORITY: tuple[Role, ...] = (
    Role.SYSTEM_ADMIN,
    Role.SCRB_STATE_ANALYST,
    Role.SUPERVISOR,
    Role.DISTRICT_ANALYST,
    Role.INVESTIGATOR,
)

#: Roles allowed to read the audit trail (PROV-003/#26 keeps this narrow).
AUDIT_READER_ROLES = frozenset({Role.SYSTEM_ADMIN})

#: Roles whose scope is the whole state regardless of assignment target.
STATEWIDE_ROLES = frozenset({Role.SYSTEM_ADMIN, Role.SCRB_STATE_ANALYST})


class RoleAssignment(BaseModel):
    """One stored user↔role↔scope mapping (DERIVED table)."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    role: Role
    scope_type: ScopeType
    scope_id: int | None = None  # District.DistrictID or Unit.UnitID

    @model_validator(mode="after")
    def _scope_target_required(self) -> RoleAssignment:
        if self.scope_type is ScopeType.STATE:
            if self.scope_id is not None:
                raise ValueError("STATE scope must not carry a scope_id")
        elif self.scope_id is None:
            raise ValueError(f"{self.scope_type.value} scope requires a scope_id")
        return self


class AuthContext(BaseModel):
    """Resolved identity for one request — what handlers are allowed to see."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    email: str | None = None
    role: Role
    scope_type: ScopeType
    scope_id: int | None = None

    @property
    def is_statewide(self) -> bool:
        return self.scope_type is ScopeType.STATE or self.role in STATEWIDE_ROLES

    @property
    def district_scope(self) -> int | None:
        """District id this request is confined to, or None for statewide.

        UNIT scope is narrower than district; callers that filter by district
        get the unit's district via `scope_id` resolution at the call site.
        """
        if self.is_statewide:
            return None
        return self.scope_id if self.scope_type is ScopeType.DISTRICT else None

    @property
    def unit_scope(self) -> int | None:
        if self.is_statewide:
            return None
        return self.scope_id if self.scope_type is ScopeType.UNIT else None

    def may_read_audit(self) -> bool:
        return self.role in AUDIT_READER_ROLES


def select_assignment(assignments: list[RoleAssignment]) -> RoleAssignment:
    """Pick the effective assignment for a user with several roles.

    Documented rule: the earliest role in ROLE_PRIORITY wins; among equal
    roles the broadest scope wins (STATE > DISTRICT > UNIT), then the
    lowest scope_id for determinism.
    """
    if not assignments:
        raise ValueError("no assignments")
    scope_rank = {ScopeType.STATE: 0, ScopeType.DISTRICT: 1, ScopeType.UNIT: 2}
    return min(
        assignments,
        key=lambda a: (
            ROLE_PRIORITY.index(a.role),
            scope_rank[a.scope_type],
            a.scope_id if a.scope_id is not None else -1,
        ),
    )
