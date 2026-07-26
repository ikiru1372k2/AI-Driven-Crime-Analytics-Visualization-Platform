# KAVACH AI — Complete Demo Script (Record-Ready)

**Total runtime:** 4:00 — Part 1: application walkthrough (3:00) + Part 2: GitHub/codebase (1:00)
**Voice pace:** calm, ~140 words/minute. Bold text = say it with emphasis.
**Legend:** 🖱 = what you do on screen · 🎙 = what you say (read verbatim)

---

## PRE-RECORDING CHECKLIST (do all of this BEFORE OBS starts)

- [ ] Open https://kavach.development.catalystappsail.in/ and click through **all seven tabs** once. Wait for every spinner to finish. If MO Profiles shows *"Setting up MO profiles…"*, wait until the list appears.
- [ ] Confirm the MO tab shows the **new design** (centered search bar). If it shows an old two-pane layout, PR #149 hasn't deployed — merge/deploy it first.
- [ ] On the MO tab, type `chain` and press Search — confirm results appear. (If empty, use `mobile` in the script instead.)
- [ ] Browser full screen (F11), 1920×1080, zoom 100%, dark theme, bookmarks bar hidden, notifications off.
- [ ] OBS: 1080p/30fps · mic tested (peaks ≈ −12 dB) · desktop audio muted · recording to MKV.
- [ ] **Tab A (start here):**
  `https://kavach.development.catalystappsail.in/#view=overview&district=44&hotspot=1&seed=CASE%3A7231`
- [ ] **Tab B:** `https://github.com/ikiru1372k2/AI-Driven-Crime-Analytics-Visualization-Platform`
- [ ] Do one silent rehearsal of the click path. Then record.

---
---

# PART 1 — APPLICATION WALKTHROUGH (3:00)

---

## SCENE 1 · 0:00–0:20 · TRENDS (opening)

🖱 **Start recording on Tab A.** The Trends dashboard is already loaded. Don't click anything for the first 8 seconds. Slowly move the cursor to the yellow banner ("Synthetic demo data"), then to the case count.

🎙
> "This is **KAVACH AI** — a crime intelligence platform built for the Karnataka State Police Datathon.
> It takes raw F-I-R data and turns it into something an officer can act on — trends, hotspots, modus operandi, and networks.
> Everything you'll see today runs on **synthetic data** — two thousand two hundred and thirty-six FIRs — deployed end to end on **Zoho Catalyst**."

---

## SCENE 2 · 0:20–0:45 · TRENDS (the briefing)

🖱 Scroll down slowly — one smooth scroll through the alert cards and district velocity. Hover **one** alert card and hold for two seconds.

🎙
> "The Trends view is the **morning briefing**.
> It watches every district and automatically flags where crime is accelerating.
> Each alert tells you **what** changed, **where** it changed, and **by how much** — so the day starts with focus, not with spreadsheets."

---

## SCENE 3 · 0:45–1:15 · GEOSPATIAL OPS (the map)

🖱 Click the **Geospatial Ops** tab. The map opens with district 44 filtered and **hotspot #1 already selected** (it comes from the URL). Hover the selected hotspot, hold two seconds, then pan the map slightly. Point the cursor briefly at the filter sidebar.

🎙
> "Geospatial Ops puts those numbers **on the ground**.
> These are ranked crime hotspots — and this is hotspot **number one** for this district.
> On the left, I can narrow by crime type, district, and time window — and stations with an active trend alert **pulse** on the map.
> One more thing: every screen state lives in the URL — so this exact view, filters and all, can be **shared with a field officer** as a single link."

---

## SCENE 4 · 1:15–1:50 · MO PROFILES (the showcase — slow down here)

🖱 Click the **MO Profiles** tab. Then, deliberately:
1. Click the search bar, type `chain`, click **Search**.
2. Click the **first result row**.
3. When the case opens, **hover the "Action" value** — watch the narrative highlight. Hold three seconds.
4. Click **"Show similar cases"**. Let the list render.

