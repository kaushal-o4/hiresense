"""Browser check: the realistic 3D interviewer loads, has its viseme blendshapes, and renders.

Saves tests_e2e/output/avatar_idle.png (and avatar_speaking_*.png if --speak).
Run from backend: .\\venv\\Scripts\\python.exe tests_e2e\\avatar_snapshot.py [--speak]
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)
BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5173")
CREDS = {"email": os.environ.get("HS_E2E_EMAIL", "student@demo.hiresense"),
         "password": os.environ.get("HS_E2E_PASSWORD", "Demo@12345")}

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                                "--autoplay-policy=no-user-gesture-required"])
    page = b.new_context(viewport={"width": 1366, "height": 900}).new_page()
    page.on("console", lambda m: m.type == "error" and print("  [console]", m.text[:200]))
    page.goto(BASE + "/login")
    page.evaluate("""async (c) => { await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(c)}); }""", CREDS)
    s = page.evaluate("""() => fetch('/api/student/interviews', {method:'POST', headers:{'Content-Type':'application/json'},
       body: JSON.stringify({job_role:'Backend Developer', category:'hr', mode:'voice', question_count:3})}).then(r => r.json())""")
    sid = s["session"]["id"]
    try:
        page.goto(f"{BASE}/student/interviews/{sid}/live")
        page.wait_for_function("window.__avatar3d && window.__avatar3d.status !== 'loading'", timeout=60000)
        info = page.evaluate("window.__avatar3d")
        print("avatar:", info)
        assert info["status"] == "ready" and info["visemes"] == 15
        page.wait_for_timeout(1500)
        page.screenshot(path=OUT / "avatar_idle.png", clip=page.locator("[data-avatar-status]").bounding_box(), animations="allow")
        if "--speak" in sys.argv:
            agree = page.get_by_label("I have read what is monitored")  # monitoring notice (security module)
            if agree.count():
                agree.check()
            page.get_by_role("button", name="I agree - start the interview").click()
            try:
                page.wait_for_function("document.querySelector('[data-avatar-mode]')?.dataset.avatarMode === 'speaking'", timeout=90000)
            except Exception:
                print("stuck at:", page.evaluate("document.querySelector('[role=status]')?.textContent"), "| notice:", page.evaluate("[...document.querySelectorAll('main *')].map(e=>e.textContent).find(t=>/unavailable|error|could not/i.test(t||'')) || null"))
                raise
            for i in range(4):
                page.wait_for_timeout(350)
                page.screenshot(path=OUT / f"avatar_speaking_{i}.png", clip=page.locator("[data-avatar-status]").bounding_box(), animations="allow")
        print("[ok] 3D avatar rendered; screenshots in", OUT)
    finally:
        page.evaluate(f"fetch('/api/student/interviews/{sid}', {{method:'DELETE'}})")
        b.close()



