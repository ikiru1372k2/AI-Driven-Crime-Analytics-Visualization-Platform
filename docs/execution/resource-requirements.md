# Resource Requirements Index

Consolidated external resources required to complete resource-blocked issues.
Everything listed here blocks ONLY live validation/provisioning — all
resource-independent implementation proceeds regardless (autonomous execution
policy). Never place secret values in this file or in GitHub issues.

---

## RES-CATALYST-PROJECT-001

**Resource:** Authenticated Zoho Catalyst project (owner login + promotion credits).

**Required by:** #16 (CAT-001), #17 (CAT-002), #18 (CAT-003 live auth), #19 (CAT-004), #20 (CAT-005), #21 (CAT-006), #40 (MO-002 live QuickML), #74–#77 (EVT-*), #82, #84.

**Exact requirement:**
1. Zoho account login for `catalyst login` (interactive browser flow — cannot be performed autonomously).
2. Credits claim at https://catalyst.zoho.com/promotions.html?cn=KSPH26.
3. Created Catalyst project (or permission for the CLI to create one).

**Configuration names (values via local env only):**
- `CATALYST_PROJECT_ID`
- `CATALYST_ENV_ID`
- (later, if QuickML serving requires it) `QUICKML_MODEL_ID`

**Secret required:** YES (Zoho session/OAuth — held by CLI, never committed).

**Why needed:** CAT-001's acceptance criteria (authenticated `catalyst project:list`, capability verification report with live probes) cannot be validated without an authenticated project. Everything in M2 and all live Catalyst integrations depend on it.

**Implementation already completed:** repository structure targets AppSail/Functions/Web Client (ADR-010); Data Store schema manifest + provisioning design specified (#17); repository abstraction keeps all engines Catalyst-portable (dev fixture in `backend/kavach/repositories/dev_fixture.py`).

**Validation pending:** `catalyst --version && catalyst project:list`; per-service capability probes (Data Store, NoSQL, AppSail Python runtime, QuickML surface, Signals, Circuits, Cron, SmartBrowz, Push, Auth, API Gateway) recorded into `docs/catalyst/capability-report.md`.

**Priority:** P0 · **Blocks demo:** YES (deployed URL).

---

## RES-DATA-SOCIOECONOMIC-001

**Resource:** Approved public area-level socio-economic dataset (population density, urbanization, education, employment indicators for Karnataka districts).

**Required by:** #55 (RISK-001 optional feature), challenge requirement C2-R8.

**Exact requirement:** A citable public dataset (e.g., Census-derived district indicators) approved for use; without it C2-R8 ships as a documented integration point — it will NOT be fabricated (ADR-009).

**Secret required:** NO. **Priority:** P2 · **Blocks demo:** NO.
