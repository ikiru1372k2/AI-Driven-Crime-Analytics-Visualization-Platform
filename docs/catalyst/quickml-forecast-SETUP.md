# FORECAST tab — QuickML setup checklist (teammate task)

**Who this is for:** whoever has the Zoho Catalyst console login.
**Time:** ~20–30 min.
**Goal:** turn the FORECAST → Area Risk screen from *"unavailable"* into a live,
per-district crime forecast.

> **You do NOT need to touch any code.** All the code is merged. This is a
> one-time console + env-var setup. Follow the boxes top to bottom.

---

## Background (30-second read)

The forecast number is produced by a **Zoho QuickML** regression model, called
live from our backend on every page load — we deliberately do NOT model locally
(a hand-rolled model on synthetic data wouldn't be trustworthy). An optional
**GLM 4.7** call rewrites the summary into plainer English but can never change a
number.

Right now the tab shows **"Forecast unavailable — prediction service not
configured"** with no numbers. That is correct and honest — it stays that way
until you finish the steps below. Nothing is broken.

---

## Step 1 — Generate the training file  ☐

From the repo root:

```bash
PYTHONPATH=backend backend/.venv/Scripts/python.exe scripts/risk_train_export.py
```

This writes **`data/risk_train_model.csv`** (it's git-ignored — that's expected).
You should see `wrote NN rows -> data/risk_train_model.csv`.

---

## Step 2 — Train + publish the QuickML pipeline  ☐

In the Catalyst console:

1. ☐ Go to **QuickML → New pipeline**.
2. ☐ Upload **`data/risk_train_model.csv`**.
3. ☐ Set the **target column** to:  `target_next_count`
4. ☐ Set the **feature columns** to exactly these seven (do **not** include
   `district_id` or `district_name` — they are labels, not features):

   ```
   recent_count, prior_count, prior2_count, velocity, rolling_mean_3, trend_slope, month
   ```

5. ☐ Choose a **regression** model, train it, glance at the eval metrics.
6. ☐ **Publish** an endpoint.
7. ☐ **Copy the endpoint key** — you'll paste it in Step 4.

> ⚠️ The feature columns above must match EXACTLY. They come from the same code
> (`backend/kavach/analytics/risk/features.py`) that builds the live request, so
> any mismatch will make predictions fail. Don't rename or reorder.

---

## Step 3 — (Optional) Enable GLM for plain-English summaries  ☐

Skip this and the forecast still works — districts just get a plain templated
sentence instead of a GLM-written one.

1. ☐ Catalyst console → **QuickML → LLM Serving** → enable **GLM 4.7**
   (available in the **IN** data center).
2. ☐ Copy the **serving endpoint URL** (ends in `/glm/chat`) and its **model id**
   (e.g. `crm-di-glm47b_30b_it`).

> The summaries reuse the **same** self-client OAuth token as the predictor
> (scope `QuickML.deployment.READ`) — no separate token is needed.

---

## Step 4 — Fill deploy.env and deploy  ☐

The live predictor is called over a **self-client OAuth REST** path (works from the
anonymous AppSail runtime), so it needs the Zoho self-client trio, not just an
endpoint key. Put all values in a **git-ignored** `deploy.env` — never commit them
(ADR-001). The deploy script auto-sources it and **refuses to deploy if any
predictor secret is empty**, so a deploy can no longer silently wipe the live
credentials.

```bash
cp scripts/catalyst/deploy.env.example scripts/catalyst/deploy.env
# edit scripts/catalyst/deploy.env and fill in:
#   KAVACH_QUICKML_RISK_ENDPOINT   endpoint key (from Step 2)
#   KAVACH_QUICKML_RISK_URL        full predict URL: …/endpoints/<id>/predict
#   KAVACH_ZOHO_CLIENT_ID          self-client id
#   KAVACH_ZOHO_CLIENT_SECRET      self-client secret
#   KAVACH_ZOHO_REFRESH_TOKEN      refresh token (scope QuickML.deployment.READ)
#   KAVACH_QUICKML_ORG_ID          e.g. 60078928452
#   # optional (Step 3): KAVACH_QUICKML_LLM_ENDPOINT / KAVACH_QUICKML_LLM_MODEL_ID

bash scripts/catalyst/deploy_backend.sh
```

> To deploy intentionally **without** the predictor (a plain demo build), set
> `ALLOW_UNCONFIGURED_QUICKML=1` — the tab then shows the honest "unavailable" panel.

---

## Step 5 — Verify it's live  ☐

```bash
curl "https://<appsail-url>/api/risk?window_days=30"
```

- ☐ **`"available": true`** with a list of districts → **done, it's live.** Open
  the FORECAST tab and you'll see per-district risk cards.
- **`"available": false`** with a `reason` → the endpoint key is wrong/unset or
  unreachable. The tab safely shows the "unavailable" panel (no fake numbers).
  Re-check Steps 2 and 4.

---

## Notes

- **Refreshing the model later:** re-run Step 1 to regenerate the CSV, re-upload
  and retrain in the console. There's no auto-retrain.
- All data is SYNTHETIC (ADR-011). The forecast is indicative, not deterministic —
  the UI states this on every card.
- Deeper reference (what the code does, envelope/provenance): see
  [quickml-forecast.md](quickml-forecast.md).
