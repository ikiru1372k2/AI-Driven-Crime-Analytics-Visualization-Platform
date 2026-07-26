# KAVACH AI — Hackathon Demo Video: Full Production Plan & Script

**Deliverable:** one 3:00 MP4, 1920×1080, fully auto-produced —
**Playwright** drives and records the browser · **edge-tts** (AI voice) narrates the script · **ffmpeg** syncs and muxes.
No OBS, no mic, no human clicking. Re-runnable any time the app changes.

---

## 1 · The winning narrative (why this script is shaped this way)

Hackathon judges score four things. Every scene is engineered to hit one:

| Judges look for | Where the video proves it |
|---|---|
| **Real problem, real user** | Cold open: FIR intelligence is locked in text — an officer's morning briefing (Scene 1–2) |
| **A "wow" only you have** | MO Profiles: narrative → structured MO with **evidence highlighting**, "never guesses", similar-case search (Scene 4 — the hero, gets the most seconds) |
| **Depth, not a facade** | Cross-linked modules (map ⇄ alerts, graph ⇄ identities), live filters, pagination, everything clickable on screen (Scenes 3, 5, 6) |
| **Trust & rigor** | Synthetic-data banner always visible; every AI answer carries method + model version + limitations; Catalyst-native, CI/CD, 325 tests (Scenes 1, 7, 8 voiceover) |

**Narrative arc:** *Problem → Briefing → Ground truth → The wow (MO) → The web (Networks/Identities) → The guardian (Anomalies/Risk) → Trust → Close.*

---

## 2 · Feature inventory (verified on the live build)

| Tab | What's on screen | The demo-able "wow" |
|---|---|---|
| **Trends** (Overview) | "State Intelligence Overview": Emerging trends ranked by deviation, largest hotspots (90d), cases by district, FIR status, top crime types, accused by age | Alert cards say *what changed, where, by how much* |
| **Geospatial Ops** | MapLibre map, ranked hotspots, filters (crime type / district / days), pulsing alert stations | URL preloads district 44 + hotspot #1 — zero setup clicks; shareable state |
| **MO Profiles** | Identities-style search + filters (action/target/mobility), 15/page list, case detail | **Hover a value → the source words highlight in the narrative**; UNKNOWN = "—" (never guesses); "Show similar cases" |
| **Networks** | Case graph seeded from URL (CASE 7231), expandable nodes, person → "See similar people" | One case becomes a living, walkable web |
| **Identities** | Ranked accused (15/page), "Find similar person", match cards with contributing/contradictory signals | Duplicate-person detection with visible evidence, "lead not conclusion" |
| **Anomalies** | Flagged-case queue, "corroborated by the IsolationForest model", open case → graph | ML anomaly detection that explains itself |
| **Area Risk** | District risk forecast with model version + reason | Forward-looking, not just reactive |
| **Everywhere** | Yellow banner: "Synthetic demo data — not real FIRs" · 2,236 cases | Ethics on-screen for the entire video |

---

## 3 · Duration plan — 3:00

| # | Time | Scene | Sec | Why it gets this much |
|---|---|---|---|---|
| 1 | 0:00–0:18 | Cold open (Trends) | 18 | Hook + credibility (Catalyst, synthetic) |
| 2 | 0:18–0:42 | Trends briefing | 24 | Sets the "officer's day" story |
| 3 | 0:42–1:06 | Geospatial Ops | 24 | Visual anchor; shareable-URL point |
| 4 | 1:06–1:48 | **MO Profiles (hero)** | 42 | The differentiator — evidence highlighting must breathe |
| 5 | 1:48–2:12 | Networks | 24 | Second-strongest visual |
| 6 | 2:12–2:34 | Identities | 22 | Dedup + ethics one-two punch |
| 7 | 2:34–2:48 | Anomalies → Area Risk | 14 | Breadth, fast cuts |
| 8 | 2:48–3:00 | Trust + close (Trends) | 12 | Provenance line + brand close |

---

## 4 · THE SCRIPT (Playwright actions + AI voiceover, scene by scene)

