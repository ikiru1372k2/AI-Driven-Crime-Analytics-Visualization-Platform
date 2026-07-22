# KAVACH — Expectations vs. What We Built (Gap Plan)

_Source: KSP Datathon 2026 "Introduction & Problem Statements Explainer" session transcript + `challenge-1.txt` (Challenge 2 brief), read against the current codebase._

## Scope: Challenge 2 only (Visualization)

The datathon has **two** challenges:

- **Challenge 1 — Intelligent Conversational AI** (agentic AI / NLP to query the crime database, voice, multilingual). **Not ours.**
- **Challenge 2 — AI-Driven Crime Analytics & Visualization Platform.** ← **This is us.**

Teams can only pitch one challenge, and the judges explicitly advised: *pick one and solve all its key aspects well* rather than spreading across both. So this plan stays strictly inside Challenge 2. Anything conversational / chatbot / natural-language-DB-query is **out of scope** — that would drift into Challenge 1 and dilute the pitch. Where the DGP said "we'd like to see agentic AI," that was a general remark aimed mainly at Challenge 1; for us it is not a goal.

---

## 1. What the judges want from a *visualization* solution

Distilled from the explainer session (DGP Dr. Pranam Mati, Rajiv Dash Sharma, Arjit Chowdhury, SCRB), filtered to what applies to Challenge 2:

