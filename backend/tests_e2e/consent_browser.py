"""Real-browser check of the hosted-AI consent flow (cloud profile, LOCAL_AI_PROVIDER=gemini).

Needs a backend started with LOCAL_AI_PROVIDER=gemini (a Gemini key is not needed: the AI is reported offline and
interviews use the question bank) and the frontend pointing at it. Example (two terminals, from backend):
    set LOCAL_AI_PROVIDER=gemini& set GEMINI_API_KEY=& set MONGODB_DB=hiresense_e2e_consent
    .\\venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8023
    (frontend) set HS_API=http://127.0.0.1:8023& npx vite --port 5193
    set HS_E2E_BASE=http://localhost:5193& .\\venv\\Scripts\\python.exe tests_e2e\\consent_browser.py
Checks: the register checkbox and /privacy say Google; without consent the interview page shows the notice and the
API refuses to start (428); "I agree" removes it; the Settings toggle withdraws it again.
"""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)
BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5193")
EMAIL = f"e2e-consent-{int(time.time())}@test.dev"
results = []


def ok(name, cond, detail=""):
    results.append(bool(cond))
    print("[ok]  " if cond else "[FAIL]", name, detail)


START = """async () => (await fetch('/api/student/interviews', {method: 'POST', credentials: 'include',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({job_role: 'Developer', category: 'technical', mode: 'text', question_count: 3})})).status"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_context(viewport={"width": 1366, "height": 900}).new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)[:200]))

    page.goto(BASE + "/privacy")
    page.wait_for_selector("text=Privacy notice")
    ok("/privacy names Google Gemini", page.locator("text=Google Gemini").count() > 0)

    page.goto(BASE + "/register")
    page.wait_for_selector("text=Create account")
    box = page.locator("text=processed by Google Gemini")
    ok("register page shows the optional Gemini consent", box.count() == 1)
    page.screenshot(path=str(OUT / "consent_register.png"))
    # register through the API (the form layout is covered by account_browser.py), without consent
    st = page.evaluate("""async (b) => (await fetch('/api/auth/register/student', {method: 'POST', credentials: 'include',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)})).status""",
                       {"full_name": "E2E Consent", "email": EMAIL, "password": "Passw0rd!x"})
    ok("registered without consent", st == 201, EMAIL)

    page.goto(BASE + "/student/interviews")
    page.wait_for_selector("text=your data is processed by Google", timeout=15000)
    ok("interview page shows the notice", True)
    ok("API refuses an interview without consent", page.evaluate(START) == 428)
    page.screenshot(path=str(OUT / "consent_gate.png"))
    page.click("button:has-text('I agree')")
    page.wait_for_selector("text=your data is processed by Google", state="detached", timeout=10000)
    ok("notice disappears after agreeing", True)
    ok("API starts an interview after consent", page.evaluate(START) == 201)

    page.goto(BASE + "/student/resume")
    page.wait_for_selector("text=Resume analysis")
    ok("resume page has no notice after consent", page.locator("text=your data is processed by Google").count() == 0)

    page.goto(BASE + "/settings")
    toggle = page.locator("button[role='switch'][aria-label='Allow processing by Google Gemini']")
    toggle.wait_for(timeout=10000)
    ok("settings toggle shows consent on", toggle.get_attribute("aria-checked") == "true")
    toggle.click()
    page.wait_for_selector("text=Not agreed", timeout=10000)
    ok("withdrawn in settings", page.evaluate(START) == 428)
    page.screenshot(path=str(OUT / "consent_settings.png"))

    ok("no page errors", not errors, "; ".join(errors))
    browser.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
