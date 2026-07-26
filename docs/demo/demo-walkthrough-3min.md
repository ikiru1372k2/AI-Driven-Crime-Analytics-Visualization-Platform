# KAVACH AI — 3-Minute Demo Walkthrough (OBS Recording Guide)

Target: **3:00 total** · voiceover pace ~140 words/min (≈420 words) · record in one take if possible.

---

## Before you hit Record (5-minute prep — do NOT skip)

1. **Warm the app.** Open https://kavach.development.catalystappsail.in/ and click through
   EVERY tab once (Trends, Geospatial Ops, MO Profiles, Networks, Identities, Anomalies,
   Area Risk). This forces the backend cold-start + cache warm so nothing spins or shows a
   setup modal mid-recording. Wait for the MO tab to finish "Setting up MO profiles…" if it
   appears.
2. **Browser:** full screen (F11), 1920×1080, 100% zoom, hide bookmarks bar, close other tabs.
3. **Theme:** pick one (dark reads better on video) and stay with it — don't toggle mid-demo.
4. **OBS:** 1080p/30fps, Display or Window capture on the browser, mic checked, desktop audio muted.
5. **Open these two tabs in order** so you can Ctrl+Tab between them:
   - Tab A: `https://kavach.development.catalystappsail.in/#view=overview&district=44&hotspot=1&seed=CASE%3A7231`
   - Tab B: `https://github.com/ikiru1372k2/AI-Driven-Crime-Analytics-Visualization-Platform` (only if you do the optional code segment)
6. **Do one silent rehearsal run** of the click path below. The clicks must be muscle memory;
   the voiceover carries the demo.

---

## The 3:00 Script

> Format: **[time] SCREEN — what you do** then the voiceover to read.
> Read at a calm pace; if you finish a line early, let the screen breathe — don't rush clicks.

---

### [0:00–0:20] Tab A: Trends (loads from your URL) — don't click anything yet

**Do:** Let the Trends dashboard sit on screen. Move the cursor slowly toward the yellow banner, then the case count.

**Say:**
> "This is KAVACH AI — a crime intelligence platform built for the Karnataka State Police
> Datathon. Everything you'll see runs on synthetic data — two thousand two hundred
> thirty-six FIRs — on Zoho Catalyst, end to end."

*(~34 words)*

---

### [0:20–0:45] Trends — scroll once, hover an alert card

**Do:** Scroll down slowly through the trend alerts / district velocity, hover one alert card.

**Say:**
> "The Trends view is the morning briefing. It watches every district and flags where crime
> is accelerating — each alert says what changed, where, and by how much, so an officer
> starts the day knowing exactly where to look."

*(~38 words)*

---

### [0:45–1:15] Geospatial Ops — click the "Geospatial Ops" tab

**Do:** Click **Geospatial Ops**. The map opens with district 44 filtered and hotspot #1
selected (from the URL state). Hover the top hotspot, then pan slightly.

**Say:**
> "Geospatial Ops puts those numbers on the map. These are ranked crime hotspots —
> here's hotspot number one in this district. Filters narrow by crime type, district, and
> time window, and stations with an active alert pulse on the map. Every view is a
> shareable URL, so this exact map state can be sent to a field officer."

*(~58 words)*

---

### [1:15–1:50] MO Profiles — click the "MO Profiles" tab

**Do:** Click **MO Profiles**. Type `chain` in the search bar, press Search. Then click the
first result row. When the case opens, hover one attribute (watch the narrative highlight),
then click **"Show similar cases"**.

**Say:**
> "MO Profiles reads every FIR narrative and extracts *how* the crime was committed —
> the action, the target, the mobility. I can search by keyword — chain — and open a case.
> Hovering a value highlights the exact words in the narrative it came from — nothing is
> asserted without evidence. And one click finds other cases committed the same way —
> a lead an investigator can actually follow."

*(~64 words)*

---

