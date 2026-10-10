"""Real-browser end-to-end test of the live voice interview (Chromium via Playwright).

The microphone is Chromium's fake capture device fed with a WAV of a spoken answer, so the whole pipeline runs:
mic -> AudioWorklet recorder -> WAV upload -> local Whisper -> review -> existing answer API -> local LLM ->
next question -> local TTS -> avatar lip sync.

Run (backend + frontend + Ollama running), from the backend folder:
    .\\venv\\Scripts\\python.exe -m pip install playwright
    .\\venv\\Scripts\\python.exe -m playwright install chromium
    .\\venv\\Scripts\\python.exe tests_e2e\\voice_interview_browser.py
Uses the seeded demo student unless HS_E2E_EMAIL / HS_E2E_PASSWORD are set. Screenshots go to tests_e2e/output/.
"""
import base64
import io
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
log = []


def make_candidate_audio():
    """The fake microphone plays this WAV: a spoken answer made with a different local voice, plus pauses."""
    if MIC.exists():
        return
    import numpy as np
    import soundfile as sf
    sys.path.insert(0, str(HERE.parent))
    from app.services import tts
    r = tts.synthesize("In my placement tracker project I used Python with Flask for the backend and React for the "
                       "frontend. I designed REST endpoints for students and companies, and I stored the data in a "
                       "SQL database with proper indexes.", voice="am_michael")
    a, sr = sf.read(io.BytesIO(base64.b64decode(r["audio_wav_b64"])), dtype="float32")
    a = np.concatenate([np.zeros(int(sr * 1.5), "float32"), a, np.zeros(int(sr * 8), "float32")])
    sf.write(MIC, a, sr, subtype="PCM_16")


make_candidate_audio()
MIC = str(MIC)


def say(*a):
    print(*a, flush=True)


INIT = """
window.__audio = [];
const _start = AudioBufferSourceNode.prototype.start;
AudioBufferSourceNode.prototype.start = function (...args) {
  window.__audio.push({ at: performance.now(), duration: this.buffer ? this.buffer.duration : null });
  return _start.apply(this, args);
};
window.__gum = [];
const _gum = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia = (c) => { window.__gum.push({ at: performance.now(), audio: !!c.audio, video: !!c.video,
  state: document.querySelector('[role=status]')?.textContent }); return _gum(c); };
"""

SAMPLE = """() => {
  const status = document.querySelector('[role=status]')?.textContent || '';
  const av = document.querySelector('[data-avatar-mode]');
  // 3D avatar: mouth openness = total weight of non-silent visemes (x10, comparable to the old 2D "gap" in px)
  const w = window.__avatar3d?.visemeWeights ? window.__avatar3d.visemeWeights() : {};
  const gap = Object.entries(w).filter(([k]) => k !== 'sil').reduce((a, [, v]) => a + v, 0) * 10;
  return { t: performance.now(), status, mode: av?.dataset.avatarMode, gap, avatar: window.__avatar3d?.status };
}"""


def wait_status(page, pattern, timeout=300, sample=True):
    """Poll the status badge until it matches `pattern`, sampling the avatar meanwhile."""
    end = time.time() + timeout
    while time.time() < end:
        s = page.evaluate(SAMPLE)
        if sample:
            log.append(s)
        if re.search(pattern, s["status"]):
            return s
        page.wait_for_timeout(150)
    raise TimeoutError(f"status never matched {pattern!r}; last={log[-1]['status'] if log else None}")


