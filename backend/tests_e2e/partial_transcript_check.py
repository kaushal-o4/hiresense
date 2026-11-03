"""Live partial transcript check (real Whisper + Kokoro + Ollama, Chromium fake microphone).

The fake microphone plays an answer with natural pauses between sentences (Kokoro's own ~1.2 s plus 0.4 s; ~1.6 s of detected quiet): hand a finished piece to Whisper while the candidate keeps talking (segment pause 0.6 s), shorter than the Fast
mode end-of-answer pause (1.0 s). Checks that "Heard so far" text appears DURING recording, that the final
transcript keeps all sentences in order, and how long the transcript takes after the candidate stops.
Run (servers running), from the backend folder:  .\\venv\\Scripts\\python.exe tests_e2e\\partial_transcript_check.py
"""
import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
OUT = HERE / "output"
WAV = OUT / "candidate_answer_pauses.wav"
BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5173")
SENTENCES = [
    "In my placement tracker project I built the backend with Python and Flask, and the frontend with React.",
    "I designed REST endpoints for students and companies, and I returned clear status codes for every error.",
    "For the database I used PostgreSQL, and I added indexes on the columns used in searches and joins.",
]
if not WAV.exists():
    from app.services import tts
    parts = []
    sr = 24000
    for s in SENTENCES:
        a, sr = sf.read(io.BytesIO(base64.b64decode(tts.synthesize(s, voice="am_michael")["audio_wav_b64"])), dtype="float32")
        parts += [a, np.zeros(int(sr * 0.4), "float32")]
    audio = np.concatenate([np.zeros(int(sr * 1.5), "float32"), *parts[:-1], np.zeros(int(sr * 10), "float32")])
    sf.write(WAV, audio, sr, subtype="PCM_16")
    print(f"made {WAV.name}: {len(audio) / sr:.1f} s", flush=True)

checks = []


def ok(name, cond, detail=""):
    checks.append({"check": name, "passed": bool(cond), "detail": detail})
    print(("[ok]  " if cond else "[FAIL]"), name, detail, flush=True)


STATUS = "() => document.querySelector('[role=status]')?.textContent || ''"
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=[
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", f"--use-file-for-fake-audio-capture={WAV}",
        "--autoplay-policy=no-user-gesture-required", "--disable-webgl", "--disable-3d-apis"])
    page = browser.new_page(viewport={"width": 1366, "height": 1000})
    page.goto(BASE + "/login")
    # Demo accounts no longer exist (MongoDB migration): register this test student on first use. Run against a
    # throwaway database (MONGODB_DB=hiresense_e2e_test), never the real one.
    page.evaluate("""async (c) => { let r = await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email: c.email, password: c.password})});
      if (!r.ok) r = await fetch('/api/auth/register/student', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({...c, full_name: 'E2E Student', college: 'ABC College', branch: 'Computer Science', graduation_year: 2027})});
      if (!r.ok) throw new Error('login ' + r.status); }""",
                  {"email": os.environ.get("HS_E2E_EMAIL", "e2e.student@test.dev"),
                   "password": os.environ.get("HS_E2E_PASSWORD", "Passw0rd!")})
    # Review the transcript instead of sending it automatically (the new default), so it can be checked here.
    page.evaluate("""() => localStorage.setItem('hs-room-settings', JSON.stringify({v: 2, autoSend: false}))""")
    page.evaluate("""async () => { const r = await fetch('/api/student/interviews?status=in_progress&page_size=50');
      for (const s of (await r.json()).items) await fetch('/api/student/interviews/' + s.id, {method: 'DELETE'}); }""")
    sid = page.evaluate("""async () => (await (await fetch('/api/student/interviews', {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({job_role: 'Backend Developer', mode: 'voice',
      question_count: 3, defer_first_question: true})})).json()).session.id""")
    page.goto(f"{BASE}/student/interviews/{sid}/live")
    page.get_by_text("Camera and interview monitoring").wait_for(timeout=60000)
    page.get_by_role("button", name=re.compile("Test my camera")).click()  # camera is required by default
    page.get_by_text("Working").first.wait_for(timeout=30000)
    agree = page.get_by_label("I have read what is monitored")  # monitoring notice (security module)
    if agree.count():
        agree.check()
    page.get_by_role("button", name=re.compile("start the interview")).click()

    end = time.time() + 240
    while time.time() < end and not re.search("Recording", page.evaluate(STATUS)):
        page.wait_for_timeout(200)
    t_rec = time.time()
    heard, heard_at, updates = "", None, []
    while time.time() < end and re.search("Recording", page.evaluate(STATUS)):
        body = page.inner_text("body")
        m = re.search(r"Heard so far:\s*(.+)", body)
        if m and not heard_at:
            heard_at = time.time() - t_rec
        if m and m.group(1)[:300] != heard:
            heard = m.group(1)[:300]
            updates.append(round(time.time() - t_rec, 1))
        page.wait_for_timeout(150)
    t_stop = time.time()
    while time.time() < end and not re.search("Review your answer", page.evaluate(STATUS)):
        page.wait_for_timeout(100)
    after_stop = time.time() - t_stop
    draft = page.locator("#answer").input_value()
    ok("partial transcript shown while still speaking", bool(heard_at), f"first after {heard_at and round(heard_at, 1)} s: {heard[:90]!r}")
    ok("live captions update while speaking (not only at long pauses)", len(updates) >= 4, f"updates at {updates} s")
    order = [draft.lower().find(k) for k in ("flask", "status codes", "postgres")]
    ok("final transcript has every sentence, in order", all(i >= 0 for i in order) and order == sorted(order), draft[:160])
    ok("not cut off at the pauses between sentences", "postgres" in draft.lower())
    print(f"transcript ready {after_stop:.1f} s after recording stopped (only the last piece was left to transcribe)")
    page.get_by_role("button", name="End", exact=True).click()
    page.get_by_role("button", name="Confirm", exact=True).click()
    page.wait_for_timeout(1500)
    browser.close()

(OUT / "partial_transcript_check.json").write_text(json.dumps({"checks": checks, "after_stop_s": round(after_stop, 2),
                                                             "caption_updates_s": updates}, indent=2))
failed = [c for c in checks if not c["passed"]]
print(f"{len(checks) - len(failed)}/{len(checks)} checks passed")
sys.exit(1 if failed else 0)
