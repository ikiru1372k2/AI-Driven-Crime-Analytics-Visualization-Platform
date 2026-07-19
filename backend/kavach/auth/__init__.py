"""Authentication, roles and scope (CAT-003/#19)."""

from kavach.auth.dependency import (
    CurrentUser,
    current_auth,
    require_role,
    reset_role_repo,
    role_repo,
    set_validator,
)
from kavach.auth.models import (
    AUDIT_READER_ROLES,
    ROLE_PRIORITY,
    STATEWIDE_ROLES,
    AuthContext,
    Role,
    RoleAssignment,
    ScopeType,
    select_assignment,
)
from kavach.auth.repository import RoleRepository
from kavach.auth.validator import (
    DEV_USER_HEADER,
    CatalystValidator,
    DevValidator,
    Identity,
    InvalidToken,
    TokenValidator,
    build_validator,
)

__all__ = [
    "AUDIT_READER_ROLES",
    "DEV_USER_HEADER",
    "ROLE_PRIORITY",
    "STATEWIDE_ROLES",
    "AuthContext",
    "CatalystValidator",
    "CurrentUser",
    "DevValidator",
    "Identity",
    "InvalidToken",
    "Role",
    "RoleAssignment",
    "RoleRepository",
    "ScopeType",
    "TokenValidator",
    "build_validator",
    "current_auth",
    "require_role",
    "reset_role_repo",
    "role_repo",
    "select_assignment",
    "set_validator",
]
