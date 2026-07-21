# Authentication, Roles & Scope (CAT-003/#19)

Identity comes from **Catalyst Authentication**. Authorization — what a
signed-in user may actually see — is resolved **server-side** from a stored
role assignment. A request can never widen its own scope.

## Roles

| Role | Typical scope | Notes |
|---|---|---|
| `SCRB_STATE_ANALYST` | STATE | statewide intelligence |
| `SUPERVISOR` | DISTRICT | district oversight |
| `DISTRICT_ANALYST` | DISTRICT | confined to one district |
| `INVESTIGATOR` | UNIT | confined to one police station |
| `SYSTEM_ADMIN` | STATE | the only role that may read the audit trail |

## Scope resolution

`AuthContext` exposes `district_scope` / `unit_scope`, derived from the
assignment — not from any request field:

- **STATE** scope (and `SYSTEM_ADMIN` / `SCRB_STATE_ANALYST` regardless of
  assignment target) → unrestricted.
- **DISTRICT** scope → graph results are filtered to cases of that district;
  cross-district edges appear only as stub *counts*, and node detail for a
  record with no in-scope case returns **403**.
- **UNIT** scope → narrower than district; it does **not** silently grant
  the whole district.

### Multiple assignments

A user may hold several. The effective one is chosen by a **documented
priority list** (`ROLE_PRIORITY` in `auth/models.py`), not an implicit
"highest privilege wins": `SYSTEM_ADMIN → SCRB_STATE_ANALYST → SUPERVISOR
→ DISTRICT_ANALYST → INVESTIGATOR`. Ties break to the broadest scope, then
the lowest scope id, so resolution is deterministic.

## Enforcement

| Condition | Response |
|---|---|
| no / invalid / expired token | **401** |
| authenticated, no role assignment | **403** (no implicit default role) |
| role lacks the specific permission (e.g. audit read) | **403** |

Decisions and audit events are attributed to the **session** identity, so
`X-KAVACH-ACTOR` / `X-KAVACH-ROLE` headers no longer influence anything —
a test asserts a spoofed header cannot escalate.

## Local development

There is no Catalyst session on a dev machine, so a header-driven validator
is available — but it is **fail-closed**: it requires *both* a non-Catalyst
runtime *and* an explicit opt-in.

```bash
KAVACH_DEV_AUTH=1 uvicorn kavach.api.main:app --port 8001
curl -H "x-kavach-dev-user: demo-district-analyst" http://127.0.0.1:8001/api/v1/graph/...
```

Without `KAVACH_DEV_AUTH=1` the Catalyst validator is used and local
requests are denied. On AppSail the dev validator can never be selected,
even if the variable is set.

## Demo users

Seeded by `python scripts/seed_demo_roles.py` (idempotent). These are
**role assignments, not credentials** — no passwords or tokens are stored
in the repo.

| User id | Role | Scope |
|---|---|---|
| `demo-state-analyst` | SCRB_STATE_ANALYST | STATE |
| `demo-district-analyst` | DISTRICT_ANALYST | DISTRICT 44 (Bengaluru City) |
| `demo-supervisor` | SUPERVISOR | DISTRICT 44 |
| `demo-investigator` | INVESTIGATOR | UNIT 4430 (Peenya PS) |
| `demo-admin` | SYSTEM_ADMIN | STATE |

For the hosted demo, replace the `user_id` values with the Catalyst user
ids of the real seeded accounts (Catalyst console → Authentication → Users),
then re-run the seeding script.

## Deployed demo mode (explicit, documented, not a security control)

The console has no sign-in screen yet (#60), so on the deployed demo the
backend is started with:

```
KAVACH_DEMO_IDENTITY=demo-state-analyst
```

With it set, a request carrying **no** Catalyst session is treated as that
one named analyst. A real Catalyst session always takes precedence.

Why this is acceptable here, and where the line is:

- the deployed data is SYNTHETIC (ADR-011) — there are no real FIRs to leak;
- the identity granted is an ordinary analyst, **not** `SYSTEM_ADMIN`, so the
  strongest control still holds: `/api/v1/audit` returns **403** on the live
  deployment. Authorization is genuinely enforced, not stubbed out;
- decisions remain attributable — the audit trail records
  `demo-state-analyst (SCRB_STATE_ANALYST)`, not an anonymous actor;
- it is off unless the variable is set, and a startup warning is logged.

**Never set this variable on a deployment holding real FIR data.** It exists
so the demo can open a node detail panel and record a review decision; it
disappears the moment the login flow (#60) lands.

## Status

Middleware, role model, scope enforcement, deny-by-default and the demo
assignments are implemented and covered by 26 tests (including a mocked
validator, forged/expired tokens, header-escalation attempts and
cross-district isolation).

**Not yet done:** the hosted login screen. The Catalyst-hosted login flow
and the frontend's sign-in UI land with #60 / #20 — until then the deployed
API authenticates but the console has no login page, so protected routes
are exercised via the API. This is the honest remaining gap on this issue's
"login via Catalyst Auth works in the deployed dev environment" criterion.
