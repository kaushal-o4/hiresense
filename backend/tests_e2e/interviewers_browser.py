"""Real-browser end-to-end test of the multi-interviewer experience (Chromium via Playwright).

1. Selection screen: 4 interviewer cards with live 3D previews, filters, a voice preview that is lip-synced.
2. Full VOICE interview with Victor: his own 3D model and voice, greeting -> speaking -> listening -> reaction ->
   thinking states, mouth moving only with audio, true pause/resume, fake-microphone answer transcribed by local
   Whisper, a real follow-up from the local LLM, report with skill breakdown + Victor's spoken closing remarks,
   and microphone/audio released at the end.
3. Stress interview with Marcus: the answer is stopped at the (shortened, test-only) time limit and stored as
   interrupted.

Run (backend + frontend + Ollama running), from the backend folder:
    .\\venv\\Scripts\\python.exe tests_e2e\\interviewers_browser.py
Uses the seeded demo student unless HS_E2E_EMAIL / HS_E2E_PASSWORD are set. Screenshots go to tests_e2e/output/.
"""
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)
MIC = OUT / "candidate_answer.wav"  # made by voice_interview_browser.py (spoken answer about a Flask project)
BASE = os.environ.get("HS_E2E_BASE", "http://localhost:5173")
if not MIC.exists():
    sys.exit("Run tests_e2e/voice_interview_browser.py once first: it creates output/candidate_answer.wav")


def say(*a):
    print(*a, flush=True)


INIT = """
window.__audio = [];
const _start = AudioBufferSourceNode.prototype.start;
AudioBufferSourceNode.prototype.start = function (...args) {
  window.__audio.push({ at: performance.now(), duration: this.buffer ? this.buffer.duration : null });
  return _start.apply(this, args);
};
window.__gum = []; window.__tracks = [];
const _gum = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia = async (c) => {
  window.__gum.push({ at: performance.now(), state: document.querySelector('[role=status]')?.textContent });
  const s = await _gum(c); s.getTracks().forEach((t) => window.__tracks.push(t)); return s;
};
"""
SAMPLE = """() => {
  const status = document.querySelector('[role=status]')?.textContent || '';
  const av = document.querySelector('[data-avatar-mode][data-interviewer]');
  const w = window.__avatar3d?.visemeWeights ? window.__avatar3d.visemeWeights() : {};
  const gap = Object.entries(w).filter(([k]) => k !== 'sil').reduce((a, [, v]) => a + v, 0) * 10;
  return { status, mode: av?.dataset.avatarMode || null, who: av?.dataset.interviewer || null, gap,
           model: window.__avatar3d?.model, audio: window.__audio.length };
}"""


