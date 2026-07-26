# KAVACH AI — Cinematic Demo Production Script (Phase 2)

**Runtime:** ~4 min 50 s (quality-first, per direction — no content cut to hit 3:00)
**Resolution:** 1920×1080 @ 30fps · **Voice:** `en-IN-PrabhatNeural`, rate +5% (calm, senior-engineer)
**Narration:** one continuous story — every second covered, every transition motivated.
**Pre-roll (not recorded):** visit all 7 tabs once; wait for `/api/v1/mo/status → ready`; confirm MO search "chain" returns rows.

Pacing reference: 2.3 words/second. Every scene's narration is sized to its screen time.

---

## SCENE 1 · The Problem (Trends, cold open)

- **Objective:** Hook. Establish the problem and the platform's credibility in one breath.
- **Playwright:** `goto('…/#view=overview')` → `wait_for_selector('h2:has-text("State Intelligence Overview")')` → 1s settle.
- **Expected loading:** 3–6 s (narration covers it — the opening line runs over the paint).
- **Camera:** static full frame.
- **Mouse:** enter from bottom-centre, drift slowly (60 steps) up to the yellow banner; trace it left→right; rest on "16,652 cases".
- **Scroll:** none. **Hover:** banner 2 s. **Wait:** hold to narration end. **Transition out:** 0 s (same page).
- **Duration:** 24 s
- **Voiceover (55 words):**
  > "Every day, police stations across Karnataka file hundreds of first-information reports. The intelligence inside them is real — but it is locked in free text, spread across tables, and invisible at state scale. KAVACH AI was built to unlock it. Sixteen thousand six hundred and fifty-two synthetic cases, three years of data, running end-to-end on Zoho Catalyst."
- **Why this scene exists:** Judges decide in the first 20 seconds whether this is "another dashboard." The synthetic banner + real scale answers ethics and credibility immediately.
- **Hackathon value:** Problem framing + data ethics on screen simultaneously.
- **Judge takeaway:** *This team understands the actual problem and handled data responsibly.*

---

## SCENE 2 · The Morning Briefing (Trends, alert anatomy)

- **Objective:** Show that alerts are statistics, not decoration — z-scores, baselines, sparklines, and an acknowledge workflow.
- **Playwright:** `hover('.alert-card, [class*=alert] >> nth=0')` → hold → slow `mouse.wheel(0,150)` ×4 with 0.4 s gaps through KPI strip → pause on "Cases by district".
- **Expected loading:** 0 s (already painted).
- **Camera:** static. **Mouse:** dwell on the ▲275% and "z 11" region of the card 3 s; then drift down with the scroll.
- **Scroll:** slow (150 px steps). **Hover:** alert card 3 s. **Transition out:** narration bridges into the map.
- **Duration:** 30 s
- **Voiceover (68 words):**
  > "The day starts here — the state intelligence overview. This alert is not a notification; it is a statistical finding. Robbery at Peenya police station is running at thirty cases a fortnight against a baseline of four a week — a two-hundred-and-seventy-five percent deviation, eleven standard deviations out, with ten weeks of history right on the card. An officer can acknowledge it, and every number below breaks the state down by district, status, and crime type."
- **Why:** The sparkline + z-score card is proof of statistical rigor most hackathon dashboards fake.
- **Hackathon value:** Depth on the very first screen.
- **Judge takeaway:** *The numbers have baselines. This is real anomaly math, not thresholds.*

---

## SCENE 3 · Where It Happens (Geospatial Ops)

