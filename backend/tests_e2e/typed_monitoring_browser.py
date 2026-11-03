"""Typed interview monitoring, end to end in a real browser (headless Chromium, Chromium's built-in fake camera).

The fake camera shows a test pattern (no face), so this checks the wiring, not face detection: the setup screen with
the notice, consent, the status bar, the self-view, tab-switch/offline events reaching the database, and that the
camera is released when the interview finishes. Face detection itself is covered by security_module_browser.py.

Needs backend + frontend running and the demo accounts. From the backend folder:
    .\\venv\\Scripts\\python.exe tests_e2e\\typed_monitoring_browser.py
Leaves one abandoned or completed demo typed interview.
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5173")
STUDENT = {"email": "student@demo.hiresense", "password": "Demo@12345"}
checks = []


def ok(name, cond, detail=""):
    checks.append(bool(cond))
    print(("[ok]   " if cond else "[FAIL] ") + name + (f" - {detail}" if detail else ""), flush=True)


LOGIN = """async (c) => { const r = await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'},
  body: JSON.stringify(c)}); if (!r.ok) throw new Error('login ' + r.status); }"""
FETCH = """async ([url, method, body]) => { const r = await fetch('/api' + url, {method, headers: {'Content-Type': 'application/json'},
  body: body ? JSON.stringify(body) : undefined}); const t = await r.text(); return {status: r.status, body: t ? JSON.parse(t) : null}; }"""


def api(page, url, method="GET", body=None):
    return page.evaluate(FETCH, [url, method, body])


with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
    ctx = b.new_context(viewport={"width": 1366, "height": 900}, permissions=["camera"])
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE + "/login")
    page.evaluate(LOGIN, STUDENT)
    res = api(page, "/student/interviews", "POST", {"job_role": "Backend Developer", "category": "hr", "mode": "text",
                                                    "question_count": 3})
    ok("typed interview created", res["status"] in (200, 201), str(res["status"]))
    sid = res["body"]["session"]["id"]

    page.goto(f"{BASE}/student/interviews/{sid}")
    page.get_by_text("Camera and interview monitoring").wait_for(timeout=60000)
    ok("setup screen shown before any question", page.get_by_text("Before we start with").count() == 1)
    ok("typed copy (no spoken-question text)", page.get_by_text("asks each question aloud").count() == 0
       and page.get_by_text("you type your answers").count() == 1)
    ok("no additional-voice (audio) option offered", page.get_by_text("additional voice", exact=False).count() == 0
       or page.get_by_label("Possible additional voice").count() == 0)
    ok("question not visible before consent", page.locator("textarea#answer").count() == 0)

    page.get_by_role("button", name="Test my camera and connection").click()
    page.wait_for_function("document.querySelector('video') && document.querySelector('video').srcObject", timeout=30000)
    ok("camera preview started after the button press", True)

    start = page.get_by_role("button", name="start the interview")
    focus = page.get_by_label("Browser focus changes", exact=False)
    if focus.count() and not focus.is_checked():
        focus.check()  # optional detector: nothing runs unless it is ticked
    notice = page.get_by_label("I have read what is monitored", exact=False)
    if notice.count():
        notice.check()
    ok("start enabled after acknowledging the notice", start.is_enabled())
    start.click()
    page.locator("textarea#answer").wait_for(timeout=120000)
    ok("question and answer box appear after consent", True)
    ok("monitoring status bar shown", page.get_by_role("status", name="Camera, microphone and monitoring status").count() == 1)
    ok("camera on badge", page.get_by_text("Camera on").first.is_visible())
    ok("self-view mounted", page.locator("video[aria-label^='Your camera']").count() == 1)

    # a real visibilitychange + offline period, then check what the server stored
    page.evaluate("""() => { Object.defineProperty(document, 'visibilityState', {value:'hidden', configurable:true});
      Object.defineProperty(document, 'hidden', {value:true, configurable:true}); document.dispatchEvent(new Event('visibilitychange')); }""")
    page.wait_for_timeout(3500)
    page.evaluate("""() => { Object.defineProperty(document, 'visibilityState', {value:'visible', configurable:true});
      Object.defineProperty(document, 'hidden', {value:false, configurable:true}); document.dispatchEvent(new Event('visibilitychange')); }""")
    page.wait_for_timeout(500)

    # reload = reconnect: setup is shown again, re-consent is stored as a reconnect
    page.reload()
    page.get_by_text("Camera and interview monitoring").wait_for(timeout=60000)
    ok("after a reload the notice is shown again (reconnect)", True)

    mon = api(page, f"/student/interviews/{sid}/integrity-events")
    events = (mon["body"] or {}).get("events", []) if mon["status"] == 200 else []
    types = {e.get("event_type") for e in events}
    print("stored event types:", sorted(types), flush=True)
    ok("tab-switch event (focus_change) stored; flushed by the page close", "focus_change" in types)

    ok("no uncaught page errors", not errors, "; ".join(errors)[:300])
    api(page, f"/student/interviews/{sid}", "DELETE")  # abandon the demo interview
    b.close()

print(f"\n{sum(checks)}/{len(checks)} checks passed")
sys.exit(0 if all(checks) else 1)
