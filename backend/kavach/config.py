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
    #: predicts a district's next-30-day case count). Unset locally → forecast
    #: reports "unavailable" rather than fabricating a number.
    quickml_risk_endpoint: str | None = os.getenv("KAVACH_QUICKML_RISK_ENDPOINT")
    #: Published endpoint's predict URL, e.g.
    #: https://api.catalyst.zoho.in/quickml/v1/project/<id>/endpoints/predict
    #: When set together with the self-client trio below, the forecast is served
    #: via OAuth REST (works from the anonymous AppSail runtime, unlike the SDK).
    quickml_risk_url: str | None = os.getenv("KAVACH_QUICKML_RISK_URL")

    # --- Zoho self-client (server-to-server OAuth) ------------------------
    #: A self-client's credentials + a refresh token minted with QuickML scope.
    #: These let the deployed app call QuickML with its OWN identity (no end-user
    #: login / Catalyst gateway headers needed). Never committed (ADR-001).
    zoho_client_id: str | None = os.getenv("KAVACH_ZOHO_CLIENT_ID")
    zoho_client_secret: str | None = os.getenv("KAVACH_ZOHO_CLIENT_SECRET")
    zoho_refresh_token: str | None = os.getenv("KAVACH_ZOHO_REFRESH_TOKEN")
    #: Accounts server for the token exchange — IN data center by default.
    zoho_accounts_url: str = os.getenv("KAVACH_ZOHO_ACCOUNTS_URL", "https://accounts.zoho.in")
    #: Sent as request headers on the predict call (from the endpoint page).
    quickml_org_id: str | None = os.getenv("KAVACH_QUICKML_ORG_ID")
    quickml_environment: str = os.getenv("KAVACH_QUICKML_ENVIRONMENT", "Development")
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
