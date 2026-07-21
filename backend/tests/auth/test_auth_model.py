"""CAT-003/#19: role/scope model, assignment selection, validator choice."""

import pytest
from pydantic import ValidationError

from kavach.auth import (
    AuthContext,
    DevValidator,
    InvalidToken,
    Role,
    RoleAssignment,
    RoleRepository,
    ScopeType,
    build_validator,
    select_assignment,
)
from kavach.auth.demo_users import DEMO_ASSIGNMENTS, seed_demo_assignments
from kavach.auth.validator import DEV_USER_HEADER, CatalystValidator
from kavach.repositories.dev_fixture import connect


@pytest.fixture()
def repo() -> RoleRepository:
    return RoleRepository(connect())


# -- scope integrity ------------------------------------------------------
def test_scoped_assignment_requires_target():
    with pytest.raises(ValidationError, match="requires a scope_id"):
        RoleAssignment(
            user_id="u", role=Role.DISTRICT_ANALYST, scope_type=ScopeType.DISTRICT
        )
    with pytest.raises(ValidationError, match="must not carry a scope_id"):
        RoleAssignment(
            user_id="u", role=Role.SCRB_STATE_ANALYST, scope_type=ScopeType.STATE, scope_id=44
        )


def test_district_scope_narrows_only_district_roles():
    district = AuthContext(
        user_id="u", role=Role.DISTRICT_ANALYST, scope_type=ScopeType.DISTRICT, scope_id=44
    )
    assert district.district_scope == 44
    assert district.unit_scope is None
    assert not district.is_statewide

    state = AuthContext(user_id="u", role=Role.SCRB_STATE_ANALYST, scope_type=ScopeType.STATE)
    assert state.district_scope is None and state.is_statewide

    unit = AuthContext(
        user_id="u", role=Role.INVESTIGATOR, scope_type=ScopeType.UNIT, scope_id=4430
    )
    assert unit.unit_scope == 4430
    # a unit-scoped user is NOT granted the whole district by default
    assert unit.district_scope is None and not unit.is_statewide


def test_admin_role_is_statewide_even_if_assignment_is_narrow():
    admin = AuthContext(
        user_id="u", role=Role.SYSTEM_ADMIN, scope_type=ScopeType.DISTRICT, scope_id=44
    )
    assert admin.is_statewide and admin.district_scope is None


def test_only_admin_reads_audit():
    for role in Role:
        ctx = AuthContext(user_id="u", role=role, scope_type=ScopeType.STATE)
        assert ctx.may_read_audit() is (role is Role.SYSTEM_ADMIN)


# -- multi-role resolution (documented priority) ---------------------------
def test_multiple_roles_resolve_by_documented_priority():
    assignments = [
        RoleAssignment(
            user_id="u", role=Role.INVESTIGATOR, scope_type=ScopeType.UNIT, scope_id=4430
        ),
        RoleAssignment(
            user_id="u", role=Role.DISTRICT_ANALYST, scope_type=ScopeType.DISTRICT, scope_id=44
        ),
    ]
    assert select_assignment(assignments).role is Role.DISTRICT_ANALYST
    assignments.append(
        RoleAssignment(user_id="u", role=Role.SCRB_STATE_ANALYST, scope_type=ScopeType.STATE)
    )
    assert select_assignment(assignments).role is Role.SCRB_STATE_ANALYST


def test_equal_roles_resolve_to_broadest_then_lowest_id():
    a = RoleAssignment(
        user_id="u", role=Role.DISTRICT_ANALYST, scope_type=ScopeType.DISTRICT, scope_id=44
    )
    b = RoleAssignment(
        user_id="u", role=Role.DISTRICT_ANALYST, scope_type=ScopeType.DISTRICT, scope_id=12
    )
    assert select_assignment([a, b]).scope_id == 12  # deterministic


# -- repository -----------------------------------------------------------
def test_no_assignment_means_no_access(repo):
    assert repo.effective_assignment("stranger") is None


def test_assignment_round_trip_and_idempotent_reassign(repo):
    a = RoleAssignment(
        user_id="u1", role=Role.DISTRICT_ANALYST, scope_type=ScopeType.DISTRICT, scope_id=44
    )
    repo.assign(a)
    repo.assign(a)  # idempotent
    assert repo.assignments_for("u1") == [a]
    effective = repo.effective_assignment("u1")
    assert effective.role is Role.DISTRICT_ANALYST and effective.scope_id == 44


def test_demo_assignments_cover_every_role(repo):
    seed_demo_assignments(repo)
    roles = {repo.effective_assignment(a.user_id).role for a in DEMO_ASSIGNMENTS}
    assert roles == set(Role)


# -- validator selection (fail closed) -------------------------------------
def test_dev_validator_requires_explicit_optin(monkeypatch):
    monkeypatch.delenv("KAVACH_ENV", raising=False)
    monkeypatch.delenv("CATALYST_PROJECT_ID", raising=False)
    monkeypatch.delenv("KAVACH_DEV_AUTH", raising=False)
    # no opt-in -> the Catalyst validator, which denies locally
    assert isinstance(build_validator(), CatalystValidator)
    monkeypatch.setenv("KAVACH_DEV_AUTH", "1")
    assert isinstance(build_validator(), DevValidator)


def test_dev_auth_never_active_in_catalyst_runtime(monkeypatch):
    monkeypatch.setenv("KAVACH_DEV_AUTH", "1")  # even with the opt-in set
    monkeypatch.setenv("KAVACH_ENV", "catalyst")
    assert isinstance(build_validator(), CatalystValidator)


def test_dev_validator_rejects_missing_user_header():
    with pytest.raises(InvalidToken):
        DevValidator().validate({})
    identity = DevValidator().validate({DEV_USER_HEADER: "demo-admin"})
    assert identity.user_id == "demo-admin"


def test_catalyst_validator_rejects_request_without_catalyst_context():
    """Forged/absent token: the SDK cannot establish a user → InvalidToken."""
    with pytest.raises(InvalidToken):
        CatalystValidator().validate({"authorization": "Bearer forged.token.value"})


# -- deployed demo identity (explicit opt-in, not a security control) -------
def test_demo_identity_requires_explicit_optin(monkeypatch):
    from kavach.auth.validator import DemoIdentityValidator

    monkeypatch.delenv("KAVACH_DEMO_IDENTITY", raising=False)
    monkeypatch.setenv("KAVACH_ENV", "catalyst")
    assert isinstance(build_validator(), CatalystValidator)  # denies by default

    monkeypatch.setenv("KAVACH_DEMO_IDENTITY", "demo-state-analyst")
    assert isinstance(build_validator(), DemoIdentityValidator)


def test_demo_identity_used_only_without_a_real_session(monkeypatch):
    from kavach.auth.validator import DemoIdentityValidator

    v = DemoIdentityValidator("demo-state-analyst")
    # no Catalyst context in the request -> the demo user
    assert v.validate({}).user_id == "demo-state-analyst"


def test_demo_identity_does_not_grant_admin(repo):
    """The audit trail must stay SYSTEM_ADMIN-only even in demo mode."""
    seed_demo_assignments(repo)
    demo = repo.effective_assignment("demo-state-analyst")
    assert demo.role is Role.SCRB_STATE_ANALYST
    ctx = AuthContext(
        user_id=demo.user_id, role=demo.role, scope_type=demo.scope_type, scope_id=demo.scope_id
    )
    assert not ctx.may_read_audit()
