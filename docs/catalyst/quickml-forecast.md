# Area Risk Forecast — QuickML + Qwen setup (FORECAST tab)

The FORECAST → Area Risk screen predicts the next 30 days of cases per district.
The number is produced by a **Zoho QuickML** model called live from the AppSail
runtime — we do not model locally. An optional **Qwen 2.5** call (QuickML LLM
Serving) rephrases the computed facts into plainer English; it can never change a
number (the engine rejects any LLM sentence that introduces a number the facts
did not contain).

Until the two endpoints below are published and their env vars are set, the tab
honestly shows **"Forecast unavailable — prediction service not configured"** and
displays **no numbers**. This is the intended local/CI state (ADR-006).

## What the code does (already built)

- `backend/kavach/analytics/risk/features.py` — the single feature contract used
  by BOTH training export and live serving (guarantees train/serve parity).
- `backend/kavach/analytics/risk/engine.py` — builds per-district feature rows,
  calls `app.quick_ml().predict(...)`, derives risk level / trend / drivers, and
  optionally polishes the summary with Qwen.
- `GET /api/risk` — returns the per-district forecast with an `AI_DERIVED`
  provenance envelope.
- `scripts/risk_train_export.py` — writes the training CSV from the same feature
  builder.

## Console steps (team — needs a Catalyst login)

### 1. Train + publish the QuickML prediction pipeline

1. Generate the training table locally (repo root):

   ```bash
   PYTHONPATH=backend backend/.venv/Scripts/python.exe scripts/risk_train_export.py
   # -> data/risk_train.csv
   ```

2. Catalyst console → **QuickML** → **New pipeline** → upload `data/risk_train.csv`.
3. Target column: **`target_next_count`**. Feature columns (leave `district_id` /
   `district_name` OUT — they are identifiers, not features):

   ```
   recent_count, prior_count, prior2_count, velocity, rolling_mean_3, trend_slope, month
   ```

4. Train a **regression** model, evaluate, then **publish an endpoint**.
5. Copy the endpoint key → set `KAVACH_QUICKML_RISK_ENDPOINT`.

### 2. Enable QuickML LLM Serving (Qwen 2.5) — optional but recommended

1. Catalyst console → **QuickML → LLM Serving** → enable **Qwen 2.5-14B-Instruct**
   (available in the IN data center).
2. Copy the serving endpoint URL → `KAVACH_QUICKML_LLM_ENDPOINT`.
3. Generate an OAuth token with the LLM-serving scope → `KAVACH_QUICKML_LLM_TOKEN`.
   (If the token is omitted, forecasts still work — every district just keeps the
   deterministic template sentence instead of the Qwen rephrase.)

### 3. Set the AppSail env vars

`scripts/catalyst/deploy_backend.sh` already threads these into the generated
`app-config.json`; export them before deploying (never commit them — ADR-001):

```bash
export KAVACH_QUICKML_RISK_ENDPOINT="<pipeline endpoint key>"
export KAVACH_QUICKML_LLM_ENDPOINT="<qwen serving url>"      # optional
export KAVACH_QUICKML_LLM_TOKEN="<oauth token>"             # optional
# KAVACH_QUICKML_LLM_MODEL defaults to qwen-2.5-14b-instruct
bash scripts/catalyst/deploy_backend.sh
```

## Verify after deploy

```bash
curl "https://<appsail-url>/api/risk?window_days=30"
```

- `available: true` with per-district forecasts → live path working.
- `available: false` with `reason` → endpoint not set or unreachable (the tab shows
  the honest unavailable panel, no fabricated numbers).

All data is SYNTHETIC (ADR-011); the forecast is indicative, not deterministic.