- **Objective:** Ground the statistics on a live map; show hotspot ranking, the AI-DERIVED panel, and the alert⇄map linkage.
- **Playwright:** `click('nav >> text=Geospatial Ops')` → `wait_for_selector('canvas')` → 2.5 s tile settle → `click` hotspot row `#1 Jayanagar PS` in sidebar → detail panel opens → hover the hour-of-day histogram 2.5 s → slow sweep across the map (70 steps).
- **Expected loading:** 2–4 s map tiles — narration's first sentence covers it.
- **Camera:** static. **Scroll:** none. **Hover:** histogram 2.5 s, crime-breakdown table 2 s.
- **Transition in (spoken, covers the click):** *"But a number without a place is only half the truth…"*
- **Duration:** 34 s
- **Voiceover (78 words):**
  > "But a number without a place is only half the truth — so the same intelligence lands on the map. These are one hundred and twelve detected hotspots across Karnataka, each with a true radius in metres and its share of night-time crime. Hotspot number one: Jayanagar, two thousand seven hundred and ninety-one cases. The panel is marked AI-derived, and this histogram shows exactly when incidents happen through the day — which is what patrol planning actually needs. Stations with an active alert pulse, live, on this map."
- **Why:** Connects Scene 2's statistics to geography; the AI-DERIVED badge introduces the provenance doctrine.
- **Hackathon value:** Map + clustering + honest AI labelling in one shot.
- **Judge takeaway:** *Hotspots have radii, timings, and provenance — this is operational, not cosmetic.*

---

## SCENE 4 · Crime Through Time (the hidden gem)

- **Objective:** The time-lapse. Nobody expects a crime map to play like a film.
- **Playwright:** move cursor to the timeline bar bottom-centre → `click('button:text("▶")')` → let it animate ~10 s (windows step 12mo→30d; "window: last N" indicator updates; URL hash follows) → cursor rests near the window label.
- **Expected loading:** each step re-renders in <1 s; continuous motion.
- **Camera:** static — the map is the motion. **Hover:** window indicator 2 s at the end.
- **Duration:** 22 s
- **Voiceover (50 words):**
  > "And time is a dimension here, not a dropdown. Press play, and the map animates the last twelve months window by window — clusters growing, shifting, and dissolving as the window narrows to thirty days. Notice the address bar following along: every frame of this animation is itself a shareable link."
- **Why:** Motion is memorable; the URL detail turns a visual trick into an engineering point.
- **Hackathon value:** A feature judges have not seen in other crime dashboards.
- **Judge takeaway:** *Thoughtful engineering exists even in places nobody was asked to build.*

---

## SCENE 5 · Inside a Case (MO Profiles — the hero, part 1: search)

- **Objective:** Transition from "where" to "how". Show corpus-wide MO keyword search.
- **Playwright:** `click('nav >> text=MO Profiles')` → `wait_for_selector('.id-search input')` → hover the input 0.8 s → `click` → `type('chain', delay=120)` → hover Search 0.5 s → `click('button:text("Search")')` → `wait_for_selector('.mo-row')` → slow scroll 300 px through results.
- **Expected loading:** results <1 s (index is warm); the transition line covers tab switch.
- **Camera:** static. **Typing:** human speed (120 ms/char).
- **Transition in (spoken):** *"Knowing where crime happens is one thing. Understanding how it is committed is another…"*
- **Duration:** 26 s
- **Voiceover (60 words):**
  > "Knowing where crime happens is one thing — understanding *how* it is committed is another. MO Profiles reads every first-information report and extracts the modus operandi: the action, the target, the mobility. I type one word — chain — and the system searches every narrative in the corpus. Sixty-two cases, each already tagged with how the crime was done."
- **Why:** Sets up the hero moment; shows search is corpus-wide and instant.
- **Hackathon value:** NLP over unstructured FIR text — the challenge's hardest ask.
- **Judge takeaway:** *Free text became a queryable database.*

---

## SCENE 6 · The Evidence (MO Profiles — the hero, part 2: proof)

- **Objective:** THE moment. Hover → the narrative highlights the exact source words. Honest UNKNOWNs.
- **Playwright:** `click('.mo-row >> nth=0')` → `wait_for_selector('.mo-narrative')` → 1.5 s read pause → `hover('.mo-attr >> nth=0')` hold 3.5 s (highlight visible) → `hover('.mo-attr >> nth=1')` hold 3 s → `hover('.mo-attr >> nth=2')` hold 2.5 s → cursor rests on a "—" attribute 2 s.
- **Expected loading:** case detail <1 s.
- **Camera:** static; the highlight IS the camera movement.
- **Duration:** 32 s
- **Voiceover (73 words):**
  > "Here is the part that matters. This is the original narrative, and beside it, the extracted profile. When I hover 'action — robbery', watch the narrative: the exact words that produced that value light up. Every single attribute is anchored to evidence in the text. And where the narrative says nothing — the system shows a dash. It does not guess. In an investigation, an honest 'unknown' is worth more than a confident hallucination."
