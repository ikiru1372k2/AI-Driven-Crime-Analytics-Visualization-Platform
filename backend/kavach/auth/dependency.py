"""FastAPI auth dependencies (CAT-003/#19) — deny by default.

    401  no valid authenticated identity
    403  authenticated but no role assignment (no implicit default role)

Handlers depend on `CurrentUser` and receive an AuthContext whose scope was
resolved server-side. There is deliberately no way for a request to widen
its own scope.
"""

from __future__ import annotations

import functools
import threading
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from kavach.auth.models import AuthContext, Role
from kavach.auth.repository import RoleRepository
from kavach.auth.validator import InvalidToken, TokenValidator, build_validator
from kavach.repositories.dev_fixture import connect

_lock = threading.Lock()
_validator_override: TokenValidator | None = None


@functools.lru_cache(maxsize=1)
def _role_repo() -> RoleRepository:
    """Process-wide role store (LOCAL path; Data Store adapter via #18)."""
    return RoleRepository(connect(check_same_thread=False))


def role_repo() -> RoleRepository:
    return _role_repo()


def reset_role_repo() -> None:
    """Test hook."""
    _role_repo.cache_clear()


@functools.lru_cache(maxsize=1)
def _validator() -> TokenValidator:
    return build_validator()


def set_validator(validator: TokenValidator | None) -> None:
    """Test hook: inject a mocked validator (issue #19 test plan)."""
    global _validator_override
    _validator_override = validator
    _validator.cache_clear()


def current_auth(request: Request) -> AuthContext:
    """Resolve the caller's identity, role and scope, or refuse the request."""
    validator = _validator_override or _validator()
    try:
        identity = validator.validate(dict(request.headers))
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    with _lock:
        assignment = role_repo().effective_assignment(identity.user_id)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="no role assignment for this user — access denied",
        )
    return AuthContext(
        user_id=identity.user_id,
        email=identity.email,
        role=assignment.role,
        scope_type=assignment.scope_type,
        scope_id=assignment.scope_id,
    )


CurrentUser = Annotated[AuthContext, Depends(current_auth)]


def require_role(*roles: Role):
    """Dependency factory restricting a route to specific roles."""
    allowed = frozenset(roles)

    def _guard(auth: CurrentUser) -> AuthContext:
        if auth.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role {auth.role.value} may not access this resource",
            )
        return auth

    return _guard
