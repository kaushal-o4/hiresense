"""Real-browser end-to-end test of spoken-English practice with Aria (Chromium via Playwright).

Pass 1 - "local" voice: Kokoro TTS (phoneme lip sync) + fake microphone -> local Whisper -> Aria (local LLM).
Pass 2 - "browser" voice: /api/voice/status is answered as "TTS and STT off", so the page uses the browser's
         speechSynthesis (approximate lip sync) and typed replies.
Both passes then end the session and check the score report and that the avatar, audio and mic are released.

Run (backend + frontend + Ollama running), from the backend folder:
    .\\venv\\Scripts\\python.exe tests_e2e\\english_avatar_browser.py
Uses the seeded demo student unless HS_E2E_EMAIL / HS_E2E_PASSWORD are set. Screenshots go to tests_e2e/output/.
"""
import base64
import io
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
MIC = OUT / "english_reply.wav"
BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5173")


def make_student_audio():
    """The fake microphone plays this: ~3 s of silence (hesitation), a short spoken reply, then silence."""
    if MIC.exists():
        return
    import numpy as np
    import soundfile as sf
    sys.path.insert(0, str(HERE.parent))
    from app.services import tts
    r = tts.synthesize("On weekends I usually play cricket with my friends, and sometimes I go to the market "
                       "with my mother.", voice="am_michael")
    a, sr = sf.read(io.BytesIO(base64.b64decode(r["audio_wav_b64"])), dtype="float32")
    a = np.concatenate([np.zeros(int(sr * 6), "float32"), a, np.zeros(int(sr * 12), "float32")])
    sf.write(MIC, a, sr, subtype="PCM_16")


make_student_audio()


def say(*a):
    print(*a, flush=True)


INIT = """
window.__audio = [];
const _start = AudioBufferSourceNode.prototype.start;
AudioBufferSourceNode.prototype.start = function (...args) {
  window.__audio.push({ at: performance.now(), duration: this.buffer ? this.buffer.duration : null });
  return _start.apply(this, args);
};
window.__tts = [];
if (window.speechSynthesis) {
  const _speak = window.speechSynthesis.speak.bind(window.speechSynthesis);
  window.speechSynthesis.speak = (u) => { window.__tts.push(u.text); return _speak(u); };
}
window.__gum = [];
window.__tracks = [];
const _gum = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia = async (c) => {
  window.__gum.push({ at: performance.now(), state: document.querySelector('[role=status]')?.textContent });
  const s = await _gum(c); s.getTracks().forEach((t) => window.__tracks.push(t)); return s;
};
"""

SAMPLE = """() => {
  const status = document.querySelector('[role=status]')?.textContent || '';
  const av = document.querySelector('[data-avatar-mode]');
  const w = window.__avatar3d?.visemeWeights ? window.__avatar3d.visemeWeights() : {};
  const gap = Object.entries(w).filter(([k]) => k !== 'sil').reduce((a, [, v]) => a + v, 0) * 10;
  return { status, mode: av?.dataset.avatarMode || null, gap };
}"""


