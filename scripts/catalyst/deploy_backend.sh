#!/usr/bin/env bash
# AppSail backend deployment (CAT-005/#21) — reproducible from clean checkout.
#
# Prerequisites (documented in docs/catalyst/appsail-deployment.md):
#   npm i -g zcatalyst-cli        # Catalyst CLI
#   catalyst login                # authenticate (browser flow)
#     …or, in CI, export CATALYST_TOKEN=<token from catalyst token:generate>
#   export CATALYST_PROJECT_ID=…  CATALYST_ORG_ID=…   # never committed (ADR-001)
#
# What it does: stages the backend into .catalyst-build/appsail (app code +
# requirements + AppSail app-config.json + generated catalyst.json), then
# `catalyst deploy`. AppSail injects X_ZOHO_CATALYST_LISTEN_PORT; the start
# command binds uvicorn to it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="$ROOT/.catalyst-build/appsail"
APP_NAME="${APPSAIL_APP_NAME:-kavach-analytics}"

command -v catalyst >/dev/null || { echo "zcatalyst-cli not installed (npm i -g zcatalyst-cli)"; exit 1; }

# -- deploy secrets ------------------------------------------------------------
# The env_variables block below is regenerated from the SHELL on every deploy, so
# a deploy run without the QuickML/Zoho secrets exported would bake in empty
# strings and silently WIPE the live predictor's credentials (this happened once —
# prod went "unavailable"). To make secrets consistent and the failure loud:
#   1. auto-source a git-ignored scripts/catalyst/deploy.env if present (copy it
#      from deploy.env.example and fill in real values — never committed, ADR-001);
#   2. abort if any predictor secret is empty, unless ALLOW_UNCONFIGURED_QUICKML=1
#      is set for an intentional demo/unconfigured deploy.
DEPLOY_ENV="$ROOT/scripts/catalyst/deploy.env"
if [ -f "$DEPLOY_ENV" ]; then
  echo "sourcing deploy secrets from $DEPLOY_ENV"
  set -a; . "$DEPLOY_ENV"; set +a
fi

if [ "${ALLOW_UNCONFIGURED_QUICKML:-0}" != "1" ]; then
  missing=()
  for v in KAVACH_QUICKML_RISK_ENDPOINT KAVACH_QUICKML_RISK_URL \
           KAVACH_ZOHO_CLIENT_ID KAVACH_ZOHO_CLIENT_SECRET \
           KAVACH_ZOHO_REFRESH_TOKEN KAVACH_QUICKML_ORG_ID; do
    [ -z "${!v:-}" ] && missing+=("$v")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    echo "ERROR: refusing to deploy — the FORECAST predictor would be UNCONFIGURED." >&2
    echo "       Missing/empty: ${missing[*]}" >&2
    echo "       Fill scripts/catalyst/deploy.env (see deploy.env.example) or export them." >&2
    echo "       To deploy intentionally without the predictor: ALLOW_UNCONFIGURED_QUICKML=1" >&2
    exit 1
  fi
fi

: "${CATALYST_PROJECT_ID:?set CATALYST_PROJECT_ID (see docs/catalyst/appsail-deployment.md)}"
: "${CATALYST_ORG_ID:?set CATALYST_ORG_ID}"

rm -rf "$BUILD"
mkdir -p "$BUILD"

# -- application code (no tests, no venv, no caches) -------------------------
cp -r "$ROOT/backend/kavach" "$BUILD/kavach"
find "$BUILD" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# -- console (single-origin) ---------------------------------------------------
# The built SPA ships with the API so both share one origin. Cross-origin
# hosting is not viable here: AppSail's proxy appends its own
# Access-Control-Allow-Origin on top of the app's, and a duplicated header
# makes browsers refuse every API call. Same origin => no CORS, and the
# console answers at "/" rather than "/app/index.html".
#
# VITE_API_BASE="" makes the client call the API relatively; --base ./ keeps
# asset URLs relative to wherever the app is served from.
if [ "${SKIP_CONSOLE:-0}" != "1" ]; then
  echo "building console for single-origin hosting …"
  ( cd "$ROOT/frontend" && npm ci --silent && VITE_API_BASE="" npx vite build --base ./ )
  mkdir -p "$BUILD/web"
  cp -r "$ROOT/frontend/dist/." "$BUILD/web/"
