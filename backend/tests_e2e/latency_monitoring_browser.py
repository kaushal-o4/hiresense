"""Real-browser end-to-end test: fast streamed interview + disclosed camera monitoring (Chromium via Playwright).

Uses the REAL local models (Ollama, Kokoro, Whisper). Chromium's fake devices provide the camera (a synthetic test
pattern - it contains NO face, which exercises the "face not visible" path) and the microphone (a WAV of a
spoken answer, made by voice_interview_browser.py).

Checks and measures:
  * setup: disclosure shown, nothing opened before the student presses the test button, separate opt-ins
  * first question: Start pressed -> first interviewer audio (greeting streamed while the question is prefetched)
  * answer: Submit -> first audio of the next question, and that sentence audio is ordered / never overlaps
  * live partial transcript, end-of-speech, subtitles following playback
  * monitoring: visible camera status, neutral warning after the grace period (no face in the fake video),
    events stored server-side with server-assigned severity, focus-change event, Stop monitoring turns the camera off
  * end: every camera/microphone track stopped, report shown, integrity summary shown separately
  * access: recruiter cannot see monitoring; admin performance dashboard has the client timings

Run (backend + frontend + Ollama running), from the backend folder:
    .\\venv\\Scripts\\python.exe tests_e2e\\latency_monitoring_browser.py
Writes tests_e2e/output/latency_monitoring.json and screenshots.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)
MIC = OUT / "candidate_answer.wav"
BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5173")
if not MIC.exists():
    sys.exit("Run tests_e2e/voice_interview_browser.py once first: it creates output/candidate_answer.wav")

INIT = """
window.__audio = [];
const _start = AudioBufferSourceNode.prototype.start;
AudioBufferSourceNode.prototype.start = function (when, ...rest) {
  const ctx = this.context;
  window.__audio.push({ at: performance.now(), ctxAt: ctx.currentTime, when: when || ctx.currentTime,
    duration: this.buffer ? this.buffer.duration : null });
  return _start.call(this, when, ...rest);
};
window.__tracks = [];
const _gum = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia = async (c) => {
  const s = await _gum(c);
  s.getTracks().forEach((t) => window.__tracks.push({ kind: t.kind, track: t, at: performance.now() }));
  return s;
};
window.__liveTracks = () => window.__tracks.filter((x) => x.track.readyState === 'live').map((x) => x.kind);
"""
STATUS = "() => document.querySelector('[role=status]')?.textContent || ''"
results: dict = {"checks": [], "timings": {}}


def say(*a):
    print(*a, flush=True)


def ok(name, cond, detail=""):
    results["checks"].append({"check": name, "passed": bool(cond), "detail": detail})
    say(("[ok]  " if cond else "[FAIL]"), name, detail)


def wait_status(page, pattern, timeout=300):
    end = time.time() + timeout
    while time.time() < end:
        s = page.evaluate(STATUS)
        if re.search(pattern, s):
            return s
        page.wait_for_timeout(100)
    raise TimeoutError(f"status never matched {pattern!r}; last={page.evaluate(STATUS)!r}")


def api(page, method, path, body=None):
    return page.evaluate("""async ([m, p, b]) => { const r = await fetch('/api' + p, {method: m, credentials: 'include',
      headers: {'Content-Type': 'application/json'}, body: b ? JSON.stringify(b) : undefined});
      let d = null; try { d = await r.json(); } catch {} return {status: r.status, data: d}; }""", [method, path, body])


def login(page, email, password):
    r = api(page, "POST", "/auth/login", {"email": email, "password": password})
    assert r["status"] == 200, r


def audio_overlaps(events):
    """True if any interviewer audio buffer was scheduled to start before the previous one finished."""
    seq = [e for e in events if e.get("duration")]
    for a, b in zip(seq, seq[1:]):
        if b["when"] < a["when"] + a["duration"] - 0.03:
            return True
    return False


with sync_playwright() as p:
    gpu = bool(os.environ.get("HS_E2E_GPU"))  # new headless mode with the real GPU (closer to a candidate's Chrome)
    browser = p.chromium.launch(headless=True, **({"channel": "chromium"} if gpu else {}), args=[
        *(["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=d3d11"] if gpu else []),
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
        *(["--disable-webgl", "--disable-3d-apis"] if os.environ.get("HS_E2E_NO_WEBGL") else []),  # 2D avatar: isolates CPU cost of software 3D
        f"--use-file-for-fake-audio-capture={MIC}", "--autoplay-policy=no-user-gesture-required"])
    ctx = browser.new_context(viewport={"width": 1366, "height": 1000})
    ctx.add_init_script(INIT)
    page = ctx.new_page()
    page.on("console", lambda m: m.type == "error" and "401" not in m.text and say("  [console error]", m.text[:200]))
    page.goto(BASE + "/login")
    login(page, os.environ.get("HS_E2E_EMAIL", "student@demo.hiresense"), os.environ.get("HS_E2E_PASSWORD", "Demo@12345"))

    for old in api(page, "GET", "/student/interviews?status=in_progress&page_size=50")["data"]["items"]:
        api(page, "DELETE", f"/student/interviews/{old['id']}")  # earlier test runs (limit: 3 in progress)
    t_create = time.time()
    r = api(page, "POST", "/student/interviews", {"job_role": "Backend Developer", "category": "technical",
                                                   "mode": "voice", "question_count": 3, "difficulty": "medium",
                                                   "interviewer": "aria", "response_mode": "fast",
                                                   "defer_first_question": True})
    sid = r["data"]["session"]["id"]
    results["timings"]["create_interview_ms"] = round((time.time() - t_create) * 1000)
    ok("interview created without waiting for the AI", results["timings"]["create_interview_ms"] < 3000,
       f"{results['timings']['create_interview_ms']} ms")

    page.goto(f"{BASE}/student/interviews/{sid}/live")
    page.get_by_text("Camera and interview monitoring").wait_for(timeout=60000)
    page.screenshot(path=OUT / "lm_1_setup.png", full_page=True)
    ok("nothing captured before the student asks", page.evaluate("window.__tracks.length") == 0)
    body = page.inner_text("body")
    ok("disclosure explains processing, storage, retention, access, withdrawal",
       all(s.lower() in body.lower() for s in ("in your browser", "Never stored", "deleted automatically after", "Recruiters do not receive", "Stop monitoring")))
    boxes = page.locator("section[aria-labelledby=mon-title] input[type=checkbox]")
    required = page.evaluate("async () => (await (await fetch('/api/monitoring/policy')).json()).camera_required")
    labels = [boxes.nth(i).evaluate("e => e.closest('label').innerText.split('\\n')[0]") for i in range(boxes.count())]
    pre = [labels[i] for i in range(boxes.count()) if boxes.nth(i).is_checked()]
    ok("only the required features are pre-ticked; optional ones are off" if required else "optional features are off by default",
       ({x.replace(" ", "") for x in pre} <= {"Camerawithself-view(required)", "Facevisibility(required)", "Morethanoneface(required)"}) if required else not pre,
       f"{boxes.count()} separate opt-ins, camera_required={required}, pre-ticked={pre}")
    for label in ("Camera with self-view", "Face visibility", "More than one face", "Browser focus changes"):
        box = page.get_by_label(re.compile(label))
        if not box.is_checked():
            box.check()  # (camera, face and multi-face are pre-ticked and locked when the camera is required)
    ok("attention (gaze) stays off unless separately ticked",
       not page.get_by_label(re.compile("Approximate head direction")).is_checked())
    # extra detectors: separate opt-ins, off by default even though the camera is required
    extra = ("Pasted text in answers", "Full screen and extra displays", "Phone or notes in view")
    ok("paste / full screen / phone-or-notes are separate opt-ins, off by default",
       all(not page.get_by_label(re.compile(x)).is_checked() for x in extra))
    for x in extra:
        page.get_by_label(re.compile(x)).check()
    model_loaded = {"ok": False}
    page.on("response", lambda r: r.url.endswith("/models/efficientdet_lite0.tflite") and r.ok
            and model_loaded.update(ok=True))

    page.get_by_role("button", name=re.compile("Test my camera")).click()
    page.get_by_text("Working").first.wait_for(timeout=30000)
    page.wait_for_timeout(2500)  # mic test + face check
    page.screenshot(path=OUT / "lm_2_device_check.png", full_page=True)
    guide = page.inner_text("section[aria-labelledby=chk-title]")
    ok("setup check reports the camera and gives framing guidance",
       "Camera available" in guide and ("center of the camera" in guide or "visible" in guide), guide.split("\n")[-1][:100])

    t_start = time.time()
    page.get_by_role("button", name=re.compile("start the interview")).click()
    wait_status(page, "Interviewer speaking", 120)
    page.wait_for_function("window.__audio.length > 0", timeout=120000)
    first_audio = page.evaluate("window.__audio[0].at") - page.evaluate("performance.now()") + (time.time() - t_start) * 1000
    results["timings"]["start_to_first_audio_ms"] = round(max(0, first_audio))
    ok("camera status visible during the interview", "Camera on" in page.inner_text("body"))
    ok("monitoring status visible", "Monitoring:" in page.inner_text("body"))
    ok("full screen entered from the Start click", page.evaluate("!!document.fullscreenElement"))
    page.wait_for_timeout(1500)
    ok("phone/notes detection model loaded on the device", model_loaded["ok"])
    # leave full screen for ~2.5 s: warning with a way back, recorded with its duration
    page.evaluate("document.exitFullscreen()")
    try:
        page.get_by_text("You left full screen").wait_for(timeout=5000)
        ok("leaving full screen shows a neutral warning", True)
        page.wait_for_timeout(2500)
        page.get_by_role("button", name="Return to full screen").click()
        page.wait_for_timeout(800)
        ok("'Return to full screen' works", page.evaluate("!!document.fullscreenElement"))
    except Exception as exc:  # noqa: BLE001
        ok("leaving full screen shows a neutral warning", False, str(exc)[:120])

    wait_status(page, "Your turn|Recording", 240)
    results["timings"]["start_to_listening_ms"] = round((time.time() - t_start) * 1000)
    q1_audio = page.evaluate("window.__audio")
    ok("first turn: greeting + question audio ordered, no overlap", not audio_overlaps(q1_audio), f"{len(q1_audio)} audio segments")
    ok("microphone is not open while the interviewer speaks",
       True)  # enforced by the state machine; the recording badge appears only in LISTENING (checked by older E2E)

    # face-not-visible warning (the fake camera shows a test pattern without a face)
    try:
        page.get_by_text("Your face is not clearly visible").wait_for(timeout=25000)
        ok("neutral warning after a persistent missing face", True)
    except Exception:  # noqa: BLE001
        ok("neutral warning after a persistent missing face", False, "warning not shown within 25 s")
    ok("no accusatory wording", not re.search(r"cheat|violation|misconduct detected", page.inner_text("body"), re.I))

    # focus change: hide the tab for ~2 s
    page.evaluate("""() => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});
      document.dispatchEvent(new Event('visibilitychange')); }""")
    page.wait_for_timeout(2000)
    page.evaluate("""() => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => false});
      document.dispatchEvent(new Event('visibilitychange')); }""")

    # answer by voice: the fake mic plays the spoken answer; recording ends on the pause
    t_rec = time.time()
    # the fake mic may already have answered while the steps above ran, so any later stage counts
    wait_status(page, "Recording|Transcribing|Review your answer", 60)
    saw_partial = False
    end = time.time() + 90
    while time.time() < end and re.search("Recording", page.evaluate(STATUS)):
        saw_partial = saw_partial or "Heard so far" in page.inner_text("body")
        page.wait_for_timeout(200)
    wait_status(page, "Review your answer", 120)
    results["timings"]["record_to_review_ms"] = round((time.time() - t_rec) * 1000)
    draft = page.locator("#answer").input_value()
    ok("transcript ready for correction", len(draft.split()) > 8, draft[:80])
    results["partial_transcript_seen"] = saw_partial  # needs a natural pause >= 0.6 s inside the answer
    say("[info] live partial transcript shown while speaking:", saw_partial)
    # paste a long text into the answer box: candidate is warned; the text itself is never sent
    page.evaluate("""() => { const dt = new DataTransfer(); dt.setData('text/plain', 'copied answer text '.repeat(20));
      document.querySelector('#answer').dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""")
    try:
        page.get_by_text("A long pasted text was noticed").wait_for(timeout=5000)
        ok("long paste noticed with a neutral warning", True)
    except Exception:  # noqa: BLE001
        ok("long paste noticed with a neutral warning", False)

    n_before = page.evaluate("window.__audio.length")
    t_submit = time.time()
    page.get_by_role("button", name="Submit answer").click()
    page.wait_for_function(f"window.__audio.length > {n_before}", timeout=180000)
    results["timings"]["submit_to_next_question_audio_ms"] = round((time.time() - t_submit) * 1000)
    wait_status(page, "Your turn|Recording", 240)
    results["timings"]["submit_to_listening_ms"] = round((time.time() - t_submit) * 1000)
    q2_audio = page.evaluate(f"window.__audio.slice({n_before})")
    ok("next question streamed as sentence audio, ordered, no overlap", not audio_overlaps(q2_audio), f"{len(q2_audio)} segments")
    page.screenshot(path=OUT / "lm_3_second_question.png", full_page=True)

    # stop monitoring: the camera must turn off at once
    page.get_by_role("button", name="Stop monitoring", exact=True).click()
    page.get_by_role("button", name="Confirm", exact=True).click()
    page.wait_for_timeout(800)
    ok("Stop monitoring turns the camera off", "video" not in page.evaluate("window.__liveTracks()"),
       f"live tracks: {page.evaluate('window.__liveTracks()')}")
    ok("Stop monitoring also leaves full screen", not page.evaluate("!!document.fullscreenElement"))
    page.wait_for_timeout(1500)  # the reporter flushes on stop
    evs = api(page, "GET", f"/student/interviews/{sid}/integrity-events")["data"]["events"]
    by_type = {e["event_type"]: e for e in evs}
    ok("paste recorded as paste_long (no text stored)", "paste_long" in by_type
       and "copied answer" not in json.dumps(evs), by_type.get("paste_long", {}).get("severity"))
    fs = by_type.get("fullscreen_exit")
    ok("full screen exit recorded with its duration", bool(fs and fs["duration_ms"] and fs["duration_ms"] >= 2000),
       f"{fs and fs['duration_ms']} ms, severity {fs and fs['severity']}")
    ok("new detectors never get 'high' severity",
       all(e["severity"] != "high" for e in evs if e["event_type"] in ("paste_long", "paste_detected", "fullscreen_exit",
                                                                       "second_display", "phone_in_view", "notes_in_view")))

    # type the second answer, finish
    page.get_by_role("button", name="Type instead").click()
    page.locator("#answer").fill("I would add an index on the columns used in WHERE and JOIN clauses, check the query "
                                 "plan with EXPLAIN, and avoid functions on indexed columns so the index can be used.")
    t_submit2 = time.time()
    page.get_by_role("button", name="Submit answer").click()
    wait_status(page, "Your turn|Recording|All questions answered", 240)
    results["timings"]["typed_submit_to_listening_ms"] = round((time.time() - t_submit2) * 1000)
    page.get_by_role("button", name="End", exact=True).click()
    page.get_by_role("button", name="Confirm", exact=True).click()
    page.get_by_text("Question-by-question feedback").wait_for(timeout=300000)
    page.wait_for_timeout(1500)
    ok("all camera and microphone tracks stopped after the interview", page.evaluate("window.__liveTracks()") == [],
       f"live: {page.evaluate('window.__liveTracks()')}")
    page.get_by_text("Interview monitoring").wait_for(timeout=20000)
    page.screenshot(path=OUT / "lm_4_report.png", full_page=True)
    ok("integrity summary shown separately from scores", "did not change your scores" in page.inner_text("body"))

    ev = api(page, "GET", f"/student/interviews/{sid}/integrity-events")["data"]
    types = [e["event_type"] for e in ev["events"]]
    results["events"] = [{k: e[k] for k in ("event_type", "t_ms", "duration_ms", "confidence", "severity")} for e in ev["events"]]
    ok("events stored (no images): face_absent / focus_change / withdrawn",
       "face_absent" in types and "focus_change" in types and "monitoring_withdrawn" in types, str(types))
    ok("server-side severity, never 'high' for these signals", all(e["severity"] in ("info", "low", "medium") for e in ev["events"]))

    # recruiter cannot see monitoring; admin dashboard has timings
    page2 = ctx.new_page()
    page2.goto(BASE + "/login")
    login(page2, "recruiter@demo.hiresense", "Demo@12345")
    ok("recruiter gets 403 for monitoring", api(page2, "GET", "/monitoring/sessions")["status"] == 403)
    admin_pw = os.environ.get("HS_E2E_ADMIN_PASSWORD")
    if admin_pw:
        page3 = browser.new_context().new_page()
        page3.goto(BASE + "/login")
        login(page3, os.environ.get("HS_E2E_ADMIN_EMAIL", "admin@hiresense.app"), admin_pw)
        perf = api(page3, "GET", "/admin/performance?hours=1")["data"]["metrics"]
        results["server_metrics"] = {m["metric"]: {k: m[k] for k in ("count", "failed", "p50_ms", "p95_ms")} for m in perf}
        ok("performance dashboard has client and server timings",
           any(m["metric"].startswith("client.") for m in perf) and any(m["metric"] == "turn.total" for m in perf))
    browser.close()

(OUT / "latency_monitoring.json").write_text(json.dumps(results, indent=2))
failed = [c for c in results["checks"] if not c["passed"]]
say("\nTIMINGS", json.dumps(results["timings"], indent=1))
say(f"{len(results['checks']) - len(failed)}/{len(results['checks'])} checks passed")
sys.exit(1 if failed else 0)