- **Why:** This is the differentiator. It converts "we used AI" into "our AI shows its working."
- **Hackathon value:** Explainable AI, demonstrated — not claimed.
- **Judge takeaway:** *Every AI output is verifiable against the source. This is how police AI must behave.*

---

## SCENE 7 · From One Case to a Pattern (similar cases)

- **Objective:** Show one-click MO similarity with per-match reasons.
- **Playwright:** hover "Show similar cases" 0.7 s → `click` → `wait_for_selector('.mo-related li')` → slow scroll 400 px through matches, pausing 1.5 s on the first match's reason text.
- **Expected loading:** <1 s.
- **Duration:** 24 s
- **Voiceover (56 words):**
  > "One click more — and KAVACH finds every case committed the same way. Fifteen matches, and each one states its reason: same offender count, same mobility, same action, same target. Two men, a motorcycle, a gold chain — a pattern an investigator can act on. And the label is deliberate: a potential association, never an assumption of guilt."
- **Why:** Completes the MO arc: extract → verify → generalize.
- **Hackathon value:** Similarity with explanations, not a black-box score.
- **Judge takeaway:** *The AI turns single cases into actionable series.*

---

## SCENE 8 · The Web (Networks)

- **Objective:** One case becomes a graph; edges are records, not inferences.
- **Playwright:** `click('nav >> text=Networks')` → `wait_for_selector('canvas')` → wait for "Loading case overview" hidden → 3 s layout settle → `mouse.wheel(0,-350)` gentle zoom → drag-pan 120 px (40 steps) → cursor circles the accused node 2 s.
- **Expected loading:** 3–6 s — the transition sentence covers it fully.
- **Transition in (spoken):** *"Patterns raise a harder question — who connects these cases?…"*
- **Duration:** 28 s
- **Voiceover (63 words):**
  > "Patterns raise a harder question — who connects these cases? The association graph answers it with records, not speculation. Case seven-two-three-one at the centre; around it the accused, the victim, the station, the offence sections — nine kinds of entities, and every single edge cites the FIR it came from. As the graph loads its neighbours, an investigator can walk outward, link by link."
- **Why:** Graphs are visually strong, and "every edge cites its FIR" extends the provenance story.
- **Hackathon value:** Network analysis grounded in source records.
- **Judge takeaway:** *Even the graph is auditable.*

---

## SCENE 9 · One Person, Many Spellings (Identities)

- **Objective:** Duplicate-person detection with visible evidence, and the leads-not-conclusions doctrine.
- **Playwright:** `click('nav >> text=Identities')` → `wait_for_selector('.accused-row')` → 2 s on ranked list → hover row 1's "Find similar person" 0.7 s → `click` → "searching…" modal (keep on screen ~2 s — narration covers it) → `wait_for_selector('.match-card')` → hover the evidence tags 2.5 s.
- **Expected loading:** search 1–3 s (modal shown — this is honest live computation, narrate it).
- **Duration:** 30 s
- **Voiceover (70 words):**
  > "The same person can appear across FIRs with different spellings, ages, districts. Identities ranks every accused by case count — and for any one of them, runs a live similarity search across the whole state. Watch the evidence on each match: name agreement, same sex, age within a year — and contradictions are shown just as plainly. Every result is a lead for human review. The system never declares two records the same person."
- **Why:** Entity resolution is technically hard; showing *contradictory* evidence is rare honesty.
- **Hackathon value:** Real ER with an ethical posture built into the UI.
- **Judge takeaway:** *The AI assists judgement; it does not replace it.*

---

## SCENE 10 · The System Audits Itself (Anomalies)