def run_pass(browser, label, local_voice):
    log = []

    def wait_status(page, pattern, timeout=300):
        end = time.time() + timeout
        while time.time() < end:
            s = page.evaluate(SAMPLE)
            log.append(s)
            if re.search(pattern, s["status"]):
                return s
            page.wait_for_timeout(150)
        raise TimeoutError(f"[{label}] status never matched {pattern!r}; last={log[-1] if log else None}")

    ctx = browser.new_context(viewport={"width": 1366, "height": 900})
    ctx.add_init_script(INIT)
    page = ctx.new_page()
    page.on("console", lambda m: m.type == "error" and say("  [console error]", m.text[:200]))
    if not local_voice:
        page.route("**/api/voice/status", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(
            {"tts": {"enabled": False}, "stt": {"enabled": False}})))
    page.goto(BASE + "/login")
    creds = {"email": os.environ.get("HS_E2E_EMAIL", "student@demo.hiresense"),
             "password": os.environ.get("HS_E2E_PASSWORD", "Demo@12345")}
    page.evaluate("""async (c) => { const r = await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(c)}); if (!r.ok) throw new Error('login ' + r.status); }""", creds)

    # start from the real form
    page.goto(BASE + "/student/english")
    page.get_by_label("Practice").select_option("free_talk" if local_voice else "interview")
    page.get_by_label("Mode").select_option("voice")
    t0 = time.time()
    page.get_by_role("button", name="Start practice").click()
    page.wait_for_url(re.compile(r"/student/english/\d+$"), timeout=240000)
    sid = int(page.url.rsplit("/", 1)[1])
    say(f"[{label}] session {sid} created in {time.time() - t0:.1f}s (Aria's opening from the local LLM)")
    wait_status(page, "Ready", 60)
    assert page.evaluate("window.__gum.length") == 0, "mic must not open before Start"
    page.screenshot(path=OUT / f"en_{label}_1_ready.png")

    page.get_by_role("button", name=re.compile("Start talking")).click()
    wait_status(page, "Aria is speaking", 120)
    i0 = len(log)
    page.wait_for_timeout(1500)
    page.screenshot(path=OUT / f"en_{label}_2_speaking.png")
    sub = page.locator(".bg-brand-500").first.text_content(timeout=2000) if page.locator(".bg-brand-500").count() else None
    wait_status(page, "Your turn|Listening to you", 120)
    speaking = [s for s in log[i0:] if s["status"] == "Aria is speaking"]
    gaps = {round(s["gap"]) for s in speaking}
    say(f"[{label}] spoke; avatar modes while speaking={ {s['mode'] for s in speaking} }, distinct mouth shapes={len(gaps)}, "
        f"highlighted subtitle word={sub!r}")
    if local_voice:
        audio = page.evaluate("window.__audio")
        assert audio and audio[0]["duration"] > 1, "Kokoro audio must be played"
        assert len(gaps) >= 4, "mouth must move with the local voice"
    else:
        say(f"[{label}] browser speechSynthesis utterances: {page.evaluate('window.__tts')}")
        assert page.evaluate("window.__tts.length") >= 1, "browser voice must be used"
    gum = page.evaluate("window.__gum")
    assert all("speaking" not in (g["state"] or "").lower() for g in gum), "mic must not open while Aria speaks"

    if local_voice:
        wait_status(page, "Listening to you", 30)
        say(f"[{label}] mic auto-opened (hands-free)")
        page.get_by_text("No rush - take a breath").wait_for(timeout=12000)
        say(f"[{label}] hesitation helpers highlighted after ~5 s of silence")
        page.screenshot(path=OUT / f"en_{label}_3_hesitation.png")
        wait_status(page, "Catching your words|Aria is thinking", 90)
        say(f"[{label}] recording auto-stopped after the student's pause")
        t1 = time.time()
        wait_status(page, "Aria is speaking", 300)
        say(f"[{label}] transcribed + Aria replied + speaking after {time.time() - t1:.1f}s")
    else:
        # Local STT is "off", so the page tries the browser's recognition. Playwright's Chromium has no speech
        # service, so it must fail visibly and fall back to typing (if the API is missing, typing is shown directly).
        box = page.get_by_label("Your reply")
        try:
            box.wait_for(timeout=30000)
        except Exception:
            page.get_by_role("button", name="Type").click()
        notice = page.locator(".bg-amber-50").first.text_content() if page.locator(".bg-amber-50").count() else None
        say(f"[{label}] typing fallback shown; notice={notice!r}")
        box.fill("I has worked on a attendance app in my college using React and Python.")
        page.get_by_label("Send").click()
        wait_status(page, "Aria is thinking", 15)
        t1 = time.time()
        wait_status(page, "Aria is speaking", 300)
        say(f"[{label}] typed reply -> Aria replied + speaking after {time.time() - t1:.1f}s")

    timings = page.evaluate("""() => performance.getEntriesByType('resource')
      .filter(e => /transcribe|\\/message|voice\\/speak/.test(e.name))
      .map(e => [e.name.replace(/^.*\\/api\\//, ''), Math.round(e.duration / 100) / 10])""")
    say(f"[{label}] request seconds: {timings}")
    detail = page.evaluate(f"fetch('/api/student/english/{sid}').then(r=>r.json())")
    stu, ai = detail["messages"][-2], detail["messages"][-1]
    say(f"[{label}] student ({stu['input_mode']}): {stu['content']!r}")
    say(f"[{label}] corrections: {stu['corrections']}")
    say(f"[{label}] Aria: {ai['content']!r}")
    say(f"[{label}] meta: {ai['meta']}")
    say(f"[{label}] confidence={detail['confidence']} live_active_seconds={detail['live_active_seconds']}")
    assert ai["meta"]["avatar_mode"] in ("speaking", "encouraging")
    assert not re.search("[\U0001F000-\U0001FAFF☀-➿]", ai["content"]), "no emoji in spoken text"
    assert detail["live_active_seconds"] > 0, "verified time must increase after a real reply"
    page.wait_for_timeout(1200)
    page.screenshot(path=OUT / f"en_{label}_4_reply.png")

    # end -> report; avatar/audio/mic released
    page.get_by_role("button", name=re.compile("End & get feedback")).click()
    page.get_by_role("button", name="Confirm").click()
    page.get_by_text("Your scores").wait_for(timeout=300000)
    page.screenshot(path=OUT / f"en_{label}_5_report.png", full_page=True)
    final = page.evaluate(f"fetch('/api/student/english/{sid}').then(r=>r.json())")
    live_tracks = page.evaluate("window.__tracks.filter(t => t.readyState === 'live').length")
    avatar_gone = page.locator("[data-avatar-mode]").count() == 0
    say(f"[{label}] ended: status={final['status']} active_seconds={final['active_seconds']} scores={final['scores']} "
        f"overall={final['overall_score']}")
    say(f"[{label}] after end: avatar unmounted={avatar_gone}, live mic tracks={live_tracks}, "
        f"speechSynthesis speaking={page.evaluate('!!window.speechSynthesis?.speaking')}")
    assert final["status"] == "completed" and avatar_gone and live_tracks == 0
    assert {"fluency", "vocabulary", "grammar", "sentence_formation"} <= set(final["scores"] or {})
    ctx.close()


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=[
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
        f"--use-file-for-fake-audio-capture={MIC}", "--autoplay-policy=no-user-gesture-required"])
    passes = sys.argv[1:] or ["local", "browser"]
    for name in passes:
        run_pass(browser, name, local_voice=name == "local")
    browser.close()
    say("ALL OK")
