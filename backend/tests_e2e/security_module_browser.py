"""Interview security module, end to end in a real browser (headless Chromium, fake camera + fake microphone).

What is REAL here: the app, the backend, MediaPipe face analysis in the browser, the AI interviewer (Ollama + TTS),
the event pipeline and database. What is SIMULATED: the person. The fake camera plays a video built from the app's
own synthetic 3D interviewer (Rocketbox model, not a real person) rendered facing the camera and with the head
turned 45 degrees, an empty room, and two faces; the fake microphone plays output/candidate_answer.wav.

Timeline of the fake camera (seconds after the camera opens, loops):
  0-22 facing the screen | 22-34 head turned 45 deg | 34-40 facing | 40-50 nobody | 50-56 facing
  56-66 two faces | 66-90 facing
Then: a tab switch (another tab in front for ~6 s), 8 s offline, a page reload (reconnect), a typed answer, finish.
Checks the events stored in the database, the student's view, and the recruiter's security report + review.

Needs backend + frontend running, Ollama, and the demo accounts. From the backend folder:
    .\\venv\\Scripts\\python.exe tests_e2e\\security_module_browser.py
Leaves one completed demo interview, a closed "[E2E] Security module check" job and a withdrawn application.
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
RECRUITER = {"email": "recruiter@demo.hiresense", "password": "Demo@12345"}
W, H, FPS = 320, 240, 5
TIMELINE = [(22, "front"), (12, "turned"), (6, "front"), (10, "empty"), (6, "front"), (10, "two"), (24, "front")]
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


# --------------------------------------------------------------------------- 1. frames from the 3D model
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
            page.evaluate(f"window.__avatar3d.orbit({yaw} * Math.PI / 180, 0.33, 1.0)")  # whole face inside the frame
            page.wait_for_timeout(800)
            im = Image.open(io.BytesIO(page.screenshot(clip=box, animations="allow"))).convert("RGB")
            w, h = im.size
            cw = min(w, int(h * 4 / 3))
            heads[name] = im.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h)).resize((W, H))
            heads[name].save(OUT / f"sec_head_{name}.png")
    finally:
        api(page, f"/student/interviews/{sid}", "DELETE")
        b.close()
    rng = np.random.default_rng(1)
    room = (np.linspace(70, 150, W)[None, :, None] + rng.normal(0, 18, (H, W, 1))).clip(0, 255)
    room = np.repeat(room, 3, axis=2).astype(np.uint8)  # an empty, evenly lit room (not "blocked" or "dark")
    heads["empty"] = Image.fromarray(room)
    two = heads["empty"].copy()
    small = heads["front"].resize((180, 135))
    two.paste(small, (-20, 55))
    two.paste(small, (160, 55))
    heads["two"] = two
    two.save(OUT / "sec_head_two.png")
    return heads


def make_video(frames: dict) -> str:
    path = Path(tempfile.gettempdir()) / "hs_security_check.y4m"
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


def text(page) -> str:
    return page.inner_text("body")


def setup_and_start(page, calibrate=True):
    page.get_by_text("Camera and interview monitoring").wait_for(timeout=90000)
    for label in ("Approximate head direction and gaze", "Possible additional voice", "Browser focus changes"):
        box = page.get_by_label(re.compile(label))
        if box.count() and not box.is_checked():
            box.check()
    page.get_by_role("button", name=re.compile("Test my camera")).click()
    t_cam = time.time()
    page.get_by_text("Your face is visible and the lighting looks fine").wait_for(timeout=30000)
    if calibrate:
        page.get_by_role("button", name="Calibrate now").click()
        page.get_by_text("Your normal viewing position was measured").wait_for(timeout=20000)  # not "clearly turned"
    page.screenshot(path=OUT / "sec_1_setup.png", full_page=True)
    page.get_by_label("I have read what is monitored").check()
    page.get_by_role("button", name=re.compile("start the interview")).click()
    return t_cam


with sync_playwright() as p:
    say("rendering head frames from the 3D model…")
    video = make_video(render_heads(p))
    browser = p.chromium.launch(headless=True, args=[
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
        f"--use-file-for-fake-video-capture={video}", f"--use-file-for-fake-audio-capture={MIC}",
        "--autoplay-policy=no-user-gesture-required", "--disable-webgl", "--disable-3d-apis"])
    ctx = browser.new_context(viewport={"width": 1366, "height": 1000})
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text[:200]))
    rctx = browser.new_context(viewport={"width": 1366, "height": 1000})
    rec = rctx.new_page()

    # recruiter job + application, so the recruiter may see the report afterwards
    page.goto(BASE + "/login")
    page.evaluate(LOGIN, STUDENT)
    rec.goto(BASE + "/login")
    rec.evaluate(LOGIN, RECRUITER)
    job = api(rec, "/recruiter/jobs", "POST", {"title": "[E2E] Security module check", "description": "Automated browser test job.",
                                               "location": "Remote", "required_skills": ["Python"], "status": "published"})
    ok("recruiter job created", job["status"] in (200, 201), str(job["status"]))
    job_id = job["body"]["id"]
    appl = api(page, f"/student/jobs/{job_id}/apply", "POST", {})
    ok("student applied", appl["status"] in (200, 201), str(appl["status"]))
    for s in (api(page, "/student/interviews?status=in_progress&page_size=50")["body"] or {}).get("items", []):
        api(page, f"/student/interviews/{s['id']}", "DELETE")
    sid = api(page, "/student/interviews", "POST", {"job_role": "Backend Developer", "category": "technical", "mode": "voice",
                                                   "question_count": 3, "defer_first_question": True})["body"]["session"]["id"]
    say("interview", sid)
    page.goto(f"{BASE}/student/interviews/{sid}/live")
    t_cam = setup_and_start(page)
    seen = {}
    samples = []
    deadline = t_cam + 92
    while time.time() < deadline:
        body = text(page)
        m = page.evaluate("window.__hsMonitor || null")  # dev-only test hook: what the monitor sees right now
        if m:
            samples.append({"t": round(time.time() - t_cam, 1), "faces": m["faces"], "yaw": m["yaw"] and round(m["yaw"]),
                            "base": m["baseline"] and round(m["baseline"]["yaw"]), "gaze": m["gaze"], "away": m["away"],
                            "light": m["light"] and round(m["light"]["mean"]), "judged": m["obs"]["attention_away"], "fps": m["fps"]})
        for key, phrase in (("gaze_warning", "Please keep your attention on the interview screen"),
                            ("face_warning", "We cannot clearly detect your face"),
                            ("faces_warning", "More than one face appears in the camera frame"),
                            ("eye_active", "Eye tracking: active"), ("connected", "Interview session connected"),
                            ("face_chip_missing", "Face not visible"), ("two_chip", "More than one face")):
            if phrase in body and key not in seen:
                seen[key] = round(time.time() - t_cam, 1)
                if key in ("gaze_warning", "faces_warning"):
                    page.screenshot(path=OUT / f"sec_2_{key}.png")
        page.wait_for_timeout(500)
    say("seen (s after camera start):", seen)
    results["samples"] = samples
    for smp in samples[::6]:
        say("   ", smp)
    ok("eye tracking active after calibration", "eye_active" in seen)
    ok("gaze reminder while the head is turned (22-34 s), not before", 28 <= seen.get("gaze_warning", 0) <= 40, str(seen.get("gaze_warning")))
    ok("face reminder while nobody is in view (40-50 s)", 42 <= seen.get("face_warning", 0) <= 54, str(seen.get("face_warning")))
    ok("multiple-face reminder (56-66 s)", 57 <= seen.get("faces_warning", 0) <= 70, str(seen.get("faces_warning")))

    # tab switch: another tab in front for ~6 s
    other = ctx.new_page()
    other.goto(BASE + "/login")
    other.bring_to_front()
    hidden = page.evaluate("document.visibilityState")
    page.wait_for_timeout(6000)
    page.bring_to_front()
    other.close()
    say("visibility while the other tab was in front:", hidden)
    page.wait_for_timeout(1500)
    if hidden == "visible":  # some headless builds never hide a background tab: fire the real browser events instead
        page.evaluate("""async () => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});
          document.dispatchEvent(new Event('visibilitychange')); await new Promise(r => setTimeout(r, 6000));
          Object.defineProperty(document, 'hidden', {configurable: true, get: () => false});
          document.dispatchEvent(new Event('visibilitychange')); }""")
        results["tab_switch"] = "simulated via visibilitychange (headless tab stayed visible)"
    ok("return-to-window reminder shown", "You have left the interview window" in text(page))

    # 8 s offline
    ctx.set_offline(True)
    page.wait_for_timeout(2500)
    offline_chip = "Connection lost" in text(page)
    page.wait_for_timeout(5500)
    ctx.set_offline(False)
    page.wait_for_timeout(12000)  # the reporter sends every 8 s; the outage is recorded when sending works again
    ok("connection chip turned to 'Connection lost' while offline", offline_chip)
    page.screenshot(path=OUT / "sec_3_room.png")

    # reload = reconnect (setup again, same interview clock)
    page.reload()
    setup_and_start(page, calibrate=False)
    page.wait_for_timeout(8000)

    # one typed answer, then finish
    try:
        page.get_by_role("button", name="Type instead").wait_for(timeout=180000)
        page.get_by_role("button", name="Type instead").click()
        page.locator("#answer").fill("I would add an index on the columns used in WHERE and JOIN clauses and check the plan with EXPLAIN.")
        page.get_by_role("button", name="Submit answer").click()
        page.wait_for_timeout(4000)
    except Exception as e:  # noqa: BLE001
        say("typed answer step:", e)
    page.wait_for_function(f"fetch('/api/student/interviews/{sid}').then(r => r.json()).then(s => s.answered >= 1)", timeout=240000, polling=2000)
    done = api(page, f"/student/interviews/{sid}/complete", "POST")
    ok("interview completed", done["status"] == 200, str(done["status"]))
    page.goto(BASE + "/student")  # leaving the room stops the camera and flushes the last events
    page.wait_for_timeout(4000)

    mine = api(page, f"/student/interviews/{sid}/integrity-events")["body"]
    events = mine["events"]
    results["events"] = [{k: e.get(k) for k in ("event_type", "category", "t_ms", "duration_ms", "confidence", "severity", "details", "start_timestamp")} for e in events]
    types = [e["event_type"] for e in events]
    say("stored events:")
    for e in events:
        say(f"   {e['t_ms'] / 1000:7.1f}s  {e['category']:<26} {e['severity']:<6} {e['description']}")
    gaze = [e for e in events if e["event_type"] == "attention_away"]
    ok("head turn recorded as ONE prolonged-looking-away event", any(e["details"] and "head" in e["details"].get("cause", "") and e["duration_ms"] >= 8000 for e in gaze),
       str([(e["t_ms"], e["duration_ms"], e["details"]) for e in gaze]))
    ok("face absence recorded", any(e["event_type"] == "face_absent" and e["duration_ms"] >= 6000 for e in events))
    ok("multiple faces recorded with the count", any(e["event_type"] == "multiple_faces" and (e["details"] or {}).get("max_faces", 0) >= 2 for e in events))
    ok("tab switch recorded with duration", any(e["event_type"] == "focus_change" and e["duration_ms"] >= 4000 for e in events))
    ok("network interruption recorded", "network_interruption" in types)
    ok("reload recorded as reconnect by the server", "session_reconnected" in types)
    ok("events never duplicated", len({(e["event_type"], e["t_ms"]) for e in events}) == len(events))
    ok("possible additional voice (static synthetic mouth + fake mic) recorded", "background_speech" in types,
       "depends on the mic opening while one face is visible")
    ok("risk summary present", mine["summary"]["risk"]["band"]["code"] in ("low", "moderate", "high"), mine["summary"]["risk"]["band"]["label"])

    # recruiter: report, timeline UI and a review that cannot change detection fields
    lst = api(rec, "/monitoring/sessions")["body"]["items"]
    ok("recruiter sees the completed interview of their applicant", any(i["id"] == sid for i in lst))
    rec.goto(BASE + "/recruiter/security")
    rec.get_by_text("Interview security reports").first.wait_for(timeout=30000)
    rec.locator("tr", has_text="Backend Developer").first.click()
    rec.get_by_text("Security summary:").wait_for(timeout=30000)
    rec.wait_for_timeout(800)
    rec.screenshot(path=OUT / "sec_4_recruiter_timeline.png", full_page=True)
    ok("timeline shows clock times", bool(re.search(r"\d\d:\d\d:\d\d", rec.inner_text("body"))))
    first = events[0]
    rv = api(rec, f"/monitoring/events/{first['id']}", "PATCH", {"review_status": "false_positive", "reviewer_notes": "E2E review", "t_ms": 1})
    ok("recruiter review saved; detection fields unchanged", rv["status"] == 200 and rv["body"]["t_ms"] == first["t_ms"]
       and rv["body"]["review_status"] == "false_positive")
    # expected: pre-login auth probe (401), WebGL switched off for this run, MediaPipe's own INFO line, the offline step
    errors = [e for e in errors if not re.search(r"401 \(Unauthorized\)|WebGL|XNNPACK delegate|ERR_INTERNET_DISCONNECTED", e)]
    ok("no browser console errors", not errors, "; ".join(errors[:3]))

    # tidy up the demo data created here: withdraw the application, close the job
    apps = api(page, "/student/applications")["body"]
    for a in (apps.get("items", []) if isinstance(apps, dict) else apps or []):
        if (a.get("job") or {}).get("id") == job_id and a.get("status") != "withdrawn":
            api(page, f"/student/applications/{a['id']}/withdraw", "POST")
    api(rec, f"/recruiter/jobs/{job_id}/status/close", "POST")
    browser.close()

(OUT / "security_module.json").write_text(json.dumps(results, indent=2))
failed = [c for c in results["checks"] if not c["ok"]]
say(f"\n{len(results['checks']) - len(failed)}/{len(results['checks'])} checks passed")
sys.exit(1 if failed else 0)
