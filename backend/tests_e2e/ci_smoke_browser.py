"""Fast browser smoke test, run by CI on every push (no GPU, no AI models, no demo accounts needed).

Registers a fresh student, opens the main student pages and checks that each renders without an uncaught page
error, then runs one live (voice-room) interview turn by typing: setup screen with the fake camera, the room's
control bar, settings and transcript panels, a typed answer, and the next question from the question bank.

Needs the backend (any AI settings; CI runs it with AI_ENABLED=false) and the frontend (dev server or
`vite preview`). From the backend folder:
    python tests_e2e/ci_smoke_browser.py          # HS_E2E_BASE=http://127.0.0.1:4173 for vite preview
"""
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)
BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5173")
EMAIL = f"ci-smoke-{int(time.time())}@test.dev"
PASSWORD = "SmokeTest-Passw0rd"
checks: list[bool] = []

FETCH = """async ([url, method, body]) => { const r = await fetch('/api' + url, {method, credentials: 'include',
  headers: {'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
  const t = await r.text(); let j = null; try { j = t ? JSON.parse(t) : null; } catch { j = t; } return {status: r.status, body: j}; }"""

# Interviewer voice off: no speech synthesis in a headless browser; the question is shown as text instead.
INIT = """try { localStorage.setItem('hs-room-settings', JSON.stringify({v: 2, voiceOn: false, autoMic: false})); } catch {}"""

PAGES = [  # each must render a visible <h1> without an uncaught page error
    "/student",
    "/student/progress",
    "/student/jobs",
    "/student/interviews",
    "/student/resume",
    "/student/english",
    "/student/english/vocabulary",
    "/student/assessments",
    "/student/rewards",
    "/student/applications",
    "/student/mentoring",
    "/notifications",
    "/settings",
    "/profile",
    "/privacy",
]


def ok(name, cond, detail=""):
    checks.append(bool(cond))
    print(("[ok]   " if cond else "[FAIL] ") + name + (f" - {detail}" if detail else ""), flush=True)


def api(page, url, method="GET", body=None):
    return page.evaluate(FETCH, [url, method, body])


def settle(page):
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:  # noqa: BLE001 - long-lived streams (notifications) can keep the network busy
        pass
    page.wait_for_timeout(300)


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
    ctx = browser.new_context(viewport={"width": 1366, "height": 900}, permissions=["camera", "microphone"])
    ctx.add_init_script(INIT)
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(f"{page.url}: {e}"))

    # ---- account
    page.goto(BASE + "/login")
    r = api(page, "/auth/register/student", "POST", {"full_name": "CI Smoke", "email": EMAIL, "password": PASSWORD,
                                                     "college": "Test College", "branch": "CSE",
                                                     "graduation_year": 2027})
    ok("student registered", r["status"] == 201, str(r["status"]))
    api(page, "/auth/logout", "POST")
    page.goto(BASE + "/login")
    page.get_by_label("Email").fill(EMAIL)
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name=re.compile("^Sign in", re.I)).click()
    page.wait_for_url(re.compile(r".*/student/?$"), timeout=30000)
    ok("login through the form lands on the dashboard", True)
    privacy = api(page, "/auth/privacy")
    if privacy["status"] == 200 and (privacy["body"] or {}).get("consent_required"):
        api(page, "/auth/ai-consent", "POST", {"accept": True})  # hosted-AI consent, when the server asks for it

    # ---- every main page renders
    for path in PAGES:
        before = len(errors)
        page.goto(BASE + path)
        settle(page)
        heading = page.locator("main h1, h1").first
        rendered = heading.count() > 0 and heading.is_visible()
        ok(f"page {path} renders", rendered and len(errors) == before and "/login" not in page.url,
           (heading.inner_text()[:60] if rendered else "no heading") + ("; " + errors[-1][:160] if len(errors) > before else ""))
    page.screenshot(path=OUT / "ci_smoke_pages.png")

    # ---- one live-room turn, typed
    res = api(page, "/student/interviews", "POST", {"job_role": "Backend Developer", "category": "hr", "mode": "voice",
                                                    "question_count": 3, "interviewer": "aria"})
    ok("voice interview created", res["status"] in (200, 201), str(res["status"]))
    if res["status"] in (200, 201):
        sid = res["body"]["session"]["id"]
        page.goto(f"{BASE}/student/interviews/{sid}/live")
        start = page.get_by_role("button", name=re.compile("start the interview", re.I))
        start.wait_for(timeout=60000)
        ok("setup screen shown", True)
        test_cam = page.get_by_role("button", name=re.compile("Test my camera", re.I))
        if test_cam.count():
            test_cam.click()
            page.wait_for_function("document.querySelector('video') && document.querySelector('video').srcObject",
                                   timeout=30000)
        for label in ("I have read what is monitored",):
            box = page.get_by_label(label, exact=False)
            if box.count() and not box.is_checked():
                box.check()
        start.click()
        toolbar = page.get_by_role("toolbar", name="Interview controls")
        toolbar.wait_for(timeout=120000)
        ok("room control bar shown", toolbar.is_visible())
        page.get_by_role("button", name="Settings").click()
        ok("settings panel opens", page.get_by_text("Subtitle size").is_visible())
        ok("transcript panel shown", page.get_by_text("Transcript", exact=True).is_visible())
        # Typed answer: "Type instead" (microphone available) or "Write my answer" (no speech-to-text)
        typed = page.get_by_role("button", name=re.compile("^(Type instead|Write my answer)$"))
        typed.first.wait_for(timeout=120000)
        typed.first.click()
        write = page.get_by_role("button", name="Write my answer")
        if not page.locator("textarea#answer").count() and write.count():
            write.click()
        page.locator("textarea#answer").wait_for(timeout=30000)
        page.locator("textarea#answer").fill("I enjoy backend work because I like designing APIs and data models, and in my "
                                             "last project I built a FastAPI service with tests and a CI pipeline.")
        page.get_by_role("button", name="Submit answer").click()
        page.wait_for_function("""() => [...document.querySelectorAll('ol li')].filter(li => li.textContent.includes('You:')).length >= 1""",
                               timeout=120000)
        ok("typed answer appears in the transcript", True)
        page.screenshot(path=OUT / "ci_smoke_room.png")
        api(page, f"/student/interviews/{sid}", "DELETE")

    ok("no uncaught page errors", not errors, " | ".join(errors)[:400])
    browser.close()

print(f"\n{sum(checks)}/{len(checks)} checks passed", flush=True)
sys.exit(0 if all(checks) else 1)
