"""Shared test helpers.

Auth (CAT-003/#19) is deny-by-default, so any test exercising a protected
route must present an identity. `install_test_auth` swaps in a header-driven
validator and seeds the requested assignments; tests that assert on 401/403
simply omit the header (see tests/api/test_auth_api.py).
"""

from __future__ import annotations

from kavach.auth import (
    Identity,
    InvalidToken,
    Role,
    RoleAssignment,
    ScopeType,
    reset_role_repo,
    role_repo,
    set_validator,
)

#: Header the test validator reads to establish identity.
TEST_USER_HEADER = "x-test-user"
#: Default statewide identity for tests that are not about authorization.
DEFAULT_TEST_USER = "test-state-analyst"


class HeaderValidator:
    """Test double for Catalyst Auth: header → identity, nothing else."""

    def validate(self, headers: dict[str, str]) -> Identity:
        user = headers.get(TEST_USER_HEADER)
        if not user:
            raise InvalidToken("no token")
        return Identity(user_id=user, email=f"{user}@test.invalid")


def install_test_auth(
    *extra: RoleAssignment, default_user: str = DEFAULT_TEST_USER
) -> dict[str, str]:
    """Install the test validator, seed a statewide default user (+ extras).

    Returns the default auth headers to pass to TestClient.
    """
    reset_role_repo()
    set_validator(HeaderValidator())
    repo = role_repo()
    repo.assign(
        RoleAssignment(
            user_id=default_user, role=Role.SCRB_STATE_ANALYST, scope_type=ScopeType.STATE
        )
    )
    for assignment in extra:
        repo.assign(assignment)
    return {TEST_USER_HEADER: default_user}


def uninstall_test_auth() -> None:
    set_validator(None)
    reset_role_repo()
