#!/usr/bin/env python3
"""Record the KAVACH cinematic demo (12 scenes) with Playwright.

Audio-first sync: each scene holds until its narration (durations.json) would
finish; actual scene start times are logged for the assembler.
"""
import json
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
BASE = "https://kavach.development.catalystappsail.in"
START_URL = f"{BASE}/#view=overview"
W, H = 1920, 1080

cfg = json.loads((HERE / "scenes.json").read_text())
durations = json.loads((HERE / "durations.json").read_text())
HOLD = {s["id"]: max(s["min_secs"], durations[s["id"]] + 0.5) for s in cfg["scenes"]}


def wait_mo_ready(timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/api/v1/mo/status", timeout=90) as r:
                body = json.loads(r.read())
                print("  mo/status:", body.get("status"), flush=True)
                if body.get("ready"):
                    return True
        except Exception as exc:  # noqa: BLE001
            print("  mo/status error:", exc, flush=True)
        time.sleep(3)
    return False


def smooth_move(page, x1, y1, x2, y2, steps=50, pause=0.0):
    page.mouse.move(x1, y1)
    page.mouse.move(x2, y2, steps=steps)
    if pause:
        time.sleep(pause)


def slow_scroll(page, total=900, step=150, delay=0.3):
    scrolled = 0
    while scrolled < total:
        page.mouse.wheel(0, step)
        scrolled += step
        time.sleep(delay)


def nav_click(page, label):
    page.locator("nav").get_by_text(label, exact=False).first.click()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ---- warm-up (not recorded) ---------------------------------------
        print("warm-up: MO index…", flush=True)
        wait_mo_ready()
        warm = browser.new_context(viewport={"width": W, "height": H})
        wpage = warm.new_page()
        wpage.goto(f"{BASE}/#view=overview", wait_until="networkidle", timeout=120000)
        for label, probe in [
            ("Geospatial Ops", "canvas"),
            ("MO Profiles", ".id-search input"),
            ("Networks", "canvas"),
            ("Identities", ".accused-row"),
            ("Anomalies", "h1"),
            ("Area Risk", "h1"),
        ]:
            try:
                nav_click(wpage, label)
                wpage.wait_for_selector(probe, timeout=120000)
                if label == "Networks":
                    wpage.wait_for_selector(
                        "text=Loading case overview", state="hidden", timeout=120000
                    )
                time.sleep(1.0)
                print(f"  warmed {label}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  WARN warm {label}: {exc}", flush=True)
        warm.close()

        # ---- recorded pass -------------------------------------------------
        print("recording…", flush=True)
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(HERE / "video"),
            record_video_size={"width": W, "height": H},
        )
        page = ctx.new_page()
        t0 = time.monotonic()
        times = {"scenes": []}

        def begin(scene_id):
            start = time.monotonic() - t0
            times["scenes"].append({"id": scene_id, "start": round(start, 3)})
            print(f"  scene {scene_id} @ {start:6.2f}s (hold {HOLD[scene_id]:.1f}s)", flush=True)
            return time.monotonic()

        def hold_until(scene_start, scene_id):
            remaining = HOLD[scene_id] - (time.monotonic() - scene_start)
            if remaining > 0:
                time.sleep(remaining)

        def safely(fn, what):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                print(f"  WARN {what}: {exc}", flush=True)

        # SCENE 1 — the problem (Trends cold open)
        page.goto(START_URL, timeout=120000)
        page.wait_for_selector('h2:has-text("State Intelligence Overview")', timeout=120000)
        time.sleep(1.2)
        times["trim"] = round(time.monotonic() - t0 - 0.6, 3)
        s = begin("01_problem")
        smooth_move(page, 960, 600, 640, 24, steps=60, pause=2.0)
        smooth_move(page, 640, 24, 1500, 24, steps=50, pause=1.5)
        smooth_move(page, 1500, 24, 1700, 16, steps=30, pause=1.0)  # rest on case count
        hold_until(s, "01_problem")

        # SCENE 2 — the briefing (alert anatomy + scroll)
        s = begin("02_briefing")
        safely(lambda: page.locator("[class*=alert]").first.hover(), "alert hover")
        time.sleep(3.5)
        slow_scroll(page, total=900, step=150, delay=0.35)
        time.sleep(1.0)
        slow_scroll(page, total=700, step=150, delay=0.35)
        hold_until(s, "02_briefing")

        # SCENE 3 — the map + hotspot detail
        nav_click(page, "Geospatial Ops")
        page.wait_for_selector("canvas", timeout=120000)
        time.sleep(2.5)
        s = begin("03_map")
        safely(lambda: page.locator('button:has-text("#1")').first.click(), "hotspot #1 click")
        time.sleep(2.0)
        smooth_move(page, 1700, 350, 1700, 340, steps=10, pause=2.0)  # rest on histogram area
        smooth_move(page, 1700, 340, 900, 500, steps=60, pause=1.5)  # sweep the map
        smooth_move(page, 900, 500, 170, 250, steps=50, pause=2.0)  # toward filters
        hold_until(s, "03_map")

        # SCENE 4 — time-lapse
        s = begin("04_timelapse")
        safely(
            lambda: page.evaluate(
                "() => { const b=[...document.querySelectorAll('button')]"
                ".find(x=>x.textContent.trim()==='▶'); "
                "if (!b) throw new Error('play button not found'); b.click(); }"
            ),
            "timelapse play",
        )
        time.sleep(12.0)  # let the animation run
        smooth_move(page, 960, 1000, 1400, 1020, steps=40, pause=1.5)
        hold_until(s, "04_timelapse")

        # SCENE 5 — MO search + filters
        nav_click(page, "MO Profiles")
        page.wait_for_selector(".id-search input", timeout=120000)
        time.sleep(0.8)
        s = begin("05_mo_search")
        page.click(".id-search input")
        page.type(".id-search input", "chain", delay=120)
        time.sleep(0.4)
        page.click('.id-search button:has-text("Search")')
        page.wait_for_selector(".mo-row", timeout=60000)
        time.sleep(2.0)
        slow_scroll(page, total=300, step=150, delay=0.35)
        safely(lambda: page.locator(".mo-filter-row select").first.hover(), "filter hover")
        time.sleep(2.0)
        hold_until(s, "05_mo_search")

        # SCENE 6 — MO evidence highlighting
        page.locator(".mo-row").first.click()
        page.wait_for_selector(".mo-narrative", timeout=60000)
        time.sleep(1.5)
        s = begin("06_mo_evidence")
        attrs = page.locator(".mo-attr")
        safely(lambda: attrs.nth(0).hover(), "attr0")
        time.sleep(3.5)
        safely(lambda: attrs.nth(1).hover(), "attr1")
        time.sleep(3.0)
        safely(lambda: attrs.nth(2).hover(), "attr2")
        time.sleep(2.5)
        safely(lambda: page.locator(".mo-attr.unknown").first.hover(), "unknown attr")
        time.sleep(2.0)
        hold_until(s, "06_mo_evidence")

        # SCENE 7 — similar cases
        s = begin("07_similar")
        page.click('button:has-text("Show similar cases")')
        page.wait_for_selector(".mo-related li", timeout=60000)
        time.sleep(1.5)
        slow_scroll(page, total=450, step=150, delay=0.4)
        hold_until(s, "07_similar")

        # SCENE 8 — networks (rich: node click + results panel)
        nav_click(page, "Networks")
        page.wait_for_selector("canvas", timeout=120000)
        safely(
            lambda: page.wait_for_selector(
                "text=Loading case overview", state="hidden", timeout=120000
            ),
            "graph load",
        )
        time.sleep(3.5)
        s = begin("08_networks")
        page.mouse.move(960, 540)
        page.mouse.wheel(0, -350)  # zoom in
        time.sleep(1.5)
        page.mouse.down()
        page.mouse.move(1080, 500, steps=40)
        page.mouse.up()
        time.sleep(1.5)
        # attempt a node click near centre (seed node) to open the detail panel
        safely(lambda: page.mouse.click(1000, 520), "node click")
        time.sleep(2.5)
        smooth_move(page, 1000, 520, 1650, 400, steps=50, pause=2.0)  # toward right panel
        smooth_move(page, 1650, 400, 900, 600, steps=50, pause=1.5)
        hold_until(s, "08_networks")

        # SCENE 9 — identities
        nav_click(page, "Identities")
        page.wait_for_selector(".accused-row", timeout=120000)
        time.sleep(2.0)
        s = begin("09_identities")
        safely(lambda: page.locator(".find-similar-btn").first.click(), "find similar")
        safely(lambda: page.wait_for_selector(".match-card", timeout=90000), "match cards")
        time.sleep(1.5)
        safely(lambda: page.locator(".match-card [class*=tag]").first.hover(), "tag hover")
        time.sleep(2.0)
        hold_until(s, "09_identities")

        # SCENE 10 — anomalies + LLM explanation
        nav_click(page, "Anomalies")
        page.wait_for_selector('h1:has-text("Anomaly Detection")', timeout=120000)
        time.sleep(1.5)
        s = begin("10_anomalies")
        time.sleep(2.0)
        safely(
            lambda: page.locator('text=Out-of-place crime type').first.click(),
            "anomaly expand",
        )
        time.sleep(4.0)
        safely(lambda: page.locator("text=explained by").first.hover(), "explained-by hover")
        time.sleep(2.0)
        safely(lambda: page.locator("text=ML").first.hover(), "ml badge hover")
        time.sleep(1.5)
        hold_until(s, "10_anomalies")

        # SCENE 11 — area risk ladder
        nav_click(page, "Area Risk")
        page.wait_for_selector('h1:has-text("Area Risk Forecast")', timeout=120000)
        time.sleep(1.5)
        s = begin("11_risk")
        time.sleep(2.0)
        slow_scroll(page, total=300, step=150, delay=0.4)
        safely(lambda: page.locator("text=Mysuru").first.hover(), "mysuru hover")
        time.sleep(2.5)
        safely(lambda: page.locator("text=Bengaluru City").first.hover(), "blr hover")
        time.sleep(2.0)
        safely(lambda: page.locator("text=Model:").first.hover(), "model hover")
        time.sleep(2.0)
        hold_until(s, "11_risk")

        # SCENE 12 — close
        nav_click(page, "Trends")
        page.wait_for_selector('h2:has-text("State Intelligence Overview")', timeout=120000)
        s = begin("12_close")
        smooth_move(page, 960, 500, 640, 24, steps=60, pause=2.0)
        hold_until(s, "12_close")
        time.sleep(2.0)

        times["end"] = round(time.monotonic() - t0, 3)
        video_path = page.video.path()
        ctx.close()
        browser.close()

    (HERE / "scene_times.json").write_text(json.dumps(times, indent=2))
    print("\nvideo:", video_path, flush=True)
    print(json.dumps(times, indent=2), flush=True)


if __name__ == "__main__":
    main()
