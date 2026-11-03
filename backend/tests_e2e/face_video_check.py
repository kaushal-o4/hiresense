"""Camera-analysis check with a face in view (Chromium fake camera fed with a generated video).

Chromium's default fake camera shows a test pattern without a face, so the main E2E only exercises "face not
visible". This script builds a looping fake-camera video from the app's own synthetic 3D interviewer (Rocketbox
model, not a real person; taken from an earlier E2E screenshot) and checks, on the setup screen and in the room:
  * 0-12 s   one face, centred      -> "face is visible", no warning
  * 12-24 s  two faces               -> "More than one face" guidance, warning after the grace period, event stored
  * 24-36 s  one face at the edge    -> "move ... center" guidance
Needs backend + frontend running (no AI calls beyond the first question). From the backend folder:
    .\\venv\\Scripts\\python.exe tests_e2e\\face_video_check.py
"""
import base64
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SRC = HERE / "output" / "2_speaking.png"  # avatar screenshot (synthetic 3D face)
BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5173")
W, H, FPS = 320, 240, 5
SEGMENT_S = 12
if not SRC.exists():
    sys.exit("Run tests_e2e/voice_interview_browser.py first (it saves output/2_speaking.png)")

COMPOSE = """async ([src, W, H]) => {
  const img = new Image(); img.src = src; await img.decode();
  const head = { x: 505, y: 225, w: 250, h: 290 };   // the avatar's head in the 1366x900 screenshot
  const frame = (faces) => {
    const c = document.createElement('canvas'); c.width = W; c.height = H;
    const g = c.getContext('2d'); g.fillStyle = '#8a8478'; g.fillRect(0, 0, W, H);
    for (const f of faces) g.drawImage(img, head.x, head.y, head.w, head.h, f.x, f.y, f.w, f.h);
    const d = g.getImageData(0, 0, W, H).data;
    let s = '';
    for (let i = 0; i < d.length; i += 8192) s += String.fromCharCode.apply(null, d.subarray(i, i + 8192));
    return btoa(s);
  };
  return {
    one: frame([{ x: 100, y: 25, w: 120, h: 140 }]),
    two: frame([{ x: 20, y: 40, w: 115, h: 134 }, { x: 185, y: 40, w: 115, h: 134 }]),
    edge: frame([{ x: 0, y: 25, w: 80, h: 94 }]),
  };
}"""


