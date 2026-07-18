#!/usr/bin/env bash
# AppSail backend deployment (CAT-005/#21) — reproducible from clean checkout.
#
# Prerequisites (documented in docs/catalyst/appsail-deployment.md):
#   npm i -g zcatalyst-cli        # Catalyst CLI
#   catalyst login                # authenticate (browser flow)
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
: "${CATALYST_PROJECT_ID:?set CATALYST_PROJECT_ID (see docs/catalyst/appsail-deployment.md)}"
: "${CATALYST_ORG_ID:?set CATALYST_ORG_ID}"

rm -rf "$BUILD"
mkdir -p "$BUILD"

# -- application code (no tests, no venv, no caches) -------------------------
cp -r "$ROOT/backend/kavach" "$BUILD/kavach"
find "$BUILD" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# -- runtime dependencies from pyproject (single source of truth) ------------
python3 - "$ROOT/backend/pyproject.toml" > "$BUILD/requirements.txt" <<'PY'
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    deps = tomllib.load(f)["project"]["dependencies"]
print("\n".join(deps))
print("zcatalyst-sdk>=0.0.10")  # Data Store SDK, AppSail runtime only
PY

# -- AppSail app config -------------------------------------------------------
cat > "$BUILD/app-config.json" <<JSON
{
  "command": "python -m uvicorn kavach.api.main:app --host 0.0.0.0 --port \$X_ZOHO_CATALYST_LISTEN_PORT",
  "stack": "python_3_9",
  "env_variables": {
    "KAVACH_ENV": "catalyst"
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

echo "staged $(du -sh "$BUILD" | cut -f1) at $BUILD"
( cd "$BUILD" && catalyst deploy --org "$CATALYST_ORG_ID" )

echo "deployed. verify:"
echo "  curl https://<appsail-url>/health"
echo "  curl https://<appsail-url>/health/deps       # numpy/sklearn/networkx/pandas versions"
echo "  curl https://<appsail-url>/health/datastore  # sample scoped ZCQL query"