| # | Expectation (their words) | Weight |
|---|---|---|
| E1 | **Proactive, not reactive** — "prediction of crime is very important"; forecast high-risk areas; emerging-trend analysis | Very high |
| E2 | **Dynamic, drill-down, digital** — replace the static "Crime in Karnataka" handbook with dynamic, analyzed, drill-down content (DGP's own framing of Challenge 2) | Very high |
| E3 | **Real-time snapshot for senior officers** — big-TV dashboards, "immediate sense of what is going on", reduce response time, *high-quality* visuals | High |
| E4 | **Network & link analysis** — "crime does not happen individually, it happens through a network"; cross-jurisdiction, repeat offenders, MO across cases | High |
| E5 | **Production-grade quality** — "model flat" analogy: miniature but production-close; "not throwaway code"; evaluated by senior architects | High (non-negotiable) |
| E6 | **Scale + security** — sustain "at least a decade"; 1–2 lakh cases; 100+ users; ~1,100 stations; capacity planning | High |
| E7 | **Explainability + statistics / advanced algorithms** — "what kind of statistics and advanced algorithms… cutting-edge research you bring" | Medium-high |
| E8 | **Deploy on Catalyst (Zoho)** — mandatory gate; reference arch from Zoho | Mandatory gate |
| E9 | **Synthetic data** — only schema/master tables provided; generate your own; DPDP not a blocker | Constraint (satisfied) |

---

## 2. What we have built (mapped to the Challenge-2 requirements)

Legend: ✅ shipped & wired to real APIs · 🟡 partial / roadmap-stubbed · ⛔ not started.

| Req | Capability | State | Evidence in code |
|---|---|---|---|
| C2-R1 | Interactive dashboards replacing static sheets | ✅ | `frontend/src/app/Overview.tsx`, `App.tsx`, `CommandNav.tsx` (DETECT→UNDERSTAND→CONNECT→FLAG→FORECAST→EXPLAIN) |
| C2-R2 | District-level drill-down (state→district→station) | ✅ | `MapView.tsx`, `/api/districts`, choropleth + velocity |
| C2-R3 | Spatiotemporal hotspots (time-of-day × location) | ✅ | DBSCAN haversine `analytics/hotspot/engine.py`, `/api/hotspots`, hour histogram + time scrubber |
| C2-R4 | Emerging trend alerts vs historical baseline | ✅ (visual polish 🟡) | robust weekly baseline + modified z-score `analytics/trends/engine.py`, `/api/trends`; "red-zone pulsing" visual not yet done |
| C2-R5 | Relationship / network & link analysis | ✅ | Cytoscape `GraphView.tsx` + NetworkX (`graph/metrics.py`: degree/betweenness centrality, Louvain communities, Jaccard); `/api/associations`, `/api/v1/graph` |
| C2-R6 | Repeat-offender tracking across jurisdictions | ✅ | entity resolution `analytics/entity/engine.py` (blocking + fuzzy name + age proximity, single-link), human-in-loop `IdentityReview.tsx`, `/api/identities` |
| C2-R7 | Modus Operandi across incidents | ✅ | `analytics/mo/` lexicon + **Catalyst Zia** (NER/keywords), span-anchored, UNKNOWN-preferring; `MoView.tsx`, `/api/v1/mo` |
| C2-R8 | Socio-economic correlation overlays | ⛔ | documented as `EXTERNAL_DATA_REQUIRED`; no engine |
| C2-R9 | Predictive risk scoring / forecast | ⛔ | `analytics/risk/__init__.py` **empty stub**; UI shows "soon" |
| C2-R10 | Anomaly detection with call-outs | ⛔ | `analytics/anomaly/__init__.py` **empty stub**; UI shows "soon" |
| C2-R11 | Evidence & explainability on every insight | ✅ | provenance envelope on every response; `provenance/`, `evidence_routes.py`, `EvidenceView.tsx`; six-class classification legend |
| C2-R12 | Event-driven automation (Signals/Circuits) | 🟡 | designed; `functions/` is **README only** — no functions implemented |

**Coverage: 8 of 12 shipped, 1 partial, 3 not started.** We are already a strong visualization + analytics platform. Foundations worth leading with in the pitch:

- **Provenance-first** — every number carries method, version, window, and source FIR IDs (E7).
- **Auth/roles/scope** — server-side scope resolution (STATE/DISTRICT/UNIT), fails closed, append-only `SYSTEM_ADMIN`-gated audit trail (E6 security).
- **Deterministic synthetic generator** with a `ground_truth.json` key the engines never read — validation is honest (E7, E9).
- **Real analytics, nothing hard-coded** — DBSCAN, modified z-score, NetworkX centrality/Louvain, fuzzy record linkage.

---

## 3. The gaps that matter (ranked by judge weight)

### Gap A — No predictive / proactive forecast (E1). **Biggest scoring risk.**
`analytics/risk/` is an empty stub. "Proactive not reactive" and "prediction of crime is very important" were the most-repeated points in the session. We visualize the past (hotspots, trends) but forecast nothing. For a *visualization* solution this is the headline missing view — the FORECAST tab is already in the nav but shows "soon".

### Gap B — No anomaly detection (C2-R10; feeds E1/E7).
`analytics/anomaly/` is empty. Cheap to build on the trend/MO/graph signals we already compute, and it produces exactly the "visual call-out" the brief names — high visual payoff for a jury demo.

### Gap C — Not demonstrably real-time / live (E3).
Dashboards are request/response snapshots. No live-update path (the `functions/` Signals→Circuits pipeline is unbuilt). The "big-TV, immediate sense of what's happening, reduce response time" story has no moving picture yet.

### Gap D — Scale not demonstrated (E6).
Generator produces ~2,236 cases; judges named **1–2 lakh**. No evidence the map/graph/queries hold at ~100× data or with 100 concurrent users. They explicitly asked about capacity planning.

### Gap E — Not confirmed deployed on Catalyst (E8, mandatory gate).
Deploy scripts exist (`scripts/catalyst/`) but there's no verified live AppSail URL. This is a submission gate, not optional.

### Gap F — Visual polish for the "wow" snapshot (E2/E3).
"Red-zone pulsing" trend markers (C2-R4) and the socio-economic overlay (C2-R8) are named in the brief and photograph well for a jury. These are the visuals that sell a *visualization* pitch.

---

## 4. Plan to close the gaps

Ordered by scoring leverage; each phase is independently demo-able.

### Phase 1 — Proactive intelligence: forecast + anomaly (closes Gap A & B; serves E1)
This is where a visualization solution wins or loses, because "predictive/proactive" was the judges' loudest theme.

- **Area risk / forecast** (`analytics/risk/`): area-level risk score (not individual — respects ADR-005) from features we already compute: velocity, cluster density, MO recurrence, trend z-scores. Temporal holdout validation; **explainable driver contributions**. Endpoint `/api/risk`; wire the FORECAST view with a risk choropleth + driver breakdown.
- **Anomaly detection** (`analytics/anomaly/`): per-factor deviation of a case vs its peer baseline, with mandatory per-factor explanation. Endpoint `/api/anomalies`; wire the FLAG view with visual call-outs on the map/list.

### Phase 2 — Real-time + visual polish (closes Gap C & F; serves E2/E3)
- **Live path**: implement `functions/` thin steps — **Signals** (new-FIR insert) → **Event Function** (recompute affected hotspot/trend) → **Circuit** → **Push** alert; documented cron fallback if Circuits unavailable. Demo: "new FIR arrives → dashboard updates → alert pulses" (transcript D9).
- **Red-zone pulsing** trend markers (C2-R4) and any other high-impact visual touches for the big-TV snapshot.
- **Socio-economic overlay** (C2-R8): ship as a **real** overlay if public Karnataka district indicators are available; otherwise keep it an honest, documented integration point (don't fake it).

### Phase 3 — Scale evidence + Catalyst deployment (closes Gap D & E; mandatory E8)
- Regenerate synthetic data at **1–2 lakh cases**; capture query/render timings; add pagination/tiling where the map or graph strains. Write a one-page **capacity/scalability note** (answers E6 directly).
- Run `scripts/catalyst/deploy_backend.sh` + `deploy_frontend.sh`, provision Data Store, verify a **live AppSail URL**. Claim Catalyst credits (code `KSPH26`).

_Phase 3's deployment is a hard submission gate and must land before the 26 July deadline regardless of the others._

---

## 5. What to say in the pitch (positioning)

- Lead with the **visual story + provenance**: state overview → drill into a pulsing hotspot → see the recurring MO → open the association network → identity match → **forecast** of where it's heading — and every screen cites its source FIRs. This is dynamic, drill-down, explainable visualization — exactly the anti-thesis of the static handbook the DGP wants to replace (E1, E2, E7).
- Frame it as **one coherent intelligence console**, not a pile of features — reads as production-shaped (E5), not "a model and a screen" (their explicit anti-pattern).
- Show the **synthetic-but-honest** validation story: deterministic generator + ground-truth key the engines can't see (E7, E9).
- Have the **scale note + live Catalyst URL** ready — the two questions a senior architect will ask (E6, E8).

---

## 6. Effort snapshot

| Phase | Closes | Rough effort | Demo-ready alone? |
|---|---|---|---|
| 1 Forecast + anomaly | Gap A, B (E1) | Medium | Yes |
| 2 Real-time + visual polish | Gap C, F (E2, E3) | Medium | Yes |
| 3 Scale + Catalyst deploy | Gap D, E (E6, E8) | Medium-high | Yes |

Phase 1 moves the score the most (proactive/predictive was the judges' loudest ask). Phase 3's Catalyst deployment is the hard gate before 26 July.

> Note: `README.md` and `CONTEXT_HANDOFF.md` are stale (handoff stops at "Phase 4"); the code is well ahead of both. Refresh them before submission.
