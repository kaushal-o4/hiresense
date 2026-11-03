"""Real-browser check of the account features and the merged student pages.

Covers: forgot password -> reset link -> new password works (old one doesn't), the merged "My Progress" and
"Jobs & Drives" pages (old URLs redirect to the right tab), and "Delete my account".
Email is off in development, so the reset token is created here the same way the server does (same secret, same
database). Run from backend with the backend + frontend running:
    .\\venv\\Scripts\\python.exe tests_e2e\\account_browser.py
"""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.odm import select  # noqa: E402
from app.security import create_reset_token  # noqa: E402

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)
BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5173")
EMAIL = f"e2e-account-{int(time.time())}@test.dev"
OLD_PW, NEW_PW = "FirstPassw0rd", "SecondPassw0rd"
results = []


def ok(name, cond, detail=""):
    results.append(bool(cond))
    print("[ok]  " if cond else "[FAIL]", name, detail)


def reset_token(email):
    db = SessionLocal()
    try:
        u = db.scalar(select(User).where(User.email == email))
        return create_reset_token(u.id, u.password_hash)
    finally:
        db.close()


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_context(viewport={"width": 1366, "height": 900}).new_page()
    page.on("pageerror", lambda e: print("  [pageerror]", str(e)[:200]))

    # register (API) and sign out
    page.goto(BASE + "/login")
    r = page.evaluate("""async (b) => (await fetch('/api/auth/register/student', {method: 'POST', credentials: 'include',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)})).status""",
                      {"full_name": "E2E Account", "email": EMAIL, "password": OLD_PW, "college": "Test College",
                       "branch": "CSE", "graduation_year": 2027})
    ok("test student registered", r == 201, EMAIL)
    page.evaluate("fetch('/api/auth/logout', {method: 'POST', credentials: 'include'})")
    page.goto(BASE + "/login")

    # ---- forgot password
    page.get_by_role("link", name="Forgot password?").click()
    page.wait_for_url("**/forgot-password")
    page.get_by_label("Email").fill(EMAIL)
    page.get_by_role("button", name="Send reset link").click()
    page.get_by_text("If an account exists for that email").wait_for(timeout=10000)
    ok("forgot password gives the same neutral reply", True)
    page.wait_for_timeout(800)  # let the page fade-in animation finish
    page.screenshot(path=OUT / "acc_1_forgot.png")

    # ---- reset with a real token
    page.goto(f"{BASE}/reset-password?token={reset_token(EMAIL)}")
    page.get_by_label("New password", exact=True).fill(NEW_PW)
    page.get_by_label("Confirm new password").fill("different1")
    page.get_by_role("button", name="Save new password").click()
    ok("mismatched passwords are caught", page.get_by_text("do not match").is_visible())
    page.get_by_label("Confirm new password").fill(NEW_PW)
    page.get_by_role("button", name="Save new password").click()
    page.get_by_text("Password updated").wait_for(timeout=10000)
    ok("reset link sets a new password", True)
    page.wait_for_timeout(800)  # let the page fade-in animation finish
    page.screenshot(path=OUT / "acc_2_reset_done.png")
    page.get_by_role("link", name="Sign in").click()
    page.get_by_label("Email").fill(EMAIL)
    page.get_by_label("Password").fill(OLD_PW)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_timeout(1200)
    ok("old password no longer works", "/login" in page.url)
    page.get_by_label("Password").fill(NEW_PW)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url("**/student", timeout=15000)
    ok("signed in with the new password", True)

    # ---- merged navigation
    nav = page.locator("nav").first.inner_text()
    ok("menu shows 'My progress' and 'Jobs & drives'", "My progress" in nav and "Jobs & drives" in nav)
    ok("old separate menu items are gone",
       not any(x in nav for x in ("Performance Report", "Practice History", "Placement Drives")))
    page.goto(BASE + "/student/report")
    page.wait_for_url("**/student/progress?tab=report", timeout=10000)
    ok("/student/report opens the 'Full report' tab",
       page.get_by_role("tab", name="Full report").get_attribute("aria-selected") == "true")
    page.get_by_role("tab", name="Practice history").click()
    page.get_by_text("Practice history").first.wait_for()
    ok("progress tabs switch and update the URL", "tab=history" in page.url)
    page.goto(BASE + "/student/drives")
    page.wait_for_url("**/student/jobs?tab=drives", timeout=10000)
    ok("/student/drives opens the 'Placement drives' tab",
       page.get_by_role("tab", name="Placement drives").get_attribute("aria-selected") == "true")
    page.wait_for_timeout(800)  # let the page fade-in animation finish
    page.screenshot(path=OUT / "acc_3_jobs_drives.png")

    # ---- delete account
    page.goto(BASE + "/settings")
    card = page.locator("section", has_text="Delete my account")
    btn = card.get_by_role("button", name="Permanently delete my account")
    card.get_by_label("Your password").fill(NEW_PW)
    ok("delete stays disabled until DELETE is typed", btn.is_disabled())
    card.get_by_label('Type "DELETE" to confirm').fill("DELETE")
    page.wait_for_timeout(800)  # let the page fade-in animation finish
    page.screenshot(path=OUT / "acc_4_delete.png")
    btn.click()
    page.wait_for_url("**/login", timeout=15000)
    ok("deleting signs the student out", True)
    page.get_by_label("Email").fill(EMAIL)
    page.get_by_label("Password").fill(NEW_PW)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_timeout(1200)
    ok("deleted account can't sign in", "/login" in page.url)
    browser.close()

print(f"{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
