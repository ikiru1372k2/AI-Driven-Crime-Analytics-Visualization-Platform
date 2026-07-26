#!/usr/bin/env python3
"""Record the KAVACH demo video with Playwright.

Audio-first sync: each scene holds on screen until its narration (measured in
durations.json) would finish, and actual scene start times are logged so the
assembler can place each MP3 exactly where its scene begins.
"""
import json
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
BASE = "https://kavach.development.catalystappsail.in"
START_URL = f"{BASE}/#view=overview&district=44&hotspot=1&seed=CASE%3A7231"
W, H = 1920, 1080

cfg = json.loads((HERE / "scenes.json").read_text())
durations = json.loads((HERE / "durations.json").read_text())
HOLD = {s["id"]: max(s["min_secs"], durations[s["id"]] + 0.5) for s in cfg["scenes"]}


def wait_mo_ready(timeout=300):
    """Poll the readiness endpoint until the MO index is built server-side."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/api/v1/mo/status", timeout=90) as r:
                body = json.loads(r.read())
                print("  mo/status:", body.get("status"))
                if body.get("ready"):
                    return True
        except Exception as exc:  # noqa: BLE001
            print("  mo/status error:", exc)
        time.sleep(3)
    return False


def smooth_move(page, x1, y1, x2, y2, steps=40, pause=0.0):
    page.mouse.move(x1, y1)
    page.mouse.move(x2, y2, steps=steps)
    if pause:
        time.sleep(pause)


def slow_scroll(page, total=1200, step=150, delay=0.25):
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

        # ---- warm-up pass (NOT recorded) -----------------------------------
        print("warm-up: MO index…")
        wait_mo_ready()
        warm = browser.new_context(viewport={"width": W, "height": H})
        wpage = warm.new_page()
        print("warm-up: visiting tabs…")
        wpage.goto(START_URL, wait_until="networkidle", timeout=120000)
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
                if label == "Networks":  # wait out the async case-overview load
                    wpage.wait_for_selector(
                        "text=Loading case overview", state="hidden", timeout=120000
                    )
                time.sleep(1.0)
                print(f"  warmed {label}")
            except Exception as exc:  # noqa: BLE001
                print(f"  WARN warm {label}: {exc}")
        warm.close()

        # ---- recorded pass --------------------------------------------------
        print("recording…")
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
            print(f"  scene {scene_id} @ {start:6.2f}s (hold {HOLD[scene_id]:.1f}s)")
            return time.monotonic()

        def hold_until(scene_start, scene_id):
            remaining = HOLD[scene_id] - (time.monotonic() - scene_start)
            if remaining > 0:
                time.sleep(remaining)

        # SCENE 1 — cold open on Trends
        page.goto(START_URL, timeout=120000)
        page.wait_for_selector('h2:has-text("State Intelligence Overview")', timeout=120000)
        time.sleep(1.0)  # let charts paint
        times["trim"] = round(time.monotonic() - t0 - 0.6, 3)  # cut the blank lead-in
        s = begin("01_cold_open")
        smooth_move(page, 960, 500, 640, 24, steps=60, pause=2.0)  # drift to banner
        smooth_move(page, 640, 24, 1500, 24, steps=50, pause=1.5)  # along the banner
        hold_until(s, "01_cold_open")

        # SCENE 2 — trends briefing
        s = begin("02_trends")
        slow_scroll(page, total=900, step=150, delay=0.3)
        time.sleep(1.0)
        slow_scroll(page, total=600, step=150, delay=0.3)
        hold_until(s, "02_trends")

        # SCENE 3 — geospatial ops
        nav_click(page, "Geospatial Ops")
        page.wait_for_selector("canvas", timeout=120000)
        time.sleep(2.5)  # tiles settle
        s = begin("03_geospatial")
        smooth_move(page, 400, 500, 1200, 450, steps=70, pause=1.5)  # sweep the map
        smooth_move(page, 1200, 450, 900, 700, steps=60, pause=1.5)
        smooth_move(page, 900, 700, 200, 400, steps=60, pause=1.0)  # toward sidebar
        hold_until(s, "03_geospatial")

        # SCENE 4 — MO profiles (hero)
        nav_click(page, "MO Profiles")
        page.wait_for_selector(".id-search input", timeout=120000)
        time.sleep(0.8)
        s = begin("04_mo_hero")
        page.click(".id-search input")
        page.type(".id-search input", "chain", delay=110)
        time.sleep(0.4)
        page.click('.id-search button:has-text("Search")')
        page.wait_for_selector(".mo-row", timeout=60000)
        time.sleep(2.0)
        page.locator(".mo-row").first.click()
        page.wait_for_selector(".mo-narrative", timeout=60000)
        time.sleep(1.5)
        attrs = page.locator(".mo-attr")
        attrs.nth(0).hover()  # Action — highlight in narrative
        time.sleep(3.0)
        attrs.nth(1).hover()  # Target
        time.sleep(2.5)
        attrs.nth(2).hover()  # Mobility
        time.sleep(2.0)
        page.click('button:has-text("Show similar cases")')
        page.wait_for_selector(".mo-related li", timeout=60000)
        time.sleep(1.0)
        slow_scroll(page, total=450, step=150, delay=0.35)
        hold_until(s, "04_mo_hero")

        # SCENE 5 — networks
        nav_click(page, "Networks")
        page.wait_for_selector("canvas", timeout=120000)
        try:  # the seed case overview loads async — don't start on a spinner
            page.wait_for_selector(
                "text=Loading case overview", state="hidden", timeout=120000
            )
        except Exception as exc:  # noqa: BLE001
            print("  WARN graph load:", exc)
        time.sleep(3.5)  # graph layout settles
        s = begin("05_networks")
        page.mouse.move(960, 540)
        page.mouse.wheel(0, -400)  # zoom in a touch
        time.sleep(1.5)
        page.mouse.down()
        page.mouse.move(1100, 480, steps=40)  # gentle pan
        page.mouse.up()
        time.sleep(1.5)
        smooth_move(page, 1100, 480, 760, 600, steps=50, pause=1.5)
        hold_until(s, "05_networks")

        # SCENE 6 — identities
        nav_click(page, "Identities")
        page.wait_for_selector(".accused-row", timeout=120000)
        time.sleep(2.0)
        s = begin("06_identities")
        try:
            page.locator(".find-similar-btn").first.click()
            page.wait_for_selector(".match-card", timeout=90000)
            time.sleep(1.0)
            page.locator(".match-card .tag").first.hover(timeout=5000)
        except Exception as exc:  # noqa: BLE001
            print("  WARN identities:", exc)
        hold_until(s, "06_identities")

        # SCENE 7 — anomalies → area risk
        nav_click(page, "Anomalies")
        page.wait_for_selector('h1:has-text("Anomaly Detection")', timeout=120000)
        s = begin("07_anomalies_risk")
        time.sleep(HOLD["07_anomalies_risk"] / 2)
        nav_click(page, "Area Risk")
        page.wait_for_selector('h1:has-text("Area Risk Forecast")', timeout=120000)
        hold_until(s, "07_anomalies_risk")

        # SCENE 8 — close on Trends
        nav_click(page, "Trends")
        page.wait_for_selector('h2:has-text("State Intelligence Overview")', timeout=120000)
        s = begin("08_close")
        hold_until(s, "08_close")
        time.sleep(2.0)  # tail

        times["end"] = round(time.monotonic() - t0, 3)
        video_path = page.video.path()
        ctx.close()  # flushes the video file
        browser.close()

    (HERE / "scene_times.json").write_text(json.dumps(times, indent=2))
    print("\nvideo:", video_path)
    print("times:", json.dumps(times, indent=2))


if __name__ == "__main__":
    main()
