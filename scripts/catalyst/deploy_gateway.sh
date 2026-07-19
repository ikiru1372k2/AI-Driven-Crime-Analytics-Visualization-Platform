#!/usr/bin/env bash
# API Gateway rule deployment (CAT-004/#20).
#
# Prerequisites:
#   npm i -g zcatalyst-cli && catalyst login   (or CATALYST_TOKEN in CI)
#   export CATALYST_PROJECT_ID=… CATALYST_ORG_ID=…
#
# Rules live in catalyst/catalyst-user-rules.json (committed, reviewable).
# This script stages them into a Catalyst app directory and deploys.
#
# IMPORTANT — verified limitation, see docs/catalyst/api-gateway.md:
# `catalyst deploy --only apig` prints "DEPLOYMENT SUCCESSFUL" even when the
# server stores none of the rules. This script therefore VERIFIES the result
# by reading the rules back, and fails if they are absent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="$ROOT/.catalyst-build/apig"
RULES="$ROOT/catalyst/catalyst-user-rules.json"

command -v catalyst >/dev/null || { echo "zcatalyst-cli not installed"; exit 1; }
command -v node >/dev/null || { echo "node not installed"; exit 1; }
: "${CATALYST_PROJECT_ID:?set CATALYST_PROJECT_ID}"
: "${CATALYST_ORG_ID:?set CATALYST_ORG_ID}"
[ -f "$RULES" ] || { echo "missing $RULES"; exit 1; }

rm -rf "$BUILD"; mkdir -p "$BUILD"
# project_id MUST be a string: these ids exceed JavaScript's safe-integer
# range, and an unquoted value is silently truncated by the CLI.
cat > "$BUILD/catalyst.json" <<JSON
{
  "project_id": "$CATALYST_PROJECT_ID",
  "apig": {
    "enabled": true,
    "rules": "catalyst-user-rules.json"
  }
}
JSON
cp "$RULES" "$BUILD/catalyst-user-rules.json"

echo "enabling API Gateway (idempotent) …"
( cd "$BUILD" && catalyst apig:enable 2>&1 | grep -viE "deprecat" ) || true

echo "deploying $(python3 -c "import json,sys;print(len(json.load(open('$RULES'))))") rules …"
( cd "$BUILD" && catalyst deploy --only apig --org "$CATALYST_ORG_ID" 2>&1 | grep -viE "deprecat" ) || true

# -- verify: the CLI's success message is not evidence -----------------------
echo "verifying rules landed on the server …"
stored=$(cd "$BUILD" && node "$ROOT/scripts/catalyst/catalyst_api.js" GET \
  "/baas/v1/project/$CATALYST_PROJECT_ID/api-gateway/api?start=1&num_of_apis=50&enhance=true" \
  2>/dev/null | tail -1)

missing=$(python3 - "$RULES" <<PY
import json, sys
wanted = {r["name"] for r in json.load(open(sys.argv[1]))}
stored = json.loads('''$stored''').get("body", {}).get("data") or []
have = {r.get("name") for r in stored}
print(",".join(sorted(wanted - have)))
PY
)

if [ -n "$missing" ]; then
  echo "GATEWAY RULES NOT APPLIED: $missing" >&2
  echo "The CLI reported success but the server did not store them." >&2
  echo "See docs/catalyst/api-gateway.md — rules may need to be added in the" >&2
  echo "Catalyst console (Serverless > API Gateway) for this CLI/plan." >&2
  exit 1
fi
echo "all rules present on the server"
