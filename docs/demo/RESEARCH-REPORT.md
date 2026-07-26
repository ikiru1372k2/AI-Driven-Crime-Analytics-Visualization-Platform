# KAVACH AI — Application Research Report (Phase 1)

*Method: full hands-on investigation of the live deployment (every tab, filter, dialog, expansion, player, and cross-link), cross-checked against the codebase. Nothing below is assumed — every item was seen working.*

---

## 1 · Complete Feature Inventory

### Global shell (all screens)
| Feature | Detail | Rating |
|---|---|---|
| Synthetic-data banner | "SYNTHETIC DEMO DATA — NOT REAL FIRS" + live dataset span (16,652 cases · 2023-07-02 → 2026-07-01) permanently visible | ⭐⭐⭐⭐ ethics on-screen at all times |
| Command navigation | 7 modules with **live count badges** (Trends ①, Anomalies ㉕) that come from real API data | ⭐⭐⭐ |
| Theme toggle (☾) | Full dark/light theme | ⭐⭐ |
| URL state everywhere | View, filters, selected hotspot, graph seed all live in the hash — any screen is shareable/reloadable | ⭐⭐⭐⭐ workflow innovation |
| Query cache + warmers | Revisited tabs paint instantly; heavy computations pre-warmed off the request path | ⭐⭐⭐ (invisible but felt) |

### Trends (State Intelligence Overview)
| Feature | Detail | Rating |
|---|---|---|
| KPI strip | Total cases, critical/serious/watch alerts, active hotspots | ⭐⭐⭐ |
| **Emerging trends ranked by deviation** | Alert card: `CRITICAL · Robbery rising at Peenya PS · 30 cases · baseline 4/wk · ▲275% · z 11` + **10-week sparkline** (week −9…0) | ⭐⭐⭐⭐⭐ statistical rigor visible |
| **Acknowledge workflow** | Alerts are actionable, not decorative | ⭐⭐⭐⭐ |
| Largest hotspots cards | `#1 Peenya PS · Robbery · 735 m · 97% night · 62` — **night-share metric** | ⭐⭐⭐⭐ |
| "Open hotspot map →" | Cross-link into Geospatial with context kept | ⭐⭐⭐⭐ connected workflow |
| District/status/crime-type/age charts | Full statistical breakdown | ⭐⭐⭐ |

### Geospatial Ops (Hotspot Map)
| Feature | Detail | Rating |
|---|---|---|
| **112 ranked hotspots statewide** | Each: station, top crime, true radius in metres, night share %, case count | ⭐⭐⭐⭐⭐ |
| District drill-down | 12 districts + all-Karnataka scope | ⭐⭐⭐ |
| Crime-type filter | Grouped offence taxonomy (IPC heads) | ⭐⭐⭐ |
| Recency chips | All / 30d / 90d / 180d | ⭐⭐⭐ |
| **Time-lapse player (hidden gem)** | ▶ animates the window 12mo→30d; map re-renders each step; URL tracks it (`days=90`…) — *watch crime evolve over time* | ⭐⭐⭐⭐⭐ judges will not expect this |
| Hotspot detail panel | **AI-DERIVED badge**, cases-in-cluster, radius, night window share, **incidents-by-hour histogram (day vs night bars)**, full crime breakdown table | ⭐⭐⭐⭐⭐ |
| Per-FIR dot tooltips | Hover any dot: crime, station, timestamp | ⭐⭐⭐⭐ |
| Map layers legend | District shade = case velocity; true-radius hotspots; **pulsing = active trend alert** (map + alerts are connected) | ⭐⭐⭐⭐ |
| Current-view stats | 5,000 cases plotted · largest cluster 2,791 · 16,032 geolocated | ⭐⭐⭐ |