def main():
    log = []

    def wait_status(page, pattern, timeout=300):
        end = time.time() + timeout
        while time.time() < end:
            s = page.evaluate(SAMPLE)
            log.append(s)
            if re.search(pattern, s["status"]):
                return s
            page.wait_for_timeout(120)
        raise TimeoutError(f"status never matched {pattern!r}; last={log[-1] if log else None}")

    def login(ctx):
        page = ctx.new_page()
        page.on("console", lambda m: m.type == "error" and "401" not in m.text and say("  [console error]", m.text[:200]))
        page.goto(BASE + "/login")
        creds = {"email": os.environ.get("HS_E2E_EMAIL", "student@demo.hiresense"),
                 "password": os.environ.get("HS_E2E_PASSWORD", "Demo@12345")}
        page.evaluate("""async (c) => { const r = await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify(c)}); if (!r.ok) throw new Error('login ' + r.status); }""", creds)
        for s in page.evaluate("fetch('/api/student/interviews?status=in_progress&page_size=50').then(r=>r.json())")["items"]:
            page.evaluate(f"fetch('/api/student/interviews/{s['id']}', {{method:'DELETE'}})")
        return page

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-audio-capture={MIC}", "--autoplay-policy=no-user-gesture-required",
            "--enable-unsafe-swiftshader"])

        # ------------------------------------------------------------ 1. selection screen
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        ctx.add_init_script(INIT)
        page = login(ctx)
        page.goto(BASE + "/student/interviews")
        page.locator("[data-interviewer-card]").first.wait_for(timeout=30000)
        cards = page.locator("[data-interviewer-card]")
        assert cards.count() == 4, cards.count()
        names = [cards.nth(i).locator("h3").text_content() for i in range(4)]
        page.wait_for_function("document.querySelectorAll('[data-interviewer-card] [data-avatar-status=ready]').length === 4",
                               timeout=120000)
        say("[ok] selection screen: cards", names, "- all 4 live 3D previews rendered")
        page.screenshot(path=OUT / "iv_1_selection.png", full_page=True)
        page.get_by_role("button", name="Stress Interview").click()
        assert page.locator("[data-interviewer-card]").count() == 1 and "Marcus" in page.locator("[data-interviewer-card] h3").text_content()
        page.get_by_role("button", name="English Confidence Practice").click()
        eng = sorted(page.locator("[data-interviewer-card] h3").all_text_contents())
        page.get_by_role("button", name="All interviewers").click()
        say("[ok] filters: Stress -> Marcus only; English confidence ->", eng)
        n0 = page.evaluate("window.__audio.length")
        page.get_by_role("button", name="Preview Victor's voice").click()
        page.wait_for_function(f"window.__audio.length > {n0}", timeout=120000)
        page.wait_for_timeout(1200)
        card = page.locator("[data-interviewer-card=victor] [data-avatar-mode]")
        say("[ok] Victor's voice preview playing; card avatar state =", card.get_attribute("data-avatar-mode"))
        assert card.get_attribute("data-avatar-mode") == "greeting"
        page.locator("[data-interviewer-card=victor]").screenshot(path=OUT / "iv_2_victor_preview.png")
        page.get_by_role("button", name="Select Victor").click()
        assert page.get_by_label("Focus").input_value() == "technical"  # Victor's default focus
        page.get_by_label("Job role").fill("Python Developer")
        page.get_by_label("Mode").select_option("voice")
        page.get_by_label("Questions").select_option("3")
        t0 = time.time()
        page.get_by_role("button", name=re.compile("Start interview with Victor")).click()
        page.wait_for_url(re.compile(r"/live$"), timeout=300000)
        sid = int(page.url.split("/")[-2])
        say(f"[ok] interview {sid} with Victor created in {time.time() - t0:.0f}s")

        # ------------------------------------------------------------ 2. voice interview with Victor
        wait_status(page, "Ready", 60)
        page.wait_for_function("window.__avatar3d && window.__avatar3d.status === 'ready'", timeout=120000)
        s = page.evaluate(SAMPLE)
        assert s["model"] == "/avatars/victor.glb" and s["who"] == "victor", s
        assert page.evaluate("window.__gum.length") == 0, "mic must not open before consent"
        say("[ok] Victor's own 3D model loaded; mic not opened before consent")
        page.get_by_role("button", name=re.compile("start the interview with Victor")).click()
        wait_status(page, "Interviewer speaking", 180)
        i0 = len(log)
        page.wait_for_timeout(1500)
        page.screenshot(path=OUT / "iv_3_victor_greeting.png")
        # true pause: audio clock stops, mouth closes; resume continues the same audio (no new buffer)
        n_audio = page.evaluate("window.__audio.length")
        page.get_by_role("button", name="Pause", exact=True).click()
        wait_status(page, "Paused", 10)
        page.wait_for_timeout(800)
        paused = page.evaluate(SAMPLE)
        page.get_by_role("button", name="Resume").click()
        wait_status(page, "Interviewer speaking", 10)
        page.wait_for_timeout(500)
        assert page.evaluate("window.__audio.length") == n_audio, "resume must continue, not replay"
        say(f"[ok] pause: avatar state={paused['mode']}, mouth={paused['gap']:.1f} (closed); resume continued the same audio")
        assert paused["gap"] < 1.5 and paused["mode"] == "transition"
        wait_status(page, "Recording your answer|Your turn", 180)
        speaking = [x for x in log[i0:] if x["status"] == "Interviewer speaking"]
        modes = {x["mode"] for x in speaking}
        gaps = {round(x["gap"]) for x in speaking}
        say(f"[ok] states while speaking: {modes}; distinct mouth shapes: {len(gaps)}")
        assert "greeting" in modes and len(gaps) >= 4
        wait_status(page, "Recording your answer", 30)
        rec = [x for x in log if x["status"] == "Recording your answer"]
        page.wait_for_timeout(3000)
        page.screenshot(path=OUT / "iv_4_listening.png")
        quiet = [x["gap"] for x in log[-20:] if x["status"] == "Recording your answer"]
        say(f"[ok] listening state={rec[-1]['mode']}; mouth while candidate speaks max={max(quiet):.1f} (stays closed)")
        assert rec[-1]["mode"] == "listening" and max(quiet) < 1.5
        k = len(log)
        wait_status(page, "Review your answer", 240)
        assert "reaction" in {x["mode"] for x in log[k:]}, "avatar should react when the answer ends"
        transcript = page.locator("#answer").input_value()
        say("[ok] reaction state seen; transcript:", transcript[:90], "…")
        page.get_by_role("button", name="Submit answer").click()
        k = len(log)
        wait_status(page, "Interviewer speaking", 400)
        seen = [x["mode"] for x in log[k:]]
        say("[ok] after submit, avatar states:", list(dict.fromkeys(seen)))
        assert "thinking" in seen
        detail = page.evaluate(f"fetch('/api/student/interviews/{sid}').then(r=>r.json())")
        q2 = detail["questions"][1]
        say(f"     Q1: {detail['questions'][0]['text']}")
        say(f"     Q2 ({'follow-up' if q2['is_followup'] else 'new'}): {q2['text']}")
        say(f"     Q1 answer observed: {detail['questions'][0]['answer']['details'].get('observed')}")
        # Q2 + Q3 typed (faster), then finish
        for _ in range(2):
            wait_status(page, "Recording your answer|Your turn", 180)
            page.get_by_role("button", name="Type instead").click()
            wait_status(page, "Review your answer", 10)
            page.locator("#answer").fill("I implemented the endpoints with Flask blueprints, validated input with "
                                         "marshmallow schemas, and used SQLAlchemy sessions per request.")
            page.get_by_role("button", name="Submit answer").click()
            wait_status(page, "Interviewer speaking|All questions answered", 400)
        wait_status(page, "All questions answered", 300)
        page.wait_for_timeout(1500)
        say("[ok] closing remarks state:", page.evaluate(SAMPLE)["mode"])
        page.get_by_role("button", name=re.compile("Finish")).click()
        page.get_by_text("Skill breakdown").wait_for(timeout=400000)
        page.get_by_text("Question-by-question feedback").wait_for(timeout=10000)
        page.wait_for_timeout(1500)
        page.screenshot(path=OUT / "iv_5_report.png", full_page=True)
        final = page.evaluate(f"fetch('/api/student/interviews/{sid}').then(r=>r.json())")
        rep = final["report"] or {}
        say(f"[ok] report: status={final['report_status']} overall={final['overall_score']} dims={rep.get('dimensions')}")
        say(f"     indicators: { {k: v for k, v in (rep.get('indicators') or {}).items() if k != 'limitations'} }")
        say(f"     next: {rep.get('recommended_next')} topics: {rep.get('suggested_topics')}")
        say(f"     Victor's closing remarks: {rep.get('closing_remarks')!r}")
        if rep.get("closing_remarks"):
            n0 = page.evaluate("window.__audio.length")
            page.get_by_role("button", name="Hear Victor's feedback").click()
            page.wait_for_function(f"window.__audio.length > {n0}", timeout=120000)
            page.wait_for_timeout(1500)
            fb = page.evaluate(SAMPLE)
            say(f"[ok] spoken feedback: avatar state={fb['mode']} mouth={fb['gap']:.1f}")
            assert fb["mode"] == "feedback"
        live = page.evaluate("window.__tracks.filter(t => t.readyState === 'live').length")
        say("[ok] live microphone tracks after the interview:", live)
        assert live == 0
        ctx.close()

        # ------------------------------------------------------------ 3. Marcus: time-limit interruption
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_init_script(INIT + "\ntry { sessionStorage.setItem('hs-test-answer-limit', '6'); } catch (e) {}")
        page = login(ctx)
        r = page.evaluate("""() => fetch('/api/student/interviews', {method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({job_role:'Backend Developer', category:'mixed', mode:'voice', question_count:3, interviewer:'marcus'})}).then(r=>r.json())""")
        mid = r["session"]["id"]
        page.goto(f"{BASE}/student/interviews/{mid}/live")
        wait_status(page, "Ready", 120)
        page.wait_for_function("window.__avatar3d && window.__avatar3d.status === 'ready'", timeout=120000)
        assert page.evaluate(SAMPLE)["model"] == "/avatars/marcus.glb"
        page.get_by_role("button", name=re.compile("start the interview with Marcus")).click()
        wait_status(page, "Recording your answer", 300)
        n0 = page.evaluate("window.__audio.length")
        wait_status(page, "Transcribing|Review your answer", 30)
        page.wait_for_function(f"window.__audio.length > {n0}", timeout=60000)  # "Let me stop you there…"
        wait_status(page, "Review your answer", 240)
        notice = page.get_by_text(re.compile("stopped your answer")).text_content()
        page.screenshot(path=OUT / "iv_6_marcus_interrupt.png")
        page.get_by_role("button", name="Submit answer").click()
        wait_status(page, "Interviewer speaking|Evaluating", 30)
        page.wait_for_timeout(2000)
        d = page.evaluate(f"fetch('/api/student/interviews/{mid}').then(r=>r.json())")
        obs = d["questions"][0]["answer"]["details"]["observed"]
        say(f"[ok] Marcus interrupted at the limit: notice={notice!r}; interjection spoken; stored observed={obs}")
        assert obs["interrupted"] is True
        page.evaluate(f"fetch('/api/student/interviews/{mid}', {{method:'DELETE'}})")
        ctx.close()
        browser.close()
        say("ALL OK")


main()
