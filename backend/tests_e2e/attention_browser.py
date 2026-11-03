"""Visual-attention percentage, end to end in a real browser (headless Chromium, fake camera + fake microphone).

REAL: the app and backend, MediaPipe face analysis in the browser, the attention meter, the live card, the upload of
cumulative totals, the stored report. SIMULATED: the person - the fake camera plays the app's own synthetic 3D
interviewer (not a real person) facing the camera, with the head turned 45 degrees, and an empty room.
This is NOT a test with a human face, glasses, real lighting or a real webcam.

Fake camera timeline (seconds after the camera opens, loops): 0-25 facing | 25-40 head turned | 40-60 facing |
60-70 nobody in view | 70-90 facing.

Checks, independent of the meter: while polling the page every 0.5 s the test counts for itself what the monitor saw
(dev hook window.__hsMonitor) and compares it with the percentage the server stored. Then reloads the page (a second
monitor run) and checks the totals add up instead of restarting.

Run (own servers so the shared :8000/:5173 are not touched):
    set HS_API=http://127.0.0.1:8001 ; start backend: uvicorn app.main:app --port 8001 ; vite --port 5174
    HS_E2E_BASE=http://localhost:5174 .\\venv\\Scripts\\python.exe tests_e2e\\attention_browser.py
"""
import io
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
MIC = OUT / "candidate_answer.wav"
BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5173")
STUDENT = {"email": "student@demo.hiresense", "password": "Demo@12345"}
W, H, FPS = 320, 240, 5
TIMELINE = [(25, "front"), (15, "turned"), (20, "front"), (10, "empty"), (20, "front")]
if not MIC.exists():
    sys.exit("Run tests_e2e/voice_interview_browser.py once first: it creates output/candidate_answer.wav")
results = {"checks": []}


def say(*a):
    print(*a, flush=True)


def ok(name, cond, detail=""):
    results["checks"].append({"check": name, "ok": bool(cond), "detail": detail})
    say(("[ok]   " if cond else "[FAIL] ") + name + (f" - {detail}" if detail else ""))


LOGIN = """async (c) => { const r = await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'},
  body: JSON.stringify(c)}); if (!r.ok) throw new Error('login ' + r.status); }"""
FETCH = """async ([url, method, body]) => { const r = await fetch('/api' + url, {method, headers: {'Content-Type': 'application/json'},
  body: body ? JSON.stringify(body) : undefined}); const t = await r.text(); return {status: r.status, body: t ? JSON.parse(t) : null}; }"""


def api(page, url, method="GET", body=None):
    return page.evaluate(FETCH, [url, method, body])


def render_heads(p) -> dict:
    b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
    page = b.new_context(viewport={"width": 1366, "height": 900}).new_page()
    page.goto(BASE + "/login")
    page.evaluate(LOGIN, STUDENT)
    sid = api(page, "/student/interviews", "POST", {"job_role": "Backend Developer", "category": "hr", "mode": "voice",
                                                   "question_count": 3, "defer_first_question": True})["body"]["session"]["id"]
    heads = {}
    try:
        page.goto(f"{BASE}/student/interviews/{sid}/live")
        page.wait_for_function("window.__avatar3d && window.__avatar3d.status === 'ready'", timeout=120000)
        box = page.locator("[data-avatar-status]").bounding_box()
        for name, yaw in (("front", 0), ("turned", 45)):
            page.evaluate(f"window.__avatar3d.orbit({yaw} * Math.PI / 180, 0.33, 1.0)")
            page.wait_for_timeout(800)
            im = Image.open(io.BytesIO(page.screenshot(clip=box, animations="allow"))).convert("RGB")
            w, h = im.size
            cw = min(w, int(h * 4 / 3))
            heads[name] = im.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h)).resize((W, H))
    finally:
        api(page, f"/student/interviews/{sid}", "DELETE")
        b.close()
    rng = np.random.default_rng(1)
    room = (np.linspace(70, 150, W)[None, :, None] + rng.normal(0, 18, (H, W, 1))).clip(0, 255)
    heads["empty"] = Image.fromarray(np.repeat(room, 3, axis=2).astype(np.uint8))
    return heads