fi

# -- precomputed MO profiles ---------------------------------------------------
# Zia cannot be reached from the deployed runtime (the SDK needs Catalyst
# platform headers that only accompany authenticated requests), so the
# Zia-derived profiles are produced offline by scripts/mo_precompute.py and
# shipped here. Without this file the app falls back to deterministic
# extraction at startup — correct, just not Zia-attributed.
if [ -f "$ROOT/data/mo_profiles.json" ]; then
  mkdir -p "$BUILD/data"
  cp "$ROOT/data/mo_profiles.json" "$BUILD/data/mo_profiles.json"
  echo "shipping precomputed MO profiles ($(du -h "$ROOT/data/mo_profiles.json" | cut -f1))"
else
  echo "note: no data/mo_profiles.json — MO will use the deterministic extractor" >&2
fi

# -- schema manifest -----------------------------------------------------------
# The ingestion path validates every CSV against this manifest. It lives under
# docs/ in the repo, which is NOT part of the bundle — omitting it made every
# graph and evidence endpoint 500 in production while passing locally.
mkdir -p "$BUILD/docs/schema"
cp "$ROOT/docs/schema/schema-manifest.json" "$BUILD/docs/schema/schema-manifest.json"

# -- synthetic dataset (~1 MB) -------------------------------------------------
# The deployed analytics read the generated CSVs through KAVACH_DATA_DIR (the
# LOCAL adapter). The data is SYNTHETIC by design (ADR-011), so shipping it
# with the bundle is what makes the hosted demo work; the Data Store adapter
# replaces this path once the ingestion load (#15) runs against Catalyst.
if [ -d "$ROOT/data/synthetic" ]; then
  mkdir -p "$BUILD/data"
  cp -r "$ROOT/data/synthetic" "$BUILD/data/synthetic"
else
  echo "data/synthetic missing — generate it first: python scripts/generate_dataset.py" >&2
  exit 1
fi

# -- runtime dependencies from pyproject (single source of truth) ------------
python3 - "$ROOT/backend/pyproject.toml" > "$BUILD/requirements.txt" <<'PY'
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    deps = tomllib.load(f)["project"]["dependencies"]
print("\n".join(deps))
print("zcatalyst-sdk>=0.0.10")  # Data Store SDK, AppSail runtime only
PY

# -- AppSail entrypoint -------------------------------------------------------
# The startup command is NOT shell-expanded by AppSail: a command containing
# $X_ZOHO_CATALYST_LISTEN_PORT reaches uvicorn as a literal string and the
# app 503s with "check the startup command or port". The port is therefore
# read in Python, from the env var AppSail injects.
cat > "$BUILD/appsail_main.py" <<'PY'
"""AppSail entrypoint (CAT-005/#21) — binds uvicorn to the injected port."""

import os

import uvicorn

from kavach.api.main import app

