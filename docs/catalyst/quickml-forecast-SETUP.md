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
**Qwen 2.5** call rewrites the summary into plainer English but can never change a
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

This writes **`data/risk_train.csv`** (it's git-ignored — that's expected).
You should see `wrote NN rows -> data/risk_train.csv`.

---

## Step 2 — Train + publish the QuickML pipeline  ☐

In the Catalyst console:

1. ☐ Go to **QuickML → New pipeline**.
2. ☐ Upload **`data/risk_train.csv`**.
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

## Step 3 — (Optional) Enable Qwen for plain-English summaries  ☐

Skip this and the forecast still works — districts just get a plain templated
sentence instead of a Qwen-written one.

1. ☐ Catalyst console → **QuickML → LLM Serving** → enable **Qwen 2.5-14B-Instruct**
   (available in the **IN** data center).
2. ☐ Copy the **serving endpoint URL**.
3. ☐ Generate an **OAuth token** with the LLM-serving scope.

---

## Step 4 — Set the env vars and deploy  ☐

Never commit these values (ADR-001) — they are environment-only. Export them,
then run the existing deploy script (it already wires them into `app-config.json`):

```bash
export KAVACH_QUICKML_RISK_ENDPOINT="<endpoint key from Step 2>"

# only if you did Step 3:
export KAVACH_QUICKML_LLM_ENDPOINT="<qwen serving url>"
export KAVACH_QUICKML_LLM_TOKEN="<oauth token>"
# KAVACH_QUICKML_LLM_MODEL defaults to qwen-2.5-14b-instruct — leave unset

bash scripts/catalyst/deploy_backend.sh
```

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