### [1:50–2:15] Networks — click the "Networks" tab

**Do:** Click **Networks**. The graph seeds from CASE 7231 (from the URL). Click one
connected node to expand it.

**Say:**
> "Networks turns a case into a graph — the accused, victims, and connected cases around
> FIR seven-two-three-one. Expanding a node walks the network outward, which is how an
> investigator finds the non-obvious link between two cases."

*(~36 words)*

---

### [2:15–2:40] Identities — click the "Identities" tab

**Do:** Click **Identities**. Let the ranked list show, then click **"Find similar person"** on the
top row. Results appear with match signals.

**Say:**
> "Identities ranks accused by how many crimes they're involved in — and for any person,
> finds likely duplicate records: same person, name spelled differently across FIRs. Every
> match shows its evidence and is a lead for review — never an automatic conclusion."

*(~41 words)*

---

### [2:40–2:52] Anomalies → Area Risk — click "Anomalies", pause, click "Area Risk"

**Do:** Click **Anomalies** (2 seconds on screen), then **Area Risk** (2–3 seconds).

**Say:**
> "Anomalies flags cases that don't fit the pattern, and Area Risk forecasts where pressure
> is building next — detection through explanation, in one place."

*(~24 words)*

---

### [2:52–3:00] Close — go back to Trends tab

**Do:** Click **Trends** to end where you began. Hold the frame.

**Say:**
> "Nine modules, one platform, fully deployed on Catalyst — this is KAVACH AI. Thank you."

*(~15 words)*

---

**Word total: ~310** — deliberately under 420 so clicks and screen-moments get air. If you
speak fast, slow down on the MO and Networks scenes; they're the differentiators.

---

## Optional add-on: 60-second GitHub / codebase walkthrough

Record as a **separate clip** (easier to edit than one long take).

### [0:00–0:15] Tab B: GitHub repo root

**Do:** Show the repo landing page, scroll slowly past the README.

**Say:**
> "The codebase is a monorepo — a FastAPI backend, a React TypeScript frontend, and the
> Catalyst deployment config, shipped through CI/CD on every merge to main."

### [0:15–0:35] Click into `backend/kavach/`

**Do:** Navigate to `backend/kavach/` — hover `analytics/`, then `api/`.

**Say:**
> "The backend is organised by intelligence type — analytics holds the engines: MO
> extraction, entity resolution, anomaly detection, risk forecasting. Every AI-derived answer
> carries a provenance envelope — what method, what model version, what limitations —
> so nothing is a black box."

### [0:35–0:50] Click into `frontend/src/app/`

**Do:** Show the components list briefly.

**Say:**
> "The frontend is one component per module, with a shared query cache so revisited tabs
> paint instantly, and every screen state lives in the URL."

### [0:50–1:00] Back to repo root — Pull Requests tab

**Do:** Open the closed PRs list, scroll once.

**Say:**
> "Everything landed through reviewed pull requests with tests — three hundred twenty-five
> passing on the backend alone. That's the engineering behind the demo."

---

## OBS quick checklist

| Setting | Value |
|---|---|
| Canvas / Output | 1920×1080, 30 fps |
| Encoder | x264 (or hardware), CBR ~8000 Kbps |
| Mic | Filters → Noise Suppression + Gain; test level ‑12 dB peak |
| Desktop audio | **Muted** (no notification dings) |
| Scene | Single Display/Window Capture of the browser, cursor visible |
| Recording format | mkv (remux to mp4 after) — survives a crash |

**Recovery tips**
- If any tab shows a spinner mid-take: pause narration, let it load, keep rolling — cut the
  dead seconds in the edit. Don't restart the whole take.
- If the MO tab shows "Setting up MO profiles…" you skipped step 1 of prep — stop, let it
  finish, and re-record that scene only.
- Record voiceover live with the screen if you can (energy matches the clicks). If you
  dub afterwards, record the screen first with this script open on a second monitor.
