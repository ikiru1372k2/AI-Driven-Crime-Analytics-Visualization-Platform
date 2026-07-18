#!/usr/bin/env bash
# Web Client Hosting deployment for the React SPA (CAT-006/#22).
#
# Prerequisites (documented in docs/catalyst/web-client-hosting.md):
#   npm i -g zcatalyst-cli && catalyst login
#   export CATALYST_PROJECT_ID=… CATALYST_ORG_ID=…       # never committed
#   export VITE_API_BASE=https://<gateway-base>          # API Gateway URL
#
# Builds the SPA with the gateway API base baked in, stages it with a
# client-package.json + 404.html SPA fallback, and deploys.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="$ROOT/.catalyst-build/client"
CLIENT_NAME="${CATALYST_CLIENT_NAME:-kavach-console}"

command -v catalyst >/dev/null || { echo "zcatalyst-cli not installed (npm i -g zcatalyst-cli)"; exit 1; }
: "${CATALYST_PROJECT_ID:?set CATALYST_PROJECT_ID (see docs/catalyst/web-client-hosting.md)}"
: "${CATALYST_ORG_ID:?set CATALYST_ORG_ID}"
: "${VITE_API_BASE:?set VITE_API_BASE to the Catalyst API Gateway base URL}"

# -- build with the gateway base URL baked in ---------------------------------
( cd "$ROOT/frontend" && npm ci && VITE_API_BASE="$VITE_API_BASE" npm run build )

rm -rf "$BUILD"
mkdir -p "$BUILD"
cp -r "$ROOT/frontend/dist/." "$BUILD/"

# SPA fallback: unknown deep links serve the app shell (hash state restores
# the view; path-style routes resolve client-side).
cp "$BUILD/index.html" "$BUILD/404.html"

cat > "$BUILD/client-package.json" <<JSON
{
  "name": "$CLIENT_NAME",
  "version": "0.1.0",
  "homepage": "index.html",
  "login_redirect": "index.html"
}
JSON

cat > "$ROOT/.catalyst-build/catalyst.json" <<JSON
{
  "project_id": "$CATALYST_PROJECT_ID",
  "client": {
    "source": "client"
  }
}
JSON

echo "staged $(du -sh "$BUILD" | cut -f1) at $BUILD"
( cd "$ROOT/.catalyst-build" && catalyst deploy --org "$CATALYST_ORG_ID" )

echo "deployed. verify from the hosted URL:"
echo "  - major routes + deep link (e.g. /#view=map&district=44) load"
echo "  - API calls hit $VITE_API_BASE (check CORS / gateway)"
echo "  - login flow end-to-end (Catalyst Authentication, CAT-003/#19)"