def make_video(frames: dict) -> str:
    path = Path(tempfile.gettempdir()) / "hs_attention_check.y4m"
    with open(path, "wb") as f:
        f.write(f"YUV4MPEG2 W{W} H{H} F{FPS}:1 Ip A1:1 C420jpeg\n".encode())
        for secs, name in TIMELINE:
            a = np.asarray(frames[name], np.float32)
            r, g, b = a[..., 0], a[..., 1], a[..., 2]
            y = 0.257 * r + 0.504 * g + 0.098 * b + 16
            u = -0.148 * r - 0.291 * g + 0.439 * b + 128
            v = 0.439 * r - 0.368 * g - 0.071 * b + 128
            sub = lambda c: c.reshape(H // 2, 2, W // 2, 2).mean(axis=(1, 3))  # noqa: E731
            frame = b"".join(np.clip(x, 0, 255).astype(np.uint8).tobytes() for x in (y, sub(u), sub(v)))
            for _ in range(secs * FPS):
                f.write(b"FRAME\n" + frame)
    return str(path)


def setup_and_start(page):
    page.get_by_text("Camera and interview monitoring").wait_for(timeout=90000)
    box = page.get_by_label(re.compile("Approximate head direction and gaze"))
    if box.count() and not box.is_checked():
        box.check()
    page.get_by_role("button", name=re.compile("Test my camera")).click()
    page.get_by_text("Your face is visible and the lighting looks fine").wait_for(timeout=30000)
    page.get_by_role("button", name="Calibrate now").click()
    page.get_by_text("Your normal viewing position was measured").wait_for(timeout=20000)
    page.get_by_label("I have read what is monitored").check()
    page.get_by_role("button", name=re.compile("start the interview")).click()
    return time.time()


def report(page, sid):
    return api(page, f"/student/interviews/{sid}/integrity-events")["body"]["attention"]


with sync_playwright() as p:
    say("rendering head frames from the 3D model...")
    video = make_video(render_heads(p))
    browser = p.chromium.launch(headless=True, args=[
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
        f"--use-file-for-fake-video-capture={video}", f"--use-file-for-fake-audio-capture={MIC}",
        "--autoplay-policy=no-user-gesture-required", "--disable-webgl", "--disable-3d-apis"])
    page = browser.new_context(viewport={"width": 1366, "height": 1000}).new_page()
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text[:200]))
    page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)[:200]))
    page.goto(BASE + "/login")
    page.evaluate(LOGIN, STUDENT)
    for s in (api(page, "/student/interviews?status=in_progress&page_size=50")["body"] or {}).get("items", []):
        api(page, f"/student/interviews/{s['id']}", "DELETE")
    sid = api(page, "/student/interviews", "POST", {"job_role": "Backend Developer", "category": "technical", "mode": "voice",
                                                   "question_count": 3, "defer_first_question": True})["body"]["session"]["id"]
    say("interview", sid)
    page.goto(f"{BASE}/student/interviews/{sid}/live")
    t0 = setup_and_start(page)

    # ---- independent observer: what the monitor saw, polled every 0.5 s, plus what the live card showed
    seen = {"toward": 0.0, "away": 0.0, "other": 0.0}
    live, card_texts = [], set()
    last = time.time()
    while time.time() - t0 < 95:
        now = time.time()
        m = page.evaluate("window.__hsMonitor || null")
        card = page.locator('[aria-label="Visual attention"]')
        text = card.inner_text() if card.count() else ""
        pct = re.search(r"(\d+)%\s*\n", text)
        live.append({"t": round(now - t0, 1), "pct": int(pct.group(1)) if pct and "unavailable" not in text else None,
                     "unavailable": "temporarily unavailable" in text, "tracking": (re.search(r"Tracking: (.*)", text) or [None, ""])[1][:45]})
        card_texts.add(re.sub(r"\s+", " ", text)[:240])
        if pct and "card_shot" not in results and now - t0 > 40:  # the card with a number (head turned)
            page.evaluate("window.scrollTo(0, 0)")  # keep the sticky page header off the card
            card.screenshot(path=OUT / "attention_card.png")
            results["card_shot"] = True
        if "Face not detected" in text and "card_shot2" not in results:
            page.evaluate("window.scrollTo(0, 0)")
            card.screenshot(path=OUT / "attention_card_unavailable.png")
            results["card_shot2"] = True
        if m and m["gaze"] in ("active", "uncalibrated"):
            dt = now - last
            if m["faces"] == 1 and not m["obs"].get("low_light") and not m["edge"]:
                seen["away" if m["away"] else "toward"] += dt
            else:
                seen["other"] += dt
        last = now
        page.wait_for_timeout(500)
    page.screenshot(path=OUT / "attention_live.png")
    time.sleep(11)  # the browser uploads totals every 10 s
    a = report(page, sid)
    results["report_run1"] = a
    say(json.dumps({k: a.get(k) for k in ("overall_attention_pct", "coverage_pct", "looking_toward_ms", "looking_away_ms",
                                         "unobserved_ms", "unobserved_by_reason", "prolonged_deviation_events")}))
    say("independent observer (s):", {k: round(v, 1) for k, v in seen.items()})

    ok("report exists and is labelled as an estimate", a and a["available"] and a["label"].startswith("Estimated visual attention"))
    valid_obs = (seen["toward"] + seen["away"])
    pct_obs = 100 * seen["toward"] / valid_obs if valid_obs else None
    ok("stored percentage within 12 points of the independent count", pct_obs is not None and abs(a["overall_attention_pct"] - pct_obs) <= 12,
       f"stored {a['overall_attention_pct']}%, observer {pct_obs and round(pct_obs)}%")
    ok("looking-away time is about the 15 s the head was turned", 9000 <= a["looking_away_ms"] <= 21000, f"{a['looking_away_ms']} ms")
    ok("empty room (10 s) was NOT counted as attention or as looking away", 6000 <= a["unobserved_ms"] <= 20000
       and a["unobserved_by_reason"]["face_not_visible"] >= 6000, str(a["unobserved_by_reason"]))
    ok("prolonged deviation recorded once", a["prolonged_deviation_events"] == 1, str(a["prolonged_deviation_events"]))
    ok("coverage is below 100% because of the empty room", a["coverage_pct"] is not None and 70 <= a["coverage_pct"] < 100, str(a["coverage_pct"]))
    pcts = [x["pct"] for x in live if x["pct"] is not None]
    ok("live percentage was shown", len(pcts) > 20, f"{len(pcts)} readings")
    ok("live percentage dropped while the head was turned", pcts and min(pcts) < 80, f"min {min(pcts) if pcts else None}")
    # wherever the card itself said "Face not detected", the percentage must be unavailable after ~1.5 s (no stale value)
    run_start, stale = None, []
    for x in live:
        if x["tracking"].startswith("Face not detected"):
            run_start = x["t"] if run_start is None else run_start
            if x["t"] - run_start > 1.5 and x["pct"] is not None:
                stale.append(x)
        else:
            run_start = None
    lost = [x for x in live if x["tracking"].startswith("Face not detected")]
    ok("while no face was in view the card showed 'Face not detected' and 'estimate unavailable', not a stale value",
       len(lost) >= 8 and not stale and any(x["unavailable"] for x in lost), f"{len(lost)} readings, {len(stale)} stale")
    ok("no live reading of exactly 0% from a missing camera", 0 not in pcts)
    results["live"] = live

    # ---- page reload = a second monitor run; totals must add up, not restart
    before = a["valid_observation_ms"]
    page.reload()
    setup_and_start(page)
    page.wait_for_timeout(25000)
    page.wait_for_function("window.__hsMonitor && window.__hsMonitor.gaze === 'active'", timeout=30000)
    page.wait_for_timeout(12000)
    b = report(page, sid)
    ok("after a reload the totals kept the first run and added the second", b["monitor_runs"] == 2 and b["valid_observation_ms"] > before,
       f"runs {b['monitor_runs']}, valid {before} -> {b['valid_observation_ms']}")

    # ---- another candidate must not read this report
    r = api(page, f"/monitoring/sessions/{sid}")
    ok("a student cannot open the reviewer report", r["status"] in (403, 404), str(r["status"]))
    api(page, f"/student/interviews/{sid}", "DELETE")
    # known, harmless in this setup: the login page's own 401 probe before signing in, and the 3D avatar's WebGL context,
    # which this test switches off on purpose (--disable-webgl) so only the 2D camera path is exercised
    # (also: MediaPipe's INFO line arrives on the console error channel, and the 403 is the access-denied check above)
    real = [e for e in errors if not any(k in e for k in ("401 (Unauthorized)", "WebGLRenderer", "INFO: ", "403 (Forbidden)"))]
    ok("no unexpected console errors in the browser", not real, "; ".join(real[:3]))
    browser.close()

(OUT / "attention_browser.json").write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
failed = [c for c in results["checks"] if not c["ok"]]
say(f"\n{len(results['checks']) - len(failed)}/{len(results['checks'])} checks passed")
sys.exit(1 if failed else 0)