def mouth_stats(samples):
    gaps = [s["gap"] for s in samples]
    return {"n": len(gaps), "min": round(min(gaps), 1), "max": round(max(gaps), 1),
            "distinct": len({round(g) for g in gaps}), "open_frac": round(sum(g > 2 for g in gaps) / len(gaps), 2)}


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=[
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
        f"--use-file-for-fake-audio-capture={MIC}", "--autoplay-policy=no-user-gesture-required"])
    ctx = browser.new_context(viewport={"width": 1366, "height": 900})
    ctx.add_init_script(INIT)
    page = ctx.new_page()
    page.on("console", lambda m: m.type == "error" and say("  [console error]", m.text[:200]))
    page.goto(BASE + "/login")
    creds = {"email": os.environ.get("HS_E2E_EMAIL", "student@demo.hiresense"),
             "password": os.environ.get("HS_E2E_PASSWORD", "Demo@12345")}  # seeded demo account (see README)
    page.evaluate("""async (c) => { const r = await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(c)}); if (!r.ok) throw new Error('login ' + r.status); }""", creds)
    sess = page.evaluate("""async () => { const r = await fetch('/api/student/interviews', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({job_role:'Backend Developer', category:'technical', mode:'voice', question_count:3, difficulty:'medium'})});
      return r.json(); }""")
    sid = sess["session"]["id"]
    say(f"interview {sid} created; source={sess['session']['question_source']}")
    say("Q1:", sess["session"]["questions"][0]["text"])

    page.goto(f"{BASE}/student/interviews/{sid}/live")
    wait_status(page, "Ready", 60)
    page.screenshot(path=OUT / "1_ready.png")
    assert page.evaluate("window.__gum.length") == 0, "microphone must not open before consent"
    say("[ok] avatar loaded, consent screen shown, mic NOT opened before start")

    t0 = time.time()
    page.get_by_role("button", name=re.compile("start the interview")).click()
    wait_status(page, "Interviewer speaking", 120)
    say(f"[ok] speaking after {time.time() - t0:.1f}s (TTS)")
    page.wait_for_timeout(1200)
    page.screenshot(path=OUT / "2_speaking.png")
    stage = page.locator('[data-avatar-status]').bounding_box()
    for i in range(6):
        page.screenshot(path=OUT / f"speaking_{i}.png", clip=stage, animations="allow")
        page.wait_for_timeout(150)
    start_idx = len(log)
    wait_status(page, "Recording your answer|Your turn", 120)
    speaking = [s for s in log[start_idx:] if s["status"] == "Interviewer speaking"]
    audio = page.evaluate("window.__audio")
    gum = page.evaluate("window.__gum")
    say("[ok] audio buffers played:", [round(a["duration"], 2) for a in audio])
    say("     mouth while speaking:", mouth_stats(speaking))
    say("     mic opened in state:", [g["state"] for g in gum])
    assert audio and audio[0]["duration"] > 1, "question audio must actually be played"
    assert mouth_stats(speaking)["distinct"] >= 5, "mouth must move while speaking"
    assert all("speaking" not in (g["state"] or "").lower() for g in gum), "mic must not open while speaking"

    wait_status(page, "Recording your answer", 30)
    page.wait_for_timeout(4000)
    rec = [s for s in log if s["status"] == "Recording your answer"]
    page.screenshot(path=OUT / "3_listening.png")
    say("[ok] recording; avatar mode while listening:", {s["mode"] for s in rec}, "mouth", mouth_stats(rec))
    wait_status(page, "Transcribing", 90)
    say("[ok] recording auto-stopped after the candidate's pause")
    wait_status(page, "Review your answer", 120)
    transcript = page.locator("#answer").input_value()
    say("[ok] transcript:", transcript)
    page.screenshot(path=OUT / "4_review.png")
    assert len(transcript.split()) > 10

    page.get_by_role("button", name="Submit answer").click()
    page.get_by_role("button", name="Submit answer").click(force=True, timeout=1000, no_wait_after=True) \
        if page.get_by_role("button", name="Submit answer").count() else None   # double-click attempt
    wait_status(page, "Evaluating", 30)
    t1 = time.time()
    wait_status(page, "Interviewer speaking", 240)
    say(f"[ok] evaluated + next question generated + spoken after {time.time() - t1:.1f}s")
    detail = page.evaluate(f"fetch('/api/student/interviews/{sid}').then(r=>r.json())")
    q1 = detail["questions"][0]
    say("     Q1 saved answer:", q1["answer"]["input_mode"], "| score", q1["answer"]["score"],
        "| next level", (q1["answer"]["details"] or {}).get("next_difficulty"))
    say("     Q2:", detail["questions"][1]["text"], f"[{detail['questions'][1]['difficulty']}]")
    assert len(detail["questions"]) == 2, "exactly one answer stored (no duplicate submission)"

    # pause while speaking -> audio stops, mouth closes; resume -> question replayed
    page.wait_for_timeout(800)
    n_audio = len(page.evaluate("window.__audio"))
    page.get_by_role("button", name="Pause").click()
    wait_status(page, "Paused", 10)
    page.wait_for_timeout(700)
    paused = page.evaluate(SAMPLE)
    say("[ok] paused: mode", paused["mode"], "mouth gap", round(paused["gap"], 1))
    assert paused["gap"] < 1.5
    page.get_by_role("button", name="Resume").click()
    wait_status(page, "Interviewer speaking", 60)
    say("[ok] resumed -> question replayed; audio buffers now", len(page.evaluate("window.__audio")), "(was", n_audio, ")")

    # Q2: typed-answer fallback
    wait_status(page, "Recording your answer|Your turn", 120)
    page.get_by_role("button", name="Type instead").click()
    wait_status(page, "Review your answer", 10)
    page.locator("#answer").fill("I would add an index on the columns used in WHERE and JOIN clauses, check the query plan "
                                 "with EXPLAIN, and avoid SELECT star so the database reads less data.")
    page.get_by_role("button", name="Submit answer").click()
    wait_status(page, "Evaluating", 30)
    wait_status(page, "Interviewer speaking", 240)
    say("[ok] typed answer accepted, Q3 spoken")

    # Q3: voice again, then finish
    wait_status(page, "Recording your answer", 120)
    wait_status(page, "Review your answer", 180)
    page.get_by_role("button", name="Submit answer").click()
    wait_status(page, "All questions answered", 240)
    page.wait_for_timeout(1500)
    page.screenshot(path=OUT / "5_wrapup.png")
    page.get_by_role("button", name=re.compile("Finish")).click()
    page.get_by_text("Question-by-question feedback").wait_for(timeout=300000)
    page.screenshot(path=OUT / "6_report.png", full_page=True)
    final = page.evaluate(f"fetch('/api/student/interviews/{sid}').then(r=>r.json())")
    say(f"[ok] completed: status={final['status']} overall={final['overall_score']} report={final['report_status']}")
    say("     answers:", [(q["answer"]["input_mode"], q["answer"]["score"]) for q in final["questions"]])
    gum = page.evaluate("window.__gum")
    say("     microphone opened", len(gum), "times, states:", [g["state"] for g in gum], "| video requested:",
        any(g["video"] for g in gum))
    browser.close()