### MO Profiles
| Feature | Detail | Rating |
|---|---|---|
| Narrative → structured MO | 8 attributes (action, target, mobility, approach, offenders, weapon, time, escape) extracted from FIR free text | ⭐⭐⭐⭐⭐ |
| **Evidence-anchored highlighting** | Hover a value → the exact source words highlight in the narrative | ⭐⭐⭐⭐⭐ THE differentiator |
| **"Never guesses"** | No evidence → shown as "—", never fabricated ("A dash means the narrative didn't say") | ⭐⭐⭐⭐⭐ responsible AI, visible |
| Keyword search + attribute filters | Search narrative text or FIR number; filter by action/target/mobility vocabulary (schema-driven, can't drift) | ⭐⭐⭐⭐ |
| Similar-case search | One click → cases committed the same way, each with a why ("same offender count, mobility, crime action, target type") + score | ⭐⭐⭐⭐⭐ |
| First-run setup modal | "Setting up MO profiles…" — index builds off the request path; cache-first afterwards | ⭐⭐⭐ engineering honesty |
| Paged list, 15/page | Server-side paging, per-page cache | ⭐⭐⭐ |

### Networks (Association Graph)
| Feature | Detail | Rating |
|---|---|---|
| Seeded graph | Seed by Case (FIR) / Police station / District | ⭐⭐⭐⭐ |
| 9 node types | Case, Accused, Victim, Station, District, Crime type, Crime head, IPC section, Court | ⭐⭐⭐⭐ |
| **"Every edge cites its FIR"** | The graph is an *observed record graph* — no inferred edges presented as fact | ⭐⭐⭐⭐⭐ provenance philosophy |
| Person → "See similar people" | Jumps into Identities with that person's search pre-run — cross-module workflow | ⭐⭐⭐⭐⭐ |

### Identities
| Feature | Detail | Rating |
|---|---|---|
| Ranked accused list | By distinct case count, 15/page, instant paging | ⭐⭐⭐⭐ |
| **Duplicate-person detection** | "Find similar person" → match cards with **contributing AND contradictory evidence tags** (`name ~ 1.00`, `same sex`, `age within 1 year`), cross-district flag | ⭐⭐⭐⭐⭐ |
| Leads-not-conclusions copy | "a lead for review, never a confirmed identity" | ⭐⭐⭐⭐⭐ responsible policing AI |
| Blocking "searching" modal | Honest live-computation feedback | ⭐⭐⭐ |

### Anomalies
| Feature | Detail | Rating |
|---|---|---|
| Ranked review queue | 25 flagged: severity (serious/warning), type (out-of-place crime, unusual timing, unusually many accused), **σ deviation score** | ⭐⭐⭐⭐⭐ |
| **"✓ ML" corroboration badges** | Statistical flag independently confirmed by an IsolationForest model — two methods agreeing | ⭐⭐⭐⭐⭐ |
| **LLM plain-English explanations** | Expand a row: "Cyber Fraud is unusual at Shivamogga Town PS because it is rare at 0.9%." — *explained by GLM-4.7* | ⭐⭐⭐⭐⭐ AI that explains itself |
| Filter chips | All / Critical / ML-confirmed | ⭐⭐⭐ |
| Open FIR → graph | Anomaly jumps straight into the Networks graph for that case | ⭐⭐⭐⭐⭐ connected workflow |

### Area Risk
| Feature | Detail | Rating |
|---|---|---|
| 30-day forecast | 533 cases expected statewide, +1% vs last 30d, 5 rising / 3 falling, high/medium/low banding | ⭐⭐⭐⭐ |
| **"Needs attention this month"** | Mysuru ▲22% — the model's single actionable headline | ⭐⭐⭐⭐ |
| **Risk ladder with momentum markers** | "Bar length is the forecast; the marker is cases now — the gap is the momentum" | ⭐⭐⭐⭐⭐ genuinely clever viz |
| Filters | All / High risk / Rising | ⭐⭐⭐ |
| Model provenance | `Model: quickml:area-risk-forecast:v1` + "a planning guide, not a certainty" | ⭐⭐⭐⭐⭐ |

---

## 2 · Hidden features discovered (a normal viewer would miss all of these)

1. **Map time-lapse player** — ▶ + window chips animates crime through time; URL follows each step.
2. **Alert ⇄ map linkage** — stations with an active trend alert *pulse* on the map; the legend says so.
3. **10-week sparklines inside alert cards** — the z-score is backed by visible weekly counts.
4. **σ scores + dual-method corroboration** on every anomaly (statistical + IsolationForest).
5. **LLM-generated explanations** (GLM-4.7) hidden behind row expansion.
6. **Momentum markers** on the risk ladder (forecast vs. now, gap = momentum).
7. **Live nav badges** (alert count, anomaly count) driven by the same APIs.
8. **Shareable URL state** for literally everything, including the time-lapse window.
9. **Provenance discipline**: AI-DERIVED badges, model versions, and limitations text on every AI surface.
10. **Night-share %** on every hotspot (patrol-planning signal).

## 3 · Innovation highlights (what to sell)

- **Evidence-anchored AI**: every extracted MO value points at the exact words that produced it; UNKNOWN is honest.
- **Three independent AI methods, all explainable**: rule/lexicon extraction (MO), IsolationForest + LLM explanation (Anomalies), QuickML regression (Risk) — each labelled with model version and limitations.
- **Connected investigation loop**: Alert → Map → Case → MO → Similar cases → Graph → Person → Identities. No dead ends.
- **Leads-not-conclusions doctrine** across Identities/Networks/Anomalies — precisely the posture a police AI must take.
- **Production quality**: caches, warmers, off-request index builds, first-run setup modal, URL state, 325 backend tests, CI/CD.

## 4 · Weak areas — do not show
- Cold-start spinners (avoid by pre-warming before recording).
- MO first-run setup modal (fine to *mention*, not to sit through).
- Theme toggle (nice, not judge-relevant; skip).
- Long hotspot list scrolling past #10 (repetitive).

## 5 · Judge wow moments (in order of impact)
1. MO hover → narrative highlight (evidence-anchored AI).
2. Anomaly expansion → plain-English LLM explanation with σ score.
3. Map time-lapse (crime evolving over time).
4. Similar-cases list with per-match reasons.
5. Identities duplicate detection with contradictory evidence shown.
6. Risk ladder momentum markers.
7. The always-on synthetic-data banner + provenance badges (trust).

## 6 · Story order (not menu order)
Problem → **Trends** (the state watches itself) → **Map** (+time-lapse: where, and how it moves) → **MO** (inside a case: the hero) → similar cases → **Networks** (cases become a web) → **Identities** (people resolve) → **Anomalies** (the system audits the data) → **Area Risk** (it looks forward) → Trust close.

## 7 · Suggested improvements before recording (optional, all small)
- Pre-warm every tab (existing warmers make this a 2-minute job).
- Pick a hotspot with a dramatic hour-of-day histogram for the map scene (Jayanagar #1 works).
- MO search term "chain" lands on gold-chain snatching — visually perfect; keep it.

## 8 · Product improvements that would impress judges (future work, not for this video)
- An "export briefing PDF" button on Trends (one-click daily brief).
- Alert → WhatsApp/SMS notification hook (Catalyst functions).
- A small "how this number was computed" popover on forecast bars (the provenance data already exists in the API).
