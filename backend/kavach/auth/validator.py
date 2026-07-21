"""Token validation (CAT-003/#19).

Identity comes from Catalyst Authentication. Two validators implement the
same protocol so handlers never care which is active:

- CatalystValidator — the real one. Initializes the Catalyst SDK with the
  incoming request headers and reads the authenticated user. Used whenever
  the runtime is Catalyst.
- DevValidator — local development only. Requires BOTH a non-Catalyst
  runtime AND an explicit KAVACH_DEV_AUTH=1 opt-in, so it can never
  silently authenticate anyone in a deployed environment.

Nothing here trusts a client-supplied role or scope: the validator only
establishes *who* the caller is; *what they may see* is resolved from the
stored assignment (repository.py).
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

logger = logging.getLogger(__name__)

#: Header a local developer sets to choose a seeded demo identity.
DEV_USER_HEADER = "x-kavach-dev-user"


class InvalidToken(Exception):
    """Raised when no valid authenticated identity is present (→ 401)."""


class Identity:
    """Authenticated principal — identity only, no authorization."""

    def __init__(self, user_id: str, email: str | None = None):
        self.user_id = user_id
        self.email = email


class TokenValidator(Protocol):
    def validate(self, headers: dict[str, str]) -> Identity: ...


class CatalystValidator:
    """Validates the caller through Catalyst Authentication."""

    def validate(self, headers: dict[str, str]) -> Identity:
        try:
            import zcatalyst_sdk  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - deployed runtime only
            raise InvalidToken("zcatalyst-sdk unavailable in runtime") from exc
        try:
            app = zcatalyst_sdk.initialize(req=headers)
            user = app.authentication().get_current_user()
        except Exception as exc:  # noqa: BLE001 - SDK raises broad errors
            # includes expired/forged tokens and missing Catalyst headers
            raise InvalidToken(f"catalyst auth failed: {type(exc).__name__}") from exc
        if not user:
            raise InvalidToken("no authenticated user in request")
        user_id = str(user.get("user_id") or user.get("zuid") or "").strip()
        if not user_id:
            raise InvalidToken("authenticated user has no id")
        return Identity(user_id=user_id, email=user.get("email_id"))


class DevValidator:
    """Local-only validator — never active in a Catalyst runtime."""

    def validate(self, headers: dict[str, str]) -> Identity:
        user_id = headers.get(DEV_USER_HEADER, "").strip()
        if not user_id:
            raise InvalidToken(
                f"local dev auth: set the {DEV_USER_HEADER} header to a seeded demo user"
            )
        return Identity(user_id=user_id, email=f"{user_id}@demo.invalid")


class DemoIdentityValidator:
    """Deployed-demo fallback: a real Catalyst session wins; if there is none,
    the request is treated as a FIXED, named demo user.

    Why this exists: the console has no sign-in screen yet (that is #60), so
    without a fallback the deployed demo cannot open a node detail panel or
    record a review decision. Enabled ONLY by setting KAVACH_DEMO_IDENTITY,
    and the identity it grants is an ordinary analyst — SYSTEM_ADMIN-only
    surfaces such as the audit trail stay denied, so the authorization model
    is still demonstrably enforced.

    This is a demo affordance on SYNTHETIC data (ADR-011), NOT a security
    control. Do not set this variable on anything holding real FIR data.
    """

    def __init__(self, demo_user: str):
        self.demo_user = demo_user
        self._catalyst = CatalystValidator()

    def validate(self, headers: dict[str, str]) -> Identity:
        try:
            return self._catalyst.validate(headers)
        except InvalidToken:
            return Identity(user_id=self.demo_user, email=f"{self.demo_user}@demo.invalid")


def is_catalyst_runtime() -> bool:
    return bool(
        os.environ.get("KAVACH_ENV") == "catalyst" or os.environ.get("CATALYST_PROJECT_ID")
    )


def demo_identity() -> str | None:
    """The configured deployed-demo identity, if any."""
    return os.environ.get("KAVACH_DEMO_IDENTITY") or None


def build_validator() -> TokenValidator:
    """Choose the validator for this runtime — fail closed.

    Order: a real Catalyst session always wins. The two fallbacks each need
    their own explicit opt-in; with neither set we return the Catalyst
    validator, which denies rather than inventing an identity.
    """
    demo_user = demo_identity()
    if demo_user:
        logger.warning(
            "KAVACH_DEMO_IDENTITY=%s: unauthenticated requests are treated as this "
            "demo analyst because the console has no sign-in screen yet (#60). "
            "Demo affordance on SYNTHETIC data — never enable this with real FIRs.",
            demo_user,
        )
        return DemoIdentityValidator(demo_user)
    if not is_catalyst_runtime() and os.environ.get("KAVACH_DEV_AUTH") == "1":
        logger.warning(
            "KAVACH_DEV_AUTH=1: header-based dev identities are enabled. "
            "This is for local development only."
        )
        return DevValidator()
    return CatalystValidator()
