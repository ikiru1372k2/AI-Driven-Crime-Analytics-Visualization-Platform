"""Runtime configuration.

All Catalyst credentials/identifiers come from environment variables — never
from the repository (see ADR-001). Defaults support local development only.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    env: str = os.getenv("KAVACH_ENV", "local")
    catalyst_project_id: str | None = os.getenv("CATALYST_PROJECT_ID")
    catalyst_env_id: str | None = os.getenv("CATALYST_ENV_ID")


settings = Settings()