🎙
> "This is **MO Profiles** — my favourite part.
> The system reads every F-I-R narrative and extracts **how** the crime was committed — the action, the target, the mobility.
> I search by keyword — *chain* — and open a case.
> Now watch this: when I hover an extracted value, it **highlights the exact words** in the narrative it came from. Nothing is asserted without evidence — if the narrative didn't say it, the system shows a dash instead of guessing.
> And with one click — **show similar cases** — it finds other crimes committed the *same way*. That's a real investigative lead."

---

## SCENE 5 · 1:50–2:15 · NETWORKS (the graph)

🖱 Click the **Networks** tab. The graph opens **already seeded from CASE 7231** (from the URL). Let it settle for two seconds, then click one connected node to expand it.

🎙
> "Networks turns a single case into a **living graph** — the accused, the victims, and the connected cases around F-I-R seven-two-three-one.
> Clicking any node walks the network outward.
> This is how an investigator finds the **non-obvious link** — the person who quietly appears in two unrelated cases."

---

## SCENE 6 · 2:15–2:40 · IDENTITIES

🖱 Click the **Identities** tab. The ranked accused list is on screen. Pause two seconds, then click **"Find similar person"** on the top row. Wait for the match results (a brief "searching" modal will show — that's fine).

🎙
> "Identities ranks accused persons by how many crimes they're involved in.
> And for any person, it searches for **likely duplicate records** — the same individual, name spelled differently across FIRs.
> Every match shows its supporting and contradicting evidence — it's a **lead for review**, never an automatic conclusion. That distinction matters in policing."

---

## SCENE 7 · 2:40–2:52 · ANOMALIES → AREA RISK (quick tour)

🖱 Click **Anomalies** — hold three seconds. Then click **Area Risk** — hold three seconds.

🎙
> "Anomalies flags the cases that **don't fit the pattern** and explains why.
> And Area Risk forecasts where pressure is building **next** — from detection all the way to explanation, in one place."

---

## SCENE 8 · 2:52–3:00 · CLOSE

🖱 Click **Trends** — ending where we began. Hold the frame steady until you finish speaking, then two more seconds of silence before stopping.

🎙
> "From raw FIRs to actionable intelligence — fully deployed on Catalyst.
> **This is KAVACH AI. Thank you.**"

---
---

# PART 2 — GITHUB / CODEBASE WALKTHROUGH (1:00)

*Record as a separate clip, then join in editing.*

---

## SCENE 9 · 0:00–0:15 · REPO ROOT

🖱 Switch to Tab B (GitHub repo). Scroll slowly once through the README.

🎙
> "A quick look under the hood.
> The codebase is a **monorepo** — a FastAPI backend, a React TypeScript frontend, and the Catalyst deployment config — shipped through **CI/CD on every merge to main**."

---

## SCENE 10 · 0:15–0:35 · BACKEND

🖱 Click into `backend/` → `kavach/`. Hover `analytics/`, then `api/`.

🎙
> "The backend is organised by intelligence type.
> The analytics package holds the engines — MO extraction, entity resolution, anomaly detection, and risk forecasting.
> And every AI-derived answer carries a **provenance envelope** — which method, which model version, what its limitations are. **Nothing is a black box.**"

---

## SCENE 11 · 0:35–0:50 · FRONTEND

🖱 Navigate to `frontend/src/app/`. Let the component list show.

🎙
> "The frontend is one component per module, with a shared query cache — so revisited tabs paint **instantly** — and every screen state is a shareable URL."

---

## SCENE 12 · 0:50–1:00 · PULL REQUESTS (close)

🖱 Click the **Pull requests** tab → **Closed**. Scroll once, slowly.

🎙
> "Everything here landed through **reviewed pull requests with tests** — over three hundred passing on the backend alone.
> That's the engineering behind the demo. **Thank you.**"

---
---

# VOICEOVER-ONLY VERSION (for dubbing after screen capture)

*If you record the screen first and dub audio later, read this straight through with the pauses marked. Total ≈ 4 minutes.*

> This is KAVACH AI — a crime intelligence platform built for the Karnataka State Police Datathon. It takes raw FIR data and turns it into something an officer can act on — trends, hotspots, modus operandi, and networks. Everything you'll see today runs on synthetic data — two thousand two hundred and thirty-six FIRs — deployed end to end on Zoho Catalyst.
>
> *(pause — switch to scrolling Trends)*
>
> The Trends view is the morning briefing. It watches every district and automatically flags where crime is accelerating. Each alert tells you what changed, where it changed, and by how much — so the day starts with focus, not with spreadsheets.
>
> *(pause — map opens)*
>
> Geospatial Ops puts those numbers on the ground. These are ranked crime hotspots — and this is hotspot number one for this district. On the left, I can narrow by crime type, district, and time window — and stations with an active trend alert pulse on the map. One more thing: every screen state lives in the URL — so this exact view, filters and all, can be shared with a field officer as a single link.
>
> *(pause — MO tab, typing)*
>
> This is MO Profiles — my favourite part. The system reads every FIR narrative and extracts how the crime was committed — the action, the target, the mobility. I search by keyword — chain — and open a case. Now watch this: when I hover an extracted value, it highlights the exact words in the narrative it came from. Nothing is asserted without evidence — if the narrative didn't say it, the system shows a dash instead of guessing. And with one click — show similar cases — it finds other crimes committed the same way. That's a real investigative lead.
>
> *(pause — graph settles)*
>
> Networks turns a single case into a living graph — the accused, the victims, and the connected cases around FIR seven-two-three-one. Clicking any node walks the network outward. This is how an investigator finds the non-obvious link — the person who quietly appears in two unrelated cases.
>
> *(pause — identities list)*
>
> Identities ranks accused persons by how many crimes they're involved in. And for any person, it searches for likely duplicate records — the same individual, name spelled differently across FIRs. Every match shows its supporting and contradicting evidence — it's a lead for review, never an automatic conclusion. That distinction matters in policing.
>
> *(pause — anomalies, then area risk)*
>
> Anomalies flags the cases that don't fit the pattern and explains why. And Area Risk forecasts where pressure is building next — from detection all the way to explanation, in one place.
>
> *(pause — back on Trends)*
>
> From raw FIRs to actionable intelligence — fully deployed on Catalyst. This is KAVACH AI. Thank you.
>
> *(cut — GitHub clip)*
>
> A quick look under the hood. The codebase is a monorepo — a FastAPI backend, a React TypeScript frontend, and the Catalyst deployment config — shipped through CI/CD on every merge to main.
>
> *(pause — backend folders)*
>
> The backend is organised by intelligence type. The analytics package holds the engines — MO extraction, entity resolution, anomaly detection, and risk forecasting. And every AI-derived answer carries a provenance envelope — which method, which model version, what its limitations are. Nothing is a black box.
>
> *(pause — frontend folder)*
>
> The frontend is one component per module, with a shared query cache — so revisited tabs paint instantly — and every screen state is a shareable URL.
>
> *(pause — pull requests)*
>
> Everything here landed through reviewed pull requests with tests — over three hundred passing on the backend alone. That's the engineering behind the demo. Thank you.

---

# IF SOMETHING GOES WRONG MID-TAKE

| Problem | Fix |
|---|---|
| A tab shows a spinner | Stop talking, let it load, resume. Trim the gap in editing — don't restart. |
| MO shows "Setting up MO profiles…" | You skipped the warm-up. Let it finish, re-record Scene 4 only. |
| `chain` search returns nothing | Use `mobile` instead — the sentence still works. |
| Graph doesn't show CASE 7231 | Reload Tab A's full URL (the seed is in it), then click Networks again. |
| You stumble on a line | Pause two seconds, re-read the whole sentence. Cut the flub in editing. |
