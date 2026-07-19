"""Demo role assignments (CAT-003/#19 acceptance criterion 4).

These are ROLE ASSIGNMENTS, not credentials: no passwords or tokens live
here. Real identities come from Catalyst Authentication; this table maps
an authenticated user id to what they may see. For the hosted demo the
ids are the Catalyst user ids of the seeded accounts; locally they double
as the `x-kavach-dev-user` header values (dev auth only).

Documented in docs/catalyst/auth-and-roles.md.
"""

from __future__ import annotations

from kavach.auth.models import Role, RoleAssignment, ScopeType
from kavach.auth.repository import RoleRepository

#: district 44 = Bengaluru City, unit 4430 = Peenya PS (the demo hotspot).
DEMO_ASSIGNMENTS: tuple[RoleAssignment, ...] = (
    RoleAssignment(
        user_id="demo-state-analyst",
        role=Role.SCRB_STATE_ANALYST,
        scope_type=ScopeType.STATE,
    ),
    RoleAssignment(
        user_id="demo-district-analyst",
        role=Role.DISTRICT_ANALYST,
        scope_type=ScopeType.DISTRICT,
        scope_id=44,
    ),
    RoleAssignment(
        user_id="demo-supervisor",
        role=Role.SUPERVISOR,
        scope_type=ScopeType.DISTRICT,
        scope_id=44,
    ),
    RoleAssignment(
        user_id="demo-investigator",
        role=Role.INVESTIGATOR,
        scope_type=ScopeType.UNIT,
        scope_id=4430,
    ),
    RoleAssignment(
        user_id="demo-admin",
        role=Role.SYSTEM_ADMIN,
        scope_type=ScopeType.STATE,
    ),
)


def seed_demo_assignments(repo: RoleRepository, *, assigned_by: str = "demo-seed") -> int:
    """Idempotently seed the demo assignments; returns how many were written."""
    for assignment in DEMO_ASSIGNMENTS:
        repo.assign(assignment, assigned_by=assigned_by)
    return len(DEMO_ASSIGNMENTS)