- **Objective:** σ-scored anomaly queue, ML corroboration badges, and the LLM explanation reveal.
- **Playwright:** `click('nav >> text=Anomalies')` → `wait_for_selector('h1:text("Anomaly Detection")')` → 1.5 s on the queue → `click` row 1 (expands) → hold 4 s on the explanation text → cursor underlines "explained by GLM-4.7" 2 s → hover a "✓ ML" badge 1.5 s.
- **Expected loading:** instant (warmed).
- **Transition in (spoken):** *"Good intelligence also questions its own data…"*
- **Duration:** 32 s
- **Voiceover (74 words):**
  > "Good intelligence also questions its own data. The anomaly queue ranks twenty-five cases whose details don't fit their station or offence — each with a deviation score in sigma, and a tick where an Isolation Forest model independently agrees with the statistics. Expand one, and the system explains itself in plain English: cyber fraud is unusual at Shivamogga Town because it is rare there — zero point nine percent. Two methods, one explanation, and a direct link to the FIR."
- **Why:** Dual-method corroboration + LLM explanation is the strongest AI moment after MO.
- **Hackathon value:** Statistics, classical ML, and an LLM working together — all visible.
- **Judge takeaway:** *The AI stack is layered, and every layer explains itself.*

---

## SCENE 11 · Looking Forward (Area Risk)

- **Objective:** The forecast: needs-attention headline, the momentum ladder, model provenance.
- **Playwright:** `click('nav >> text=Area Risk')` → `wait_for_selector('h1:text("Area Risk Forecast")')` → 1.5 s on KPIs → slow scroll 250 px to the ladder → hover the Mysuru bar 2.5 s → cursor rests on "Model: quickml:area-risk-forecast:v1" 2 s.
- **Expected loading:** instant (warmed).
- **Duration:** 28 s
- **Voiceover (65 words):**
  > "Everything so far looked at what has happened. Area Risk looks at what comes next: five hundred and thirty-three cases expected statewide in the next thirty days, and one headline — Mysuru, up twenty-two percent, needs attention this month. On the ladder, the bar is the forecast and the marker is today; the gap between them is momentum. The model is named, versioned, and labelled a guide — not a certainty."
- **Why:** Forward-looking closes the intelligence loop; the momentum viz is genuinely clever.
- **Hackathon value:** QuickML forecasting with honest framing.
- **Judge takeaway:** *Prediction with humility — exactly right for policing.*

---

## SCENE 12 · The Close (back to Trends)

- **Objective:** Land the trust argument and the brand.
- **Playwright:** `click('nav >> text=Trends')` → hold the opening frame → cursor drifts once to the banner and stops → end recording 2 s after narration.
- **Duration:** 20 s
- **Voiceover (48 words):**
  > "From a free-text FIR to patterns, networks, identities, anomalies, and a thirty-day forecast — one connected workflow, and every AI answer carrying its method, its model version, and its limitations. Fully deployed on Zoho Catalyst, on synthetic data, ready for the real thing. This is KAVACH AI."
- **Judge takeaway:** *Complete, connected, explainable, deployed. This team deserves to win.*

---

## Full Uninterrupted Voiceover (for TTS — read as one piece, ~700 words ≈ 4:50 with scene pacing)