> 🤖 = what the Playwright recorder does (exact, automatable)
> 🎙 = the AI voiceover line (edge-tts reads this verbatim)
> Each scene's on-screen hold = max(scripted seconds, voice duration + 0.5 s) — sync is automatic.

---

### SCENE 1 · 0:00–0:18 · COLD OPEN — Trends

🤖 `goto` `https://kavach.development.catalystappsail.in/#view=overview&district=44&hotspot=1&seed=CASE%3A7231` → `wait_for_selector('h2:has-text("State Intelligence Overview")')` → hold still 3 s → slow `mouse.move` to the synthetic-data banner → hold.

🎙
> "Every day, police stations across Karnataka file hundreds of FIRs. The intelligence inside them is real — but it's locked away in free text. **KAVACH AI unlocks it.** Built end-to-end on Zoho Catalyst, running entirely on synthetic data — two thousand two hundred and thirty-six cases."

---

### SCENE 2 · 0:18–0:42 · TRENDS — the morning briefing

🤖 Smooth `mouse.wheel` scroll through "Emerging trends · ranked by deviation" → pause on the first alert card → `hover` it → scroll to "Cases by district" → hold.

🎙
> "This is the State Intelligence Overview — an officer's **morning briefing**. Emerging trends, ranked by how far they deviate from normal. The moment crime accelerates anywhere in the state, KAVACH flags it — **what** changed, **where**, and **by how much**. No spreadsheets. Just focus."

---

### SCENE 3 · 0:42–1:06 · GEOSPATIAL OPS — ground truth

🤖 `click('text=Geospatial Ops')` → `wait_for_selector('.map-col canvas')` + 2 s settle → map opens with district 44 filtered and hotspot #1 pre-selected (URL state) → `hover` the selected hotspot in the sidebar → slow `mouse.move` across the map → brief pause on the filter sidebar.

🎙
> "One click, and those numbers hit the ground. Ranked crime hotspots — this is **hotspot number one** for this district. Filters narrow by crime type, district, and time window, and stations with an active alert **pulse** on the map. And every view is a URL — this exact picture can be shared with a field officer as a single link."

---

### SCENE 4 · 1:06–1:48 · MO PROFILES — **the hero scene**

🤖 `click('text=MO Profiles')` → wait for `.id-search input` (setup modal already warmed away pre-roll) → `type('chain', delay=80)` (visible human-speed typing) → `click('button:has-text("Search")')` → wait for `.mo-row` → 1.5 s pause → `click` first `.mo-row` → wait for `.mo-narrative` → **`hover` the "Action" attribute row** → hold 3 s (the highlight is the money shot) → `hover` the "Target" row → hold 2 s → `click('button:has-text("Show similar cases")')` → wait for `.mo-related` → slow scroll through matches.

🎙
> "Here's where KAVACH goes beyond dashboards. **MO Profiles** reads every FIR narrative and extracts *how* the crime was committed. I search one word — *chain* — and open a case. Now watch: hovering an extracted value **highlights the exact words it came from**. And if the narrative didn't say it? KAVACH shows a dash. It **never guesses**. One more click — and here are the other cases committed the *same way*. From a single FIR to a pattern, in seconds."

---

### SCENE 5 · 1:48–2:12 · NETWORKS — the web

🤖 `click('text=Networks')` → graph auto-seeds from CASE 7231 (URL) → wait for canvas + 2.5 s layout settle → `click` a connected node (via canvas coordinates or the detail panel list) → 2 s → slow `mouse.move` around the expanded graph.

🎙
> "Networks turns a single case into a **living graph** — the accused, the victims, and every connected case around FIR seven-two-three-one. Expanding a node walks the web outward. This is how investigators find the **non-obvious link** — the person who quietly appears in two unrelated cases."

---

### SCENE 6 · 2:12–2:34 · IDENTITIES — one person, many spellings

🤖 `click('text=Identities')` → wait for `.accused-row` → 2 s on the ranked list → `click` first `.find-similar-btn` → the "searching" modal shows (keep it — it reads as live computation) → wait for `.match-card` → `hover` the top match's signal tags.

