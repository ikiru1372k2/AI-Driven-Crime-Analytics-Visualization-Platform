#!/usr/bin/env bash
# Gateway integration matrix (CAT-004/#20 test plan): auth/no-auth per
# route group, through the gateway origin.
#
#   GATEWAY_URL=https://<project>.development.catalystserverless.in \
#   scripts/catalyst/verify_gateway.sh
#
# Exit non-zero if any expectation fails, so it can gate a deploy.
set -uo pipefail

GATEWAY_URL="${GATEWAY_URL:?set GATEWAY_URL to the Catalyst project domain}"
AUTH_HEADER="${AUTH_HEADER:-}"   # e.g. "Authorization: Bearer <token>"

fail=0
check() { # name, expected_code, path, [extra curl args…]
  local name="$1" expect="$2" path="$3"; shift 3
  local code
  code=$(curl -s -m 60 -o /tmp/kavach_gw.out -w '%{http_code}' "$@" "$GATEWAY_URL$path" || echo 000)
  if [ "$code" = "$expect" ]; then
    printf '  ok    %-34s %s\n' "$name" "$code"
  else
    printf '  FAIL  %-34s got %s want %s\n' "$name" "$code" "$expect"
    fail=1
  fi
}

echo "gateway: $GATEWAY_URL"

echo "public routes (no auth required):"
check "health"          200 /health
check "health/deps"     200 /health/deps

echo "protected routes without credentials (must be rejected):"
check "graph subgraph"  401 "/api/v1/graph/subgraph?seed_type=CASE&seed_id=5001"
check "audit"           401 /api/v1/audit
check "decisions POST"  401 /api/v1/decisions -X POST -H 'Content-Type: application/json' \
      -d '{"kind":"ALERT_ACK","target_ref":"x","decision":"ACKNOWLEDGED"}'

if [ -n "$AUTH_HEADER" ]; then
  echo "protected routes with credentials:"
  check "graph subgraph (auth)" 200 \
    "/api/v1/graph/subgraph?seed_type=CASE&seed_id=5001" -H "$AUTH_HEADER"
else
  echo "protected routes with credentials: SKIPPED (set AUTH_HEADER)"
fi

echo "analytics through the gateway:"
check "api/meta"        200 /api/meta

[ "$fail" -eq 0 ] && echo "gateway matrix passed" || echo "gateway matrix FAILED" >&2
exit "$fail"