> Every day, police stations across Karnataka file hundreds of first-information reports. The intelligence inside them is real — but it is locked in free text, spread across tables, and invisible at state scale. KAVACH AI was built to unlock it. Sixteen thousand six hundred and fifty-two synthetic cases, three years of data, running end-to-end on Zoho Catalyst.
>
> The day starts here — the state intelligence overview. This alert is not a notification; it is a statistical finding. Robbery at Peenya police station is running at thirty cases a fortnight against a baseline of four a week — a two-hundred-and-seventy-five percent deviation, eleven standard deviations out, with ten weeks of history right on the card. An officer can acknowledge it, and every number below breaks the state down by district, status, and crime type.
>
> But a number without a place is only half the truth — so the same intelligence lands on the map. These are one hundred and twelve detected hotspots across Karnataka, each with a true radius in metres and its share of night-time crime. Hotspot number one: Jayanagar, two thousand seven hundred and ninety-one cases. The panel is marked AI-derived, and this histogram shows exactly when incidents happen through the day — which is what patrol planning actually needs. Stations with an active alert pulse, live, on this map.
>
> And time is a dimension here, not a dropdown. Press play, and the map animates the last twelve months window by window — clusters growing, shifting, and dissolving as the window narrows to thirty days. Notice the address bar following along: every frame of this animation is itself a shareable link.
>
> Knowing where crime happens is one thing — understanding how it is committed is another. MO Profiles reads every first-information report and extracts the modus operandi: the action, the target, the mobility. I type one word — chain — and the system searches every narrative in the corpus. Sixty-two cases, each already tagged with how the crime was done.
>
> Here is the part that matters. This is the original narrative, and beside it, the extracted profile. When I hover 'action — robbery', watch the narrative: the exact words that produced that value light up. Every single attribute is anchored to evidence in the text. And where the narrative says nothing — the system shows a dash. It does not guess. In an investigation, an honest 'unknown' is worth more than a confident hallucination.
>
> One click more — and KAVACH finds every case committed the same way. Fifteen matches, and each one states its reason: same offender count, same mobility, same action, same target. Two men, a motorcycle, a gold chain — a pattern an investigator can act on. And the label is deliberate: a potential association, never an assumption of guilt.
>
> Patterns raise a harder question — who connects these cases? The association graph answers it with records, not speculation. Case seven-two-three-one at the centre; around it the accused, the victim, the station, the offence sections — nine kinds of entities, and every single edge cites the FIR it came from. As the graph loads its neighbours, an investigator can walk outward, link by link.
>
> The same person can appear across FIRs with different spellings, ages, districts. Identities ranks every accused by case count — and for any one of them, runs a live similarity search across the whole state. Watch the evidence on each match: name agreement, same sex, age within a year — and contradictions are shown just as plainly. Every result is a lead for human review. The system never declares two records the same person.
>
> Good intelligence also questions its own data. The anomaly queue ranks twenty-five cases whose details don't fit their station or offence — each with a deviation score in sigma, and a tick where an Isolation Forest model independently agrees with the statistics. Expand one, and the system explains itself in plain English: cyber fraud is unusual at Shivamogga Town because it is rare there — zero point nine percent. Two methods, one explanation, and a direct link to the FIR.
>
> Everything so far looked at what has happened. Area Risk looks at what comes next: five hundred and thirty-three cases expected statewide in the next thirty days, and one headline — Mysuru, up twenty-two percent, needs attention this month. On the ladder, the bar is the forecast and the marker is today; the gap between them is momentum. The model is named, versioned, and labelled a guide — not a certainty.
>
> From a free-text FIR to patterns, networks, identities, anomalies, and a thirty-day forecast — one connected workflow, and every AI answer carrying its method, its model version, and its limitations. Fully deployed on Zoho Catalyst, on synthetic data, ready for the real thing. This is KAVACH AI.

---

## Production notes

- **Pipeline:** reuse `docs/demo/video-pipeline/` — replace `scenes.json` scene list with the 12 scenes above (`id`, `min_secs` = scene duration, `text` = voiceover). Update `record_demo.py` scene blocks with the Playwright actions listed per scene (all selectors verified live today). Audio-first sync keeps narration and screen locked.
- **New actions vs. the previous recording:** Overview alert hover + KPI scroll, hotspot detail-panel open (`click` sidebar row `#1`), time-lapse `▶`, anomaly row expansion (`click` first queue row), Area Risk ladder scroll+hover. All verified clickable in this investigation.
- **Numbers used in narration were read off the live app today** (16,652 cases · 112 hotspots · Jayanagar 2,791 · 25 anomalies · 533 forecast · Mysuru +22% · Peenya ▲275% z 11 · 62 "chain" results ⇐ verify this last one at record time; if the count differs, say "dozens of cases" instead).
- If any live number drifts before recording day, re-check Scene 1/3/10/11 lines against the app — the pipeline makes regeneration a 6-minute operation.
