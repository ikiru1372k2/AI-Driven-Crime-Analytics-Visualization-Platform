"""Runtime configuration.

All Catalyst credentials/identifiers come from environment variables — never
from the repository (see ADR-001). Defaults support local development only.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    env: str = os.getenv("KAVACH_ENV", "local")
    #: Catalyst project id. ``CATALYST_*`` is a reserved env prefix in the AppSail
    #: runtime — it cannot be set in app-config.json's ``env_variables`` (the deploy
    #: is rejected with HTTP 400 "reserved keywords"), so the deploy maps the id to
    #: the non-reserved ``KAVACH_CATALYST_PROJECT_ID`` alias. Read that first, then
    #: the plain name (used locally / in CI where nothing is reserved).
    catalyst_project_id: str | None = (
        os.getenv("KAVACH_CATALYST_PROJECT_ID") or os.getenv("CATALYST_PROJECT_ID")
    )
    catalyst_env_id: str | None = os.getenv("CATALYST_ENV_ID")

    # --- Data source selector (CAT-002 / PR-B) ----------------------------
    #: Where the analytics API reads its rows from: ``"csv"`` (bundled synthetic
    #: CSVs, the default — prod-safe) or ``"datastore"`` (live Catalyst Data
    #: Store via OAuth REST, so console edits show up in the app). Anything else
    #: is treated as ``"csv"``. Defaults to CSV so no deploy changes behaviour
    #: until this flag is deliberately flipped.
    data_source: str = os.getenv("KAVACH_DATA_SOURCE", "csv")
    #: Catalyst Data Store REST base (IN data center by default). Combined with
    #: the project id to form ``/baas/v1/project/<id>`` (mirrors the seed tool).
    datastore_api_base: str = os.getenv(
        "KAVACH_DATASTORE_API_BASE", "https://api.catalyst.zoho.in"
    )
    #: Self-client refresh token scoped ``ZohoCatalyst.zcql.CREATE`` (the ZCQL
    #: execute-query scope — named CREATE even for SELECT, since it executes a
    #: query resource; ``tables.rows.READ`` only covers the non-paging row API we
    #: don't use). A DIFFERENT scope from the QuickML token, minted as a separate
    #: console step. Falls back to the shared refresh token if unset. Never
    #: committed (ADR-001).
    datastore_refresh_token: str | None = os.getenv("KAVACH_DATASTORE_REFRESH_TOKEN")
    #: Seconds a fetched table is cached before a re-read picks up console edits.
    #: Short enough to feel live, long enough that a burst of requests shares one
    #: fetch. ``0`` disables caching (every call re-reads — for tests/debug).
    datastore_cache_ttl: float = float(os.getenv("KAVACH_DATASTORE_TTL", "300"))

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
    #: QuickML LLM Serving endpoint URL (GLM chat, ``/glm/chat``) for phrasing
    #: computed driver facts in plain English. Optional polish only — never
    #: originates numbers. Unset → the deterministic template sentence is used.
    quickml_llm_endpoint: str | None = os.getenv("KAVACH_QUICKML_LLM_ENDPOINT")
    #: OAuth token for the LLM endpoint. Unset → the minted self-client access
    #: token is reused (same QuickML.deployment.READ scope).
    quickml_llm_token: str | None = os.getenv("KAVACH_QUICKML_LLM_TOKEN")
    #: The API ``model`` id sent in the chat request (e.g. the deployed GLM id
    #: ``crm-di-glm47b_30b_it``). Unset → the LLM polish is skipped (template).
    quickml_llm_model_id: str | None = os.getenv("KAVACH_QUICKML_LLM_MODEL_ID")
    #: Friendly model name shown to users as provenance (summary_source /
    #: model_version) — kept separate from the cryptic API id above.
    quickml_llm_model: str = os.getenv("KAVACH_QUICKML_LLM_MODEL", "GLM-4.7")


settings = Settings()
