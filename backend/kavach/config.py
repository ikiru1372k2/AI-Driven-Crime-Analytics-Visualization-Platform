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

    # --- Area-risk forecast (QuickML) -------------------------------------
    #: Published QuickML pipeline endpoint key (the trained regressor that
    #: predicts a district's next-30-day case count). Called live from AppSail
    #: via app.quick_ml().predict(key, row). Unset locally → forecast reports
    #: "unavailable" rather than fabricating a number.
    quickml_risk_endpoint: str | None = os.getenv("KAVACH_QUICKML_RISK_ENDPOINT")
    #: QuickML LLM Serving endpoint URL (Qwen 2.5) for phrasing computed driver
    #: facts in plain English. Optional polish only — never originates numbers.
    quickml_llm_endpoint: str | None = os.getenv("KAVACH_QUICKML_LLM_ENDPOINT")
    #: OAuth token for the LLM Serving endpoint (short-lived; via a Catalyst
    #: connector in production). Unset → the deterministic template sentence is
    #: used instead of the Qwen-polished one.
    quickml_llm_token: str | None = os.getenv("KAVACH_QUICKML_LLM_TOKEN")
    #: Human-readable model id recorded as provenance model_version for the LLM.
    quickml_llm_model: str = os.getenv("KAVACH_QUICKML_LLM_MODEL", "qwen-2.5-14b-instruct")


settings = Settings()