def rgba_to_i420(rgba: bytes) -> bytes:
    a = np.frombuffer(rgba, np.uint8).reshape(H, W, 4).astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    y = 0.257 * r + 0.504 * g + 0.098 * b + 16
    u = -0.148 * r - 0.291 * g + 0.439 * b + 128
    v = 0.439 * r - 0.368 * g - 0.071 * b + 128
    sub = lambda c: c.reshape(H // 2, 2, W // 2, 2).mean(axis=(1, 3))  # noqa: E731
    return b"".join(np.clip(x, 0, 255).astype(np.uint8).tobytes() for x in (y, sub(u), sub(v)))


def make_video(frames: dict) -> str:
    path = Path(tempfile.gettempdir()) / "hs_face_check.y4m"
    with open(path, "wb") as f:
        f.write(f"YUV4MPEG2 W{W} H{H} F{FPS}:1 Ip A1:1 C420jpeg\n".encode())
        for key in ("one", "two", "edge"):
            data = rgba_to_i420(base64.b64decode(frames[key]))
            for _ in range(SEGMENT_S * FPS):
                f.write(b"FRAME\n" + data)
    return str(path)


results = {"checks": []}


def ok(name, cond, detail=""):
    results["checks"].append({"check": name, "passed": bool(cond), "detail": detail})
    print(("[ok]  " if cond else "[FAIL]"), name, detail, flush=True)


with sync_playwright() as p:
    b0 = p.chromium.launch(headless=True)
    pg = b0.new_page()
    frames = pg.evaluate(COMPOSE, ["data:image/png;base64," + base64.b64encode(SRC.read_bytes()).decode(), W, H])
    b0.close()
    video = make_video(frames)
    print("fake camera video:", video, flush=True)

    browser = p.chromium.launch(headless=True, args=[
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
        f"--use-file-for-fake-video-capture={video}", "--autoplay-policy=no-user-gesture-required",
        "--disable-webgl", "--disable-3d-apis"])  # 2D interviewer: keep the CPU for face analysis
    page = browser.new_page(viewport={"width": 1366, "height": 1000})
    page.goto(BASE + "/login")
    page.evaluate("""async (c) => { const r = await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(c)}); if (!r.ok) throw new Error('login ' + r.status); }""",
                  {"email": os.environ.get("HS_E2E_EMAIL", "student@demo.hiresense"),
                   "password": os.environ.get("HS_E2E_PASSWORD", "Demo@12345")})
    page.evaluate("""async () => { const r = await fetch('/api/student/interviews?status=in_progress&page_size=50');
      for (const s of (await r.json()).items) await fetch('/api/student/interviews/' + s.id, {method: 'DELETE'}); }""")
    sid = page.evaluate("""async () => (await (await fetch('/api/student/interviews', {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({job_role: 'Backend Developer', mode: 'voice',
      question_count: 3, defer_first_question: true})})).json()).session.id""")
    page.goto(f"{BASE}/student/interviews/{sid}/live")
    page.get_by_text("Camera and interview monitoring").wait_for(timeout=60000)
    for label in ("Camera with self-view", "Face visibility", "More than one face"):
        box = page.get_by_label(re.compile(label))
        if not box.is_checked():
            box.check()
    page.get_by_role("button", name=re.compile("Test my camera")).click()
    t0 = time.time()  # the fake video starts when the camera opens
    seen: dict[str, set] = {"one": set(), "two": set(), "edge": set()}
    while time.time() - t0 < 3 * SEGMENT_S:
        el = page.locator("section[aria-labelledby=chk-title]")
        text = el.inner_text() if el.count() else ""
        seg = ("one", "two", "edge")[min(2, int((time.time() - t0) // SEGMENT_S))]
        for phrase in ("visible and the lighting looks fine", "More than one face", "center of the picture",
                       "center of the camera", "far from the camera", "dark"):
            if phrase in text and (time.time() - t0) % SEGMENT_S > 3:  # skip the moment of switching
                seen[seg].add(phrase)
        page.wait_for_timeout(400)
    results["setup_guidance_seen"] = {k: sorted(v) for k, v in seen.items()}
    ok("one centred face: reported visible", "visible and the lighting looks fine" in seen["one"], str(sorted(seen["one"])))
    ok("two faces: reported", "More than one face" in seen["two"], str(sorted(seen["two"])))
    ok("face at the edge: asked to move to the centre", bool(seen["edge"] & {"center of the picture", "far from the camera"}),
       str(sorted(seen["edge"])))

    # In the room: the tracker must warn about two faces only after the grace period and record one event.
    agree = page.get_by_label("I have read what is monitored")  # monitoring notice (security module)
    if agree.count():
        agree.check()
    page.get_by_role("button", name=re.compile("start the interview")).click()
    t_room = time.time()
    warned_at = None
    face_warn = False
    while time.time() - t_room < 75:
        body = page.inner_text("body")
        face_warn = face_warn or "cannot clearly detect your face" in body
        if warned_at is None and "More than one face appears in the camera frame" in body:
            warned_at = time.time() - t_room
        page.wait_for_timeout(500)
    ok("multiple-face warning shown in the room", warned_at is not None, f"after {warned_at and round(warned_at, 1)} s in the room")
    ok("no 'face not visible' warning while a face is in view", not face_warn)
    page.get_by_role("button", name="End", exact=True).click()
    page.get_by_role("button", name="Confirm", exact=True).click()
    page.wait_for_timeout(2000)
    ev = page.evaluate(f"async () => (await (await fetch('/api/student/interviews/{sid}/integrity-events')).json()).events")
    results["events"] = [{k: e[k] for k in ("event_type", "t_ms", "duration_ms", "confidence", "severity")} for e in ev]
    multi = [e for e in ev if e["event_type"] == "multiple_faces"]
    ok("multiple_faces event recorded with duration and confidence",
       bool(multi) and all(e["duration_ms"] and e["confidence"] for e in multi), json.dumps(results["events"]))
    ok("no face_absent event while a face was in view", not [e for e in ev if e["event_type"] == "face_absent"])
    browser.close()

(HERE / "output" / "face_video_check.json").write_text(json.dumps(results, indent=2))
failed = [c for c in results["checks"] if not c["passed"]]
print(f"{len(results['checks']) - len(failed)}/{len(results['checks'])} checks passed")
sys.exit(1 if failed else 0)
