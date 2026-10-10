"""Browser check: the optional camera preview starts only on click and is released on "Hide".

Uses Chromium's fake camera. Run from the backend folder: .\\venv\\Scripts\\python.exe tests_e2e\\camera_preview_browser.py
"""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)
BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5173")
CREDS = {"email": os.environ.get("HS_E2E_EMAIL", "student@demo.hiresense"),
         "password": os.environ.get("HS_E2E_PASSWORD", "Demo@12345")}

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
    page = b.new_context(viewport={"width": 1366, "height": 900}).new_page()
    page.goto(BASE + "/login")
    page.evaluate("""async (c) => { await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(c)}); }""", CREDS)
    s = page.evaluate("""() => fetch('/api/student/interviews', {method:'POST', headers:{'Content-Type':'application/json'},
       body: JSON.stringify({job_role:'Frontend Developer', category:'hr', mode:'voice', question_count:3})}).then(r => r.json())""")
    sid = s["session"]["id"]
    page.goto(f"{BASE}/student/interviews/{sid}/live")
    page.get_by_text("Before we start").wait_for()
    assert page.locator("video").count() == 0, "camera must not start automatically"
    page.get_by_role("button", name="Show my camera (optional)").click()
    page.locator("video").wait_for()
    page.wait_for_timeout(1500)
    assert page.evaluate("(() => { const v = document.querySelector('video'); return v.videoWidth > 0 && !v.paused; })()")
    page.screenshot(path=OUT / "camera_preview.png")
    page.get_by_role("button", name="Hide my camera").click()
    page.wait_for_timeout(300)
    assert page.locator("video").count() == 0
    print("[ok] camera: off by default, shown only after click, removed on hide")
    page.evaluate(f"fetch('/api/student/interviews/{sid}', {{method:'DELETE'}})")
    b.close()