🎙
> "Identities ranks accused by how many crimes they're involved in — then finds **likely duplicate records**: the same person, spelled differently across FIRs. Every match shows its supporting *and* contradicting evidence. A lead for review — **never** an automatic accusation. In policing, that distinction is everything."

---

### SCENE 7 · 2:34–2:48 · ANOMALIES → AREA RISK — fast cuts

🤖 `click('text=Anomalies')` → wait for content → hold 6 s → `click('text=Area Risk')` → wait → hold 6 s.

🎙
> "Anomalies flags the cases that break the pattern — corroborated by an Isolation-Forest model. And Area Risk forecasts where pressure builds **next**. Detection, explanation, and foresight — one platform."

---

### SCENE 8 · 2:48–3:00 · CLOSE — trust

🤖 `click('text=Trends')` → hold the opening frame steady → end recording 2 s after the voice stops.

🎙
> "And every AI answer in KAVACH carries its method, its model version, and its limitations — on the record. **Explainable. Ethical. Deployed.** This is KAVACH AI."

---

**Voiceover total: ~330 words** — comfortable inside 3:00 at a presenter's pace, leaving air for the visuals.

---

## 5 · Production pipeline (how the automation works)

```
script.json  ──►  gen_audio.py (edge-tts)  ──►  scene_01.mp3 … scene_08.mp3  + durations.json
                                                          │
record_demo.py (Playwright, 1920×1080, record_video) ◄────┘   scene hold = max(min_secs, audio + 0.5s)
        │  drives every 🤖 action above, logs actual scene start-times
        ▼
   demo_raw.webm  +  scene_times.json
        │
assemble.py (ffmpeg):  concat audio with silence-padding to scene_times  →  mux
        ▼
   KAVACH_demo_3min.mp4   (H.264 + AAC, 1080p)
```

**Key design choices**
- **Audio-first sync:** every scene's MP3 is generated and measured *before* recording; the Playwright script holds each scene until its narration would finish. Video and voice can't drift.
- **Voice:** `en-IN-PrabhatNeural` (male, Indian English) — fits the Karnataka context; alternate `en-IN-NeerjaNeural` (female). One flag to switch; regenerate in ~30 s.
- **Determinism:** the URL preloads district 44 / hotspot 1 / CASE 7231, so map and graph scenes need zero setup clicks.
- **Pre-roll warm-up (not recorded):** the script visits every tab once and waits for the MO index (`/api/v1/mo/status` → ready) *before* recording starts — no spinners or setup modals on camera.
- **Re-runnable:** change a voiceover line or a click path → re-run one command → new MP4 in ~5 minutes. This also means the video can be re-cut the night before submission at zero cost.

**Toolchain status (already installed & tested on this machine):**
- ✅ Playwright + Chromium (records video natively)
- ✅ edge-tts (verified: synthesis works, en-IN voices available)
- ✅ Full ffmpeg v7 via imageio-ffmpeg (verified: probes/encodes MP3)
- ✅ Live site verified: PR #149 (new MO design) is **merged & deployed**; `/api/v1/mo/status` returns 200

---

## 6 · Optional add-ons (only if the hackathon allows >3:00)

| Add-on | Extra time | What it shows |
|---|---|---|
| GitHub/codebase segment | +0:60 | Monorepo, provenance envelopes in code, 325 tests, CI/CD, reviewed PRs |
| Title card + end card | +0:08 | "KAVACH AI" branded open/close (ffmpeg drawtext — no extra tools) |
| Background music bed | +0 | Low-volume track under the voice (needs a royalty-free MP3 from you) |

---

## 7 · Execution checklist (when you say go)

1. Freeze this script (any wording edits happen now — regeneration is cheap but review isn't).
2. I generate the 8 narration MP3s and measure durations.
3. I run the recorder headless against the live site (with pre-roll warm-up).
4. I assemble and deliver `KAVACH_demo_3min.mp4` + all intermediate files (per-scene audio, raw video) so you can re-edit in future.
5. You review; any scene you dislike → tell me the change → I re-run just that piece.