if __name__ == "__main__":
    port = int(os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT", "9000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
PY

# -- AppSail app config -------------------------------------------------------
# build_path, stack and command are all REQUIRED by the CLI's config
# validator (util_modules/config/lib/appsail.js); build_path resolves
# relative to the staged source dir.
cat > "$BUILD/app-config.json" <<JSON
{
  "command": "python3 appsail_main.py",
  "stack": "${APPSAIL_STACK:-python_3_11}",
  "build_path": ".",
  "env_variables": {
    "KAVACH_ENV": "catalyst",
    "KAVACH_DATA_DIR": "data/synthetic",
    "KAVACH_WEB_DIR": "web",
    "KAVACH_SCHEMA_MANIFEST": "docs/schema/schema-manifest.json",
    "KAVACH_MO_PROFILES": "data/mo_profiles.json",
    "KAVACH_DEMO_IDENTITY": "${KAVACH_DEMO_IDENTITY:-demo-state-analyst}",
    "KAVACH_QUICKML_RISK_ENDPOINT": "${KAVACH_QUICKML_RISK_ENDPOINT:-}",
    "KAVACH_QUICKML_RISK_URL": "${KAVACH_QUICKML_RISK_URL:-}",
    "KAVACH_ZOHO_CLIENT_ID": "${KAVACH_ZOHO_CLIENT_ID:-}",
    "KAVACH_ZOHO_CLIENT_SECRET": "${KAVACH_ZOHO_CLIENT_SECRET:-}",
    "KAVACH_ZOHO_REFRESH_TOKEN": "${KAVACH_ZOHO_REFRESH_TOKEN:-}",
    "KAVACH_ZOHO_ACCOUNTS_URL": "${KAVACH_ZOHO_ACCOUNTS_URL:-https://accounts.zoho.in}",
    "KAVACH_QUICKML_ORG_ID": "${KAVACH_QUICKML_ORG_ID:-}",
    "KAVACH_QUICKML_ENVIRONMENT": "${KAVACH_QUICKML_ENVIRONMENT:-Development}",
    "KAVACH_QUICKML_LLM_ENDPOINT": "${KAVACH_QUICKML_LLM_ENDPOINT:-}",
    "KAVACH_QUICKML_LLM_TOKEN": "${KAVACH_QUICKML_LLM_TOKEN:-}",
    "KAVACH_QUICKML_LLM_MODEL_ID": "${KAVACH_QUICKML_LLM_MODEL_ID:-}",
    "KAVACH_QUICKML_LLM_MODEL": "${KAVACH_QUICKML_LLM_MODEL:-GLM-4.7}",
    "KAVACH_CATALYST_PROJECT_ID": "${CATALYST_PROJECT_ID}",
    "KAVACH_DATA_SOURCE": "${KAVACH_DATA_SOURCE:-csv}",
    "KAVACH_DATASTORE_REFRESH_TOKEN": "${KAVACH_DATASTORE_REFRESH_TOKEN:-}",
    "KAVACH_DATASTORE_API_BASE": "${KAVACH_DATASTORE_API_BASE:-https://api.catalyst.zoho.in}",
    "KAVACH_DATASTORE_TTL": "${KAVACH_DATASTORE_TTL:-300}"
  },
  "memory": 512
}
JSON

# -- project descriptor (generated, never committed: carries the project id) --
cat > "$BUILD/catalyst.json" <<JSON
{
  "project_id": "$CATALYST_PROJECT_ID",
  "appsail": [
    {
      "name": "$APP_NAME",
      "source": ".",
      "config": "app-config.json"
    }
  ]
}
JSON

# -- vendor dependencies into the bundle --------------------------------------
# AppSail's Python stack does NOT resolve requirements.txt server-side: the
# runtime only executes the start command, so an un-vendored bundle deploys
# "successfully" and then 503s with "check the startup command or port".
# This mirrors the CLI's own appsail-python template (predeploy: pip install
# -t ./). Wheels must match the AppSail interpreter, so build for the target
# platform rather than this VM's.
echo "vendoring dependencies for ${APPSAIL_STACK:-python_3_11} …"
python3 -m pip install \
  --requirement "$BUILD/requirements.txt" \
  --target "$BUILD" \
  --upgrade \
  --quiet \
  --only-binary=:all: \
  --platform manylinux2014_x86_64 \
  --python-version "${APPSAIL_PY_VERSION:-3.11}" \
  || { echo "dependency vendoring failed" >&2; exit 1; }
find "$BUILD" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo "staged $(du -sh "$BUILD" | cut -f1) at $BUILD"
# `catalyst deploy` exits 0 even when it deploys nothing, so assert on its
# output rather than trusting the exit code (observed on a real failed run).
deploy_log="$BUILD/deploy.log"
( cd "$BUILD" && catalyst deploy --org "$CATALYST_ORG_ID" ) 2>&1 | tee "$deploy_log"
if grep -qiE "No components deployed|deploy skipped|Invalid AppSail" "$deploy_log"; then
  echo "DEPLOY FAILED — see $deploy_log" >&2
  exit 1
fi

echo "deployed. verify:"
echo "  curl https://<appsail-url>/health"
echo "  curl https://<appsail-url>/health/deps       # numpy/sklearn/networkx/pandas versions"
echo "  curl https://<appsail-url>/health/datastore  # sample scoped ZCQL query"
