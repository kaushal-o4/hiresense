# HireSense

**AI-Powered Intelligent Interview and Placement Assessment System.** It has four portals (Student, Recruiter, Mentor, Admin) that share one database and API.

The full requirements are in [PROJECT_SPEC.md](PROJECT_SPEC.md).

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Recharts, React Router |
| Backend | Python FastAPI, a small MongoDB data layer (`backend/app/odm.py`, pymongo) |
| Database | **MongoDB** (local Windows service by default; MongoDB Atlas works by changing `MONGODB_URL`). Uploaded files are stored on local disk in `backend/uploads/`. |
| Auth | JWT in an httpOnly cookie (Bearer header also accepted). Argon2 password hashing. Role-based access is enforced on the backend. |
| AI (text) | **Local** language model via [Ollama](https://ollama.com): `qwen3:4b` by default, with JSON-schema-constrained outputs. No API key is needed and no student data leaves the computer. |
| AI (matching) | **Local** Sentence Transformers embeddings (`all-MiniLM-L6-v2`) + transparent skill rules |
| ML | scikit-learn question-type classifier, trained offline (`backend/ml/`) |
| Resumes | `pypdf` (PDF) and `python-docx` (DOCX) |
| Voice | Browser Web Speech API for speech-to-text and text-to-speech (Chrome/Edge) |

---

## 1. Run it (Windows, VS Code)

You need **Python 3.12+** (`py --version`), **Node.js 20+** (`node --version`), **MongoDB Community Server** (runs as the
Windows service "MongoDB" on `127.0.0.1:27017`) and **Ollama** for the AI features (see section 2).

### Easiest way
Double-click **`start.bat`**. It checks Python, Node.js and Ollama, downloads the AI model on first run, opens the
backend and frontend in two windows and then opens **http://localhost:5173**.

You can also start the two parts yourself:

```
start-backend.bat     -> API on http://127.0.0.1:8000  (docs: http://127.0.0.1:8000/docs)
start-frontend.bat    -> App on http://localhost:5173
```

On first setup the backend console prints a generated **admin password once**. Copy it somewhere safe.

### Automated tests
`backend: .\venv\Scripts\python.exe -m pytest tests` and `frontend: npm test`. Once the project is on GitHub,
`.github/workflows/tests.yml` runs both on every push, with a MongoDB service container.

### Manual way (two VS Code terminals)

```powershell
# Terminal 1 - backend
cd backend
py -3.14 -m venv venv                 # first time only
.\venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # first time only (CPU build, ~200 MB)
pip install -r requirements.txt       # first time only
pip install --no-deps kokoro==0.7.16  # first time only (voice; see section 2b)
copy .env.example .env                # first time only, then edit it
python -m app.seed                    # indexes, admin account, badges, question bank (safe to re-run)
uvicorn app.main:app --reload --port 8000

# Terminal 2 - frontend
cd frontend
npm install                           # first time only
npm run dev
```

### Accounts after seeding

| Role | Email | Password |
|---|---|---|
| Admin | admin@hiresense.app | Generated on first seed and printed **once** in the console (or `ADMIN_PASSWORD` in `backend/.env` if you set one) |

There are **no demo accounts or sample users**. Students and recruiters register on the sign-up page (recruiters can be
set to need admin approval); the admin creates mentor accounts in *Admin → Users*. The seed only adds the platform's
reference data: interview categories and question bank, rubrics, badges, reward rules, challenges and four starter
assessments. The backend logs a security warning at startup while any admin account still uses the old published password `Admin@12345`.

**Lost the admin password?** From `backend/` run `venv\Scripts\python -m app.reset_admin` to generate and print a new one, or `venv\Scripts\python -m app.reset_admin "YourNewPassword"` to set your own.

**Forgot password:** the sign-in page has a "Forgot password?" link. With email set up (`SMTP_*` in `backend/.env`), the reset link is emailed. Without email, the link is printed in the backend console so the placement office can pass it on. Links expire after 30 minutes and work only once.

**Deleting an account:** students can permanently delete their own account and data under *Account settings → Delete my account*.

---

## 2. Turn on the AI features (local, free, private - or Gemini, see 2a)

All AI runs on your own computer. Nothing is sent to an outside AI service, and there is no API key.

### Models used
| Purpose | Model | Size | License |
|---|---|---|---|
| Resume analysis, interview questions, answer evaluation, English coach, match explanations | `qwen3:4b` via Ollama | ~2.6 GB download, ~3.5–4 GB RAM/VRAM in use | Apache-2.0 (commercial use allowed) |
| Semantic job matching | `sentence-transformers/all-MiniLM-L6-v2` | ~90 MB | Apache-2.0 |
| Question-type cross-check | our own scikit-learn model (`backend/ml`) | < 1 MB | this project |

Ollama itself is MIT-licensed. The embedding model downloads once from Hugging Face, then runs offline.

### Setup (once)
```powershell
winget install --id Ollama.Ollama -e        # or download from https://ollama.com/download
ollama pull qwen3:4b                         # ~2.6 GB
```
Ollama starts automatically in the system tray after install. If it isn't running, open the Ollama app or run `ollama serve`.
Then restart the backend. The admin **AI & Monitoring** page and the student pages show whether the AI is ready.

### Hardware
| Machine | Recommendation |
|---|---|
| 16 GB RAM, any or no GPU (tested: i5-12450H + RTX 3050 4 GB) | `qwen3:4b` (default). Resume analysis ~60 s, interview question ~5–10 s, answer evaluation ~10–30 s. |
| 8 GB RAM, no GPU | Set `OLLAMA_MODEL=qwen3:1.7b` in `backend/.env` and run `ollama pull qwen3:1.7b`. Faster, but lower quality. |
| < 8 GB RAM | Not recommended; set `AI_ENABLED=false`. |

A GPU is not required. On the test laptop, Ollama split the model between the GPU and CPU (about 55% / 45%).
The first request after starting loads the model and takes 30–70 s longer. `OLLAMA_KEEP_ALIVE=30m` keeps it loaded afterwards.
Requests are processed one at a time (`AI_MAX_CONCURRENT=1`) so a laptop doesn't run out of memory.

### Per-task models (2026-10-25)
`OLLAMA_MODEL_FAST` / `OLLAMA_MODEL_STRONG` route tasks to different models (`services/model_router.py`); empty = `OLLAMA_MODEL`.
Measured on this laptop: `qwen3:1.7b` for English chat takes ~2 s per turn instead of ~22 s, but it scores answers far too
generously, so only chat uses it. Switching models costs 5-8 s on a 4 GB GPU. Details: `docs/PERFORMANCE_BASELINE.md`.
Health checks: `/api/health/live`, `/api/health/ready`. English replies stream from `POST /api/student/english/{id}/message/stream`.

### How each feature works
* **Resume analysis**: PDF/DOCX text → local model (resume text wrapped in tags, with an instruction to ignore any instructions inside it) → JSON validated against a schema (one retry if invalid).
  Then **every skill, project, employer, certification and the name is checked against the resume text**, and anything not found is removed.
  "Resume completeness" (0–100) is a points table, not an AI opinion: name 5, education 15, technical skills 2.5 each (max 25), projects 8 each (max 25), experience/internships 10 each (max 20), certifications 5 each (max 10).
  Students can fix mistakes with **Correct details**.
* **Mock interviews**: each question is generated from the student's resume analysis, skills, projects, chosen subject, the role and the previous answers.
  **Adaptive rule:** an answer scoring ≥ 75 moves the next question up a level (easy → medium → hard), and < 45 moves it down with a short explanation first (once, then it moves on).
  A "hard" interview starts with one medium warm-up. Near-duplicate questions are rejected (text similarity) and regenerated once, then a question-bank question is used.
* **Answer evaluation**: the model scores relevance, correctness, completeness, clarity and communication (0–10).
  **Fixed rules then apply:** empty or "I don't know" answers are capped at 1, answers under 8 words at 3, answers under 25 words get completeness ≤ 5, and correctness can be at most relevance + 3.
  "Content" and "Communication" are shown separately. Accent and speech-recognition errors are explicitly excluded.
* **Job matching** (`backend/app/services/matching.py`): score = weighted average of required-skill coverage (0.50), preferred-skill coverage (0.15), semantic similarity of profile vs job (0.20) and experience fit (0.15).
  Then a **gap cap** applies: score ≤ 40 + 60 × required coverage, so similarity can never hide a missing required skill.
  Skills match exactly (with aliases such as JS = JavaScript) or when named in project text. Related skills (embedding similarity ≥ 0.50, e.g. MySQL for PostgreSQL) count as *partial*, at half credit.
  Thresholds were calibrated on real embeddings (comments in the file). "AI match" adds a local-model explanation, but **the model cannot change the score**, and missing required skills are always listed as concerns.

### When the AI is not available
The app still runs, but it never fakes AI results:
- Resume analysis is marked "unavailable", with the reason (e.g. "Ollama is not running" or "Run: ollama pull qwen3:4b"). You can retry it later.
- Mock interviews use the admin **question bank**, labelled in the UI. Answers stay unscored until you click "Retry evaluation".
- Job matching still works: semantic if the embedding model is available, otherwise "keyword match only", clearly labelled.
- English practice and AI recommendations show a clear error message.

Each user is limited to `AI_DAILY_LIMIT_PER_USER` AI calls per day (default 200). Admins can switch all AI off under **Settings → ai_features_enabled**.
The admin **AI usage** log records the status, latency and token counts of each call, never the resume or answer text.

## 2a. Gemini API (fast, hosted) - default provider since 2026-10-29

`LOCAL_AI_PROVIDER=gemini` in `backend/.env` sends every language-model call to Google Gemini instead of the local
Ollama model. Speech (Kokoro/Whisper), embeddings and camera monitoring still run on this computer.

**Privacy:** with Gemini, prompts containing resumes and interview/English answers are sent to Google. Use
`LOCAL_AI_PROVIDER=ollama` if that is not acceptable (e.g. no consent from students).

Setup:
1. Create a key at https://aistudio.google.com/apikey
2. Put it in `backend/.env`: `GEMINI_API_KEY=...` (never commit this file), then restart the backend.
3. Admin > Monitoring shows `Model: ... (gemini)` and "Gemini API: running".

How it stays fast and reliable (`backend/app/services/gemini_llm.py`, plugged into `local_llm.chat_json`):
- `GEMINI_MODEL=gemini-flash-latest` (Google's alias for the newest Flash). If the key can't use the configured
  model, the newest stable Flash model it can use is picked automatically. Per-task tiers: `GEMINI_MODEL_FAST/_STRONG`.
- Thinking is turned down (`GEMINI_THINKING=minimal`) - the app asks for JSON with a schema, so it isn't needed.
- Replies are streamed, so the interviewer starts speaking at the first sentence.
- Rate limits (429) and Google errors (5xx) / network drops are retried up to `GEMINI_RETRIES` times with backoff.
- Up to `GEMINI_MAX_CONCURRENT` requests run in parallel (Ollama: 1), and background feedback no longer waits behind
  the candidate's turn.
- `AI_FALLBACK_TO_OLLAMA=true`: no key, no internet or quota used up -> the same request is answered by the local
  Ollama model (only if nothing was streamed yet). Admin > Monitoring shows when the fallback is in use.
- Tests never call Gemini (`tests/conftest.py` forces Ollama); `tests/test_gemini.py` uses a fake HTTP client.

## 2b. Live voice interview (animated AI interviewer)

Choose **Mock interviews → Mode: Live voice (AI interviewer)**. "Aria", an animated interviewer, asks each question
aloud. You answer by speaking, the answer is transcribed, and it goes through the **same** interview API as text
mode (scoring, adaptive difficulty, follow-ups, rewards and report are unchanged).

```
Start ─► AI writes question (Ollama) ─► local TTS (Kokoro) ─► Aria speaks, lips follow phoneme timing
   ▲                                                                    │ audio ends
   │                                                                    ▼
next question ◄─ existing /answer API scores it ◄─ you review/edit ◄─ local Whisper ◄─ mic records (auto-stops on pause)
```

| Part | How | Licence |
|---|---|---|
| Avatars | **Realistic 3D humans** (three.js), one per interviewer (see §2c): Microsoft Rocketbox Female_Adult_01 (Aria, `interviewer.glb`), Business_Male_07 (Victor, `victor.glb`), Business_Male_01 (Marcus, `marcus.glb`), Business_Female_01 (Elena, `elena.glb`). 15 viseme blendshapes drive the lips; ARKit blendshapes drive blinks, smiles, brows and eye direction; bones drive head sway, nods and breathing. Converted once with Blender by `frontend/avatar-src/convert_rocketbox.py` into `frontend/public/avatars/`. If WebGL fails, a simplified 2D SVG avatar is used (Aria's drawing, recoloured for the others). | MIT (`public/avatars/ROCKETBOX_LICENSE.md`) |
| Voice (TTS) | **Kokoro-82M**, local, CPU (~2.5× faster than real time on the test laptop) | Apache-2.0 |
| Phonemes | espeak-ng via `phonemizer-fork` + `espeakng-loader` | **GPL-3.0** (see below) |
| Speech-to-text | **Whisper base.en** via `transformers`, local, CPU (~2 s for 7 s of speech) | MIT |
| Browser recorder | Web Audio AudioWorklet → 16 kHz WAV, silence detection | this project |

Kokoro (~330 MB) and Whisper (~150 MB) download once on first use, then run offline. The server preloads them at startup.

**Lip sync, honestly:** Kokoro predicts how long each phoneme lasts (25 ms units). Each phoneme becomes one of 14
mouth shapes, played against the audio clock and scaled by the live audio volume, so the mouth closes in pauses and when
playback stops. The timing comes from the speech model itself, not a looping animation. The shapes are a stylised
14-viseme set, not a facial-capture rig. If the local voice fails, the browser's own voice is used. That fallback has
no phoneme timing, so its lip sync is **approximate** (letters per word) and labelled as such on screen.

**Eye contact** means Aria looks out of the screen toward you. The app does **not** track or measure your gaze.

**Avatar appearance:** a generic, made-up 3D person from the Rocketbox library (blonde hair, jeans). It is
deliberately not modelled on any real person.

**Answer scoring (2 steps):** a fast score (~60 tokens) decides the next question's difficulty, then the detailed
tips and sample answer are written in the background (answer status `scored` → `completed`). Off-topic answers to
technical/project questions are capped using question–answer meaning similarity (< 0.20, calibrated on real
examples), and for every question type when the model itself says the answer does not address the question.

### Open items (work in progress, 2026-10-10)
* Last browser run: the reply after an answer took ~130 s (slower than before). Likely cause: the server had just
  restarted (models still loading) and the background feedback competes with the next AI call (one at a time).
  Needs a re-measure on a warm server.
* In that run the final report showed `report_status=pending` for a moment; check that the report finalises after
  background feedback.
* Voice: Kokoro uses espeak phonemes because spaCy (needed for its better English pronunciation) has no Python 3.14
  build yet; this is the main remaining cause of a slightly synthetic voice.

### Privacy
* The microphone opens only after you press **I agree – start the interview**. It is open only while it is your turn (red "Recording" badge), and it is released between answers. It is never on while Aria speaks (the state machine blocks it).
* Audio is sent only to this app's backend, transcribed in memory and **not stored**. Only the text you submit is saved.
* The camera is used only for the disclosed interview monitoring (§2e): analysed in your browser, never recorded or
  uploaded; only short event records are stored.
* The old text-mode voice input (Web Speech API) sends audio to Google/Microsoft in Chrome/Edge. The live interview does **not** use it.

### State machine (`frontend/src/voice/interviewMachine.js`)
`INITIALIZING → READY → PREPARING_SPEECH → SPEAKING → LISTENING → TRANSCRIBING → REVIEWING → EVALUATING → (next question) … → WRAP_UP → COMPLETING → COMPLETED`,
plus `PAUSED` and `ERROR`. Events not allowed in the current state are ignored. This prevents double submissions, recording while speaking, processing one recording twice, and accidental finishing.
Pausing while the interviewer speaks **pauses** the audio (the audio clock is suspended and the mouth closes), and Resume continues from the same word; if the speech could not be paused, the question is replayed instead. Pausing while recording discards that recording.
`INTERRUPT` (stress interview only) stops a recording at the interviewer's time limit and keeps what was said.
If submitting fails, the transcript is kept. If the server saved the answer but failed to create the next question, the page calls `POST /api/student/interviews/{id}/next-question` to recover.

### Licences to be aware of
espeak-ng and phonemizer are **GPL-3.0**. Running this app yourself (including for a college) is fine. If you
**distribute** the backend to others, the GPL's source-availability terms may apply to that distribution. Kokoro's
weights (Apache-2.0), Whisper (MIT) and misaki (MIT) have no such condition. Set `TTS_ENABLED=false` to avoid using
espeak-ng; the app then uses the browser voice with approximate lip sync.

### Manual check with a real microphone (not automatable)
1. Chrome or Edge, speakers on, open a Live voice interview, press Start: you **hear** Aria and see her lips move with the words.
2. Grant microphone permission when asked. The red Recording badge appears only after she stops talking.
3. Answer aloud, then pause for ~4 s: recording stops by itself and your words appear in the box. Fix any mistakes, then Submit.
4. With speakers loud and no headphones, check that Aria's voice is not transcribed as your answer.
5. Try Pause/Resume, Repeat question, Type instead, the camera toggle and End.
6. Finish: the feedback report appears.

### Troubleshooting
| Problem | Fix |
|---|---|
| "Interviewer voice unavailable" | Check **AI & Monitoring** / `GET /api/voice/status`; the first run needs internet to download Kokoro |
| "Microphone permission was denied" | Click the lock icon in the address bar → allow Microphone, then press Start answering |
| Transcript is empty | Wrong microphone selected in Windows sound settings, or too quiet; or use **Type instead** |
| Recording stops too early | You paused for 3.5 s; press **Record again**, or press "Start answering" before continuing |
| Problem | Fix |
|---|---|
| "Ollama is not running" | Open the Ollama app, or run `ollama serve` in a terminal |
| "The model 'qwen3:4b' has not been downloaded" | `ollama pull qwen3:4b` |
| "took too long to respond" | First call after a restart is slow; try again. Otherwise use `qwen3:1.7b` or raise `AI_TIMEOUT_SECONDS` |
| `CUDA error` in the AI usage log | Happened once on first load on the test laptop and then went away. If it repeats, update the NVIDIA driver or run CPU-only by setting the Windows environment variable `CUDA_VISIBLE_DEVICES=-1` and restarting Ollama |
| Matching says "keyword match only" | The embedding model could not load. It needs internet the first time; see **AI & Monitoring** for the error |

---

## 2c. Interviewer personalities (Aria, Victor, Marcus, Elena)

**Mock interviews → 1. Choose your interviewer.** Each card shows a live 3D preview, the personality, voice,
recommended level and categories, a **Preview** button (the avatar speaks a sample line with lip sync) and
**Select**. Filters: Friendly, Standard, Strict Technical, Stress, HR, English Confidence Practice. Selecting an
interviewer pre-fills their usual focus and level; you can change both. Text-mode interviews keep the same
personality (questions and feedback), just without the avatar.

| | Aria (existing) | Victor | Marcus | Elena |
|---|---|---|---|---|
| Style | friendly, patient | strict, formal, analytical | stress interview | professional HR |
| Questions | confidence-building, simple wording | depth: how/why, trade-offs, what *you* built | very short, rapid, challenges assumptions | behavioural (teamwork, conflict, goals), STAR |
| Weak answer | kind 1-2 sentence explanation + simpler follow-up | no hints; demands specifics on the same topic | no hints; "give me the key point" | asks for the missing situation/action/result |
| Next question harder at / easier below | 75 / 45 (unchanged) | 70 / 35 | 70 / 40 | 75 / 45 |
| Answer time | 180 s | 150 s | **75 s, then he politely stops you** | 150 s |
| Voice (Kokoro) | `af_heart` 0.95× | `bm_george` 0.95× | `am_michael` 1.12× | `bf_emma` 1.0× |
| Face | warm smiles, nods | serious, controlled head, raised brow when probing | focused, squint, brief scepticism | polished, attentive nods |

* **Where:** behaviour in `backend/app/services/interviewers.py` (prompts stay on the server; `GET /api/interviewers`
  returns the public part). Expressions in `frontend/src/voice/avatarStates.js`. Each session stores `interviewer`
  (migration `e5c8f3b1d726`; older sessions = Aria).
* **Fair scoring:** every answer is scored by the same rubric and evaluator whoever the interviewer is (tested:
  identical scores across all four). Personality changes question strategy, follow-ups, difficulty steps, time
  limit, voice and the *tone* of feedback, never the score. The evaluator is told that grammar must not lower
  relevance, correctness or completeness. All personas share the same professional boundaries (no insults,
  nothing personal; resume contents are claims to verify, not facts).
* **Avatar states** (one at a time, from the conversation state): `idle`, `greeting`, `speaking`, `probing`
  (follow-up), `listening`, `thinking`, `reaction` (after you answer), `feedback` (closing remarks), `transition`
  (paused / resting). Expressions blend over ~0.3-0.6 s. The **mouth is not tied to the state**: it follows the
  audio actually playing, so it stops when the sound stops. Reduced-motion users get very little head movement.
* **Stress interruptions** happen only at the time limit (countdown shown), never randomly: recording stops, Marcus
  says "Let me stop you there", and your words so far go to the review box as usual. The answer is marked as stopped
  at the time limit in the report.
* **Interview room:** a large avatar with a name, badge and voice-activity dot, subtitles with the spoken word
  highlighted, and a right panel with progress, duration, transcript, private notes (kept in your browser only) and
  settings (voice on/off, speed, captions, subtitle size, auto-microphone). Controls: microphone on/off, repeat,
  pause/resume, voice, camera, settings, end. **Language:** English only, because the local Kokoro and Whisper
  base.en models support only English.
* **Report:** the existing question-by-question feedback, plus a skill breakdown (technical knowledge, scored only
  on technical/project questions and separate from communication; relevance; answer structure; communication
  clarity). It also has response indicators (answer length, time, speaking pace, filler words, short answers,
  stopped at limit; observable behaviour only, with limitations shown), topics to revise, a recommended next
  difficulty and interviewer, and the interviewer's **spoken closing remarks** (FEEDBACK state). Eye contact, facial
  expression, accent and emotion are never measured or used.
* **No paid services, no API keys:** everything runs locally (Ollama, Kokoro, Whisper, Rocketbox models).

## 2d. Spoken English practice with Aria (avatar)

`/student/english` → Mode **Speak with Aria (avatar)**, Practice **English free talk** or **Job interview practice**.
The session page (`frontend/src/pages/student/EnglishAvatarSession.jsx`, loop in `src/voice/englishMachine.js`) runs
hands-free: Aria speaks with lip sync and highlighted subtitles → the mic opens → the student talks → a ~4 s pause
or **Done** → local Whisper (`POST /api/student/english/{id}/transcribe`) → Aria thinks → replies. Text-mode
sessions keep the plain chat page.

- Persona: `ARIA_SYSTEM` in `backend/app/services/ai.py`. Each reply returns `reply`, `avatar_mode`
  (`speaking`/`encouraging`), `encouragement`, `corrections` and `suggested_followups`, stored in
  `english_messages.meta`. Corrections are checked server-side: they must quote the student, and
  punctuation-only fixes are dropped because punctuation in voice replies comes from the speech recogniser.
  Emoji are stripped so TTS never reads them aloud.
- Sidebar: **Confidence meter** (`confidence_meter()`, shown during practice only; it is not a score),
  **Practice streak** (`GET /api/student/english/stats`) and **Verified practice time**
  (`live_active_seconds`, the same rule as the final `active_seconds`).
- Hesitation helpers: after 5 s of quiet on the student's turn, starter phrases are highlighted (Aria's
  suggestions plus generic ones). Clicking one shows "Try saying…" in voice mode, or fills the box in typing mode.
- Fallbacks: no local TTS → the browser voice (approximate lip sync). No local STT → browser recognition
  (Chrome/Edge send audio to their cloud, and the start screen says so). If that fails → typing.
- Measured on this laptop (no browser running): transcription ~4 s and Aria's reply ~15 s. In the headless E2E,
  each step is 3-10x slower because Chromium renders the 3D avatar on the CPU.

## 2e. Interview speed, response modes and camera monitoring (2026-10-11)

### What made the interviewer slow (measured, `tests_perf/`)
| Bottleneck found | Fix |
|---|---|
| **`localhost` on Windows**: every connection to Ollama tried IPv6 first and waited **~2.1 s** (and the 2 s status check could time out) | Ollama URL uses `127.0.0.1`; one kept-alive HTTP connection (`services/local_llm.py`) |
| **Token generation** is the slow part (~17-25 tokens/s, model split between the 4 GB GPU and CPU); prompt reading is 0.1-0.6 s | shorter questions (Fast mode), compact history, an unused scoring field removed, tighter output limits |
| Speech waited for the **whole** question and the **whole** audio | `/turn` streams: each finished sentence is synthesised and played while the rest is written |
| **Cold model**: first AI call 64 s | model, voice and transcription loaded at server start and again from the setup screen (`POST /api/voice/warmup`); first question written while the student does the setup |
| **Background feedback** (~350 tokens) competed with the next turn (one spoken sentence took 122 s in a browser run) | priority gate: candidate-facing work goes first, background generation pauses during turns, speech and transcription, and resumes later |
| Long first sentence → long synthesis before any sound | the first sentence is synthesised in two parts at a natural comma |

### Before / after (real models, this laptop)
| Step | Before (p50 / p95) | After, Fast mode (p50 / p95) |
|---|---|---|
| First AI call after start (model load) | 63.9 s | 4.7 s (preloaded) |
| Write a question | 8.4 s / 9.1 s | 4.1 s / 4.5 s |
| First spoken sentence of the question ready | (whole question only) | 2.8 s / 3.1 s |
| Score an answer | 10.6 s / 27.6 s | 3.3 s / 3.4 s |
| Server: answer → next question complete | 19.0 s / 36.1 s | 7.4 s / 7.7 s |
| Server: answer → first sentence ready for speech | — | 6.1 s / 6.4 s |
| TTS of the first sentence | (whole question 5.0 s) | 1.2 s |
| Browser E2E: Start → first interviewer audio | (≈ cold model + TTS) | 1.0-1.2 s |
| Browser E2E: answer submitted → next question audible | — | 10.8-15.0 s |
Coaching mode: first sentence ready 2.1 s (spoken feedback comes first), whole reply 6.5 s.
Re-measured after the coverage-plan question generator was added (more metadata per question): first spoken
sentence 2.6 s and answer → first sentence 6.3 s (unchanged), whole question 7.5 s, answer → question complete 11.0 s
(`tests_perf/results/final_fast.json`). Numbers vary with what
else the laptop is doing; the 1-3 s target is not reachable for a full turn with `qwen3:4b` on this hardware
(scoring alone generates ~50 tokens ≈ 3 s). Re-measure with `tests_perf\bench_interview_latency.py`.
Headless Chromium **without a GPU** renders the 3D avatar on the CPU and makes every step 3-10x slower; use
`HS_E2E_GPU=1` (or `HS_E2E_NO_WEBGL=1`) for representative E2E timings.

### Response modes (chosen on the start form)
* **Fast interview**: one short question (~25 words), first sentence of the greeting only, a short cached spoken
  acknowledgement (since 2026-10-25; see below),
  detailed feedback written in the background and shown at the end.
* **Coaching**: 1-2 spoken sentences of feedback before each question (what was good, what was missing, an English
  phrasing tip when communication < 6/10), hints for every interviewer, 50% more answer time, longer pause before the
  microphone stops, written coaching notes after each answer.

### Speech recognition
End of answer = a pause of **2.0 s** (Fast) / **3.0 s** (Coaching) after at least 1.2 s of speech, adjustable in the room
settings (0.6-4 s). A 1.0 s default was tried and measured: an ordinary pause between two spoken sentences reads as
1.3-2 s of silence to the detector (soft sentence endings fall below its level threshold), so answers were cut off
after the first sentence (`tests_e2e\partial_transcript_check.py`). Long answers are cut into pieces at natural pauses and transcribed while the student is still
talking ("Heard so far"), so only the last piece is transcribed after they stop. **Continue speaking** appends to the
transcript; **Send automatically** is an optional setting (off by default).

**Live transcription (2026-10-29).** Speech recognition now uses **faster-whisper** (CTranslate2, int8, greedy) instead
of the transformers pipeline (`STT_ENGINE=faster`, falls back to `transformers` if the package is missing). Measured on
this laptop's CPU with `tests_perf\bench_stt.py` (Kokoro-voiced answers, base.en):

| clip | transformers | faster-whisper | faster-whisper small.en |
|---|---|---|---|
| 9 s answer | 2.3 s | **0.7 s** | 2.0 s |
| 16 s answer | 4.2-4.9 s | **0.8 s** | 2.3 s |

small.en was no more accurate on these clips, so base.en stays the default. The room now behaves like a live interviewer:
- **Live captions** - the unfinished piece of the answer is transcribed about every 1.2 s while the student talks (one
  request at a time, `live=true`, own rate limit) and shown under "Heard so far".
- **No wait after the pause** - when the latest live caption already reaches the end of the speech, its text is the
  final text, so nothing is transcribed after the student stops (`client.stt_roundtrip` metric has `reused_live`).
- **Sent automatically** - the answer goes to the interviewer as soon as the end-of-answer pause is detected (setting
  "Send my answer automatically", now on by default; turn it off to check the text first).
- The current question is given to Whisper as context, so technical words come out right ("FastAPI", not "Fast API").

`tests_e2e\partial_transcript_check.py` (fake microphone, 3-sentence answer): 18 caption updates in 27 s, all sentences
in order, **transcript ready 0.0 s after recording stopped** (was: the last piece's transcription, ~2-5 s). The 2 s
end-of-answer pause itself is unchanged (shorter pauses cut answers off, see above).

### Camera monitoring (disclosed, on-device)
* Setup screen before every live interview: what is monitored and why, processed **in the browser** (MediaPipe Face
  Landmarker, model served from `public/models`), nothing stored except event records, retention (default 90 days,
  setting `monitoring_retention_days`), who can see it, how to stop. Separate opt-ins; permissions are requested only
  when the student presses **Test my camera and microphone**; camera preview with face/lighting/framing guidance.
* **Camera required by default** (`monitoring_camera_required` = true, admin → Settings): camera, face visibility
  and multiple-face checks are mandatory; approximate gaze/head direction and tab-focus changes stay optional.
  Without camera access the interview does not start and the student is told why.
* Signals: face not visible, more than one face, sustained looking away (approximate), camera blocked/dark, low light,
  camera disconnected, permission revoked, tab/window focus changes, monitoring stopped/unavailable. Grace periods,
  hysteresis and frame-agreement confidence (`src/monitoring/signalTracker.js`); neutral warnings only.
* Severity is assigned by the server (`services/integrity.py`); gaze is never above "low", and low-confidence signals
  stay "info". Events **never change scores** and never trigger a penalty.
* Review: admin → AI & Monitoring → **Interview integrity**; mentors only with the extra permission
  `review_integrity` and only for students they can access; recruiters: only completed interviews of their own applicants (see §2g). Views and reviews are audit-logged.
  Students see their events after the interview and can add an explanation.
* Media handling: one camera stream, self-view always marked "Camera on", **Stop monitoring** turns it off at once,
  everything is stopped when the interview ends or the page is left. Frames and audio are never sent to other services.

### Performance dashboard
Admin → AI & Monitoring → **Performance**: count, failures, average, p50, p95 and max per step (LLM with
load/prompt/generation split, TTS, STT, whole turn, and browser-measured waiting times). Only timings are stored
(`perf_metrics` table), never content. `PERF_METRICS_ENABLED=false` turns it off.

### Smoother avatar, faster speech (2026-10-25)
Measured on this laptop (real models; browser E2E `latency_monitoring_browser.py` with `HS_E2E_GPU=1` and a frame probe).
| Cause found | Fix |
|---|---|
| `num_ctx` 8192 left 45% of `qwen3:4b` on the CPU (Ollama keeps ~1 GB VRAM spare), so generation was slow **and** Kokoro TTS, also on the CPU, slowed down beside it (perf log: 7-25 s per sentence during live turns) | `OLLAMA_NUM_CTX=4096` (largest prompt ever logged: ~2,700 tokens) + `OLLAMA_NUM_GPU=99` (all layers on the GPU, ~3.1 GB VRAM; falls back to Ollama's own placement if loading fails). `MAX_RESUME_CHARS` 12000 → 9000 so a resume still fits. Warm-up reloads a model loaded with other settings |
| Silence after Submit while the answer is scored | the interviewer's cached acknowledgement now plays in Fast mode too (first sound ~0.1 s after Submit) |
| Avatar capped at 30 fps with uneven frame spacing (strict frame-time threshold) | Balanced = 60 fps (the Intel GPU Chrome uses holds it, p95 18 ms), jitter-tolerant pacing, shadow map redrawn every 3rd frame, no per-frame allocations; automatic step down (30 fps → lower resolution → no shadows) when frames run late |
| Phone/notes detection blocked the page ~73 ms every second (4-5 dropped avatar frames each time) | runs in a Web Worker (`public/mediapipe/object-worker.js`; `vision_bundle.js` there is a copy of the npm package's file - update it with `wasm/` on upgrades) |
| The mic worklet posted ~375 messages/s, each re-rendering the interview page | 1024-sample batches; the level meter updates at most ~12x/s |

Server, Fast mode, p50 (`tests_perf/results/gpu_full_ctx4096.json`): answer → first sentence ready 6.3 s → **4.0 s**,
answer → whole question 8.9 s → **5.7 s**, scoring 3.3 s → 2.4 s, question 5.8 s → 3.3 s, TTS first sentence 1.2 s →
0.8 s, LLM 17 → 25 tokens/s. Avatar during the live interview: ~28 → ~70 fps (144 Hz display), frames > 50 ms late per
phase 10-21 → 0-4, p99 frame gap 55-107 ms → 18-37 ms. Still not tried with a real human camera/mic. If another
program holds GPU memory, Ollama may fall back to partial GPU placement (logged as "loading with num_gpu=99 failed").

## 2f. Interview intelligence and the English conversation companion (2026-10-11)

No model was trained or fine-tuned. The same local `qwen3:4b` is used; what changed is the information it gets,
the checks on what it returns, and per-personality behaviour configuration.

**Why questions were generic or repeated (found in the code):** the prompt got project *names* only (no description,
technologies or the candidate's part); repeats were detected by wording only (`difflib` + word overlap), so
paraphrases passed; nothing recorded what each question had already covered; personalities differed mainly in prompt
wording.

**Interview engine** (`backend/app/services/interview_engine.py`, wired into `routers/interviews.py`):
* *Candidate facts*: projects with description, technologies and role, internships, education, skills. The prompt
  says these are the only experience the interviewer may refer to; missing details must be asked, not assumed.
* *Answer signals* (deterministic): vague team answers ("we did it"), unmeasured claims ("improved performance"),
  unexplained AI, very short, self-correction, partly unsure, "can you repeat the question". Each suggests the most
  useful follow-up; the interviewer's `followup_preference` decides which one comes first.
* *Coverage*: each stored question records `topic` (worked out in code from the resume) and `aspect` (one short
  label from the model); the prompt lists what was explored and what is still open - guidance, not a script.
* *Duplicates*, checked before a question is accepted: same wording; same request ("Tell me about / Explain /
  Describe the hospital project" are one question); same meaning (MiniLM cosine >= 0.78, calibrated: paraphrases
  0.81-0.94, different follow-ups on one project <= 0.69); same topic + aspect with similar wording. A clarifying
  follow-up and "please repeat the question" are allowed.
* *Retries*: live voice interviews 1 retry (each costs ~4 s while the candidate waits; anything already spoken is
  retracted), text mode 2. Then a resume-grounded template ("Which part of X did you build yourself?"), then the
  admin question bank, then general role questions - an interview never gets stuck. Rejection reason codes (never
  text) are stored in the question's `meta`.
* *Output checks*: stock praise ("Great answer!", "Excellent!") and greetings are removed, internal numbering
  ("your answer for Q3"), metadata/JSON and over-long questions are rejected.
* *Personalities* (`services/interviewers.py`): each has its own objective, traits (shown on the card), question
  length limit, aspect order, follow-up preference, acknowledgement and transition style and prohibited behaviours.
  Choosing Marcus shows a clear stress-interview notice. Scoring is still identical for every interviewer.

**English conversation companion** (`services/english_companion.py`): a separate personality from the interviewers
(Aria's avatar and voice, no interview pressure). Three learning modes chosen on the start screen:
*Free conversation* (at most one on-screen tip, spaced out, never spoken), *English learning* (a short spoken "a more
natural way to say that is...", then the conversation continues; the same correction is never repeated) and
*Confidence* (short easy questions, 0.85x speech, 6.5 s before the turn ends, example answers). Topic changes such as
"Actually, can we talk about movies?" are detected in code; if the model ignores one, the reply is regenerated.
A compact memory (current/earlier topics, interests, details, questions asked, corrections given; sensitive details
are never stored) is sent instead of the full transcript and shown as "What Aria remembers". Wrong corrections are
filtered (British/American spelling, rewrites much longer than what was said, invented quotes).

**Evaluation** (`backend/eval/scenarios.json`, `eval/run_eval.py`, real model, fictional resumes; results in
`eval/results/`). Same 34 interview questions before and after; duplicates judged independently by MiniLM >= 0.75:

| | before | after |
|---|---|---|
| near-duplicate question pairs | 9 | 3 (remaining pairs ask different sides of one project) |
| follow-up responds to a vague answer (similarity >= 0.35) | 62% | 73% |
| questions that mention the resume or role | 84% | 73% (behavioural questions rarely name the resume) |
| robotic phrases / invalid model output | 0 / 0% | 0 / 0% |
| English: replies follow the student's topic, incl. 2 topic switches | - | 100% (3 sessions) |

Latency (`tests_perf/bench_interview_latency.py --mode fast`, Ollama idle): first spoken sentence 2.5 s
(unchanged); whole question 5.8 s (was 4.1 s; the extra label and longer prompt); answer -> question complete 8.9 s.
In text mode a turn where the model keeps repeating itself takes 17-25 s (3 attempts + template).

**Known limits:** a 4B model still asks some similar questions in long interviews; aspect labels are coarse; the
"resume mentions" metric is a keyword check; each eval was run once (no variance estimate); English "before"
numbers were not measured because the old code could not be isolated from other work in progress.

## 2g. Interview security module (2026-10-23)

Extends the camera monitoring of §2e into one security module: more detectors, one event engine, a security summary,
recruiter reports and admin settings. Everything in §2e still applies (disclosed, opt-in per feature, on-device,
never changes scores). Code: `frontend/src/monitoring/*`, `backend/app/services/integrity.py`,
`backend/app/routers/monitoring.py`, migration `c6f1a9e3d852`.

### What is detected, and how
| Category (`event_type`) | How | Where it runs |
|---|---|---|
| PROLONGED_LOOKING_AWAY (`attention_away`) | head yaw/pitch from MediaPipe's face transformation matrix + eye-direction blendshapes, measured **from the candidate's own calibrated position**; recorded after 3 s, reminder after 8 s; brief glances are not recorded; not judged in low light | browser |
| EYE_GAZE_DEVIATION (`attention_repeated`) | 5 recorded deviations within 120 s = one event (then counting restarts) | browser |
| FACE_NOT_DETECTED / FACE_PARTIALLY_VISIBLE | no face for 4 s+ / face cut by the frame edge for 10 s+ (grace periods, hysteresis, frame agreement) | browser |
| MULTIPLE_FACES_DETECTED | 2+ faces for 3 s+, with the largest count seen; nobody is identified | browser |
| BROWSER_TAB_SWITCH, FULLSCREEN_EXIT, SECOND_DISPLAY, PASTE | Page Visibility / blur, Fullscreen API, `screen.isExtended`, paste events (§2e) | browser |
| POSSIBLE_BACKGROUND_SPEECH (`background_speech`) | while the microphone is open **for the answer**: voiced audio (RMS level only) for 4 s+ while the one visible face's mouth (jawOpen) does not move → "uncertain"; nothing is reported when it cannot be attributed (no face / several faces) | browser |
| MICROPHONE_DISCONNECTED, CAMERA_DISCONNECTED, PERMISSION_REVOKED | track `ended`/`mute`, getUserMedia errors, Permissions API | browser |
| NETWORK_INTERRUPTION | `offline`/`online` events + failed event uploads; one event per outage (2 s+) | browser |
| SESSION_RECONNECTED | the candidate accepted the notice again for the same interview (page reload) - **recorded by the server** | server |
| INTERVIEW_PAUSED | pause/resume in the room, with the reason (manual / admin pause rule) | browser |
| POSSIBLE_IDENTITY_MISMATCH | **not implemented** - see limitations | - |

The interviewer is excluded from audio checks by design: the microphone is closed while the interviewer speaks, echo
cancellation is on, and nothing is analysed between answers. No audio is recorded or uploaded for these checks (the
answer itself is transcribed as before, §2b).

**Calibration**: the setup screen asks the candidate to sit comfortably, centre their face, look at the screen and
check the light, then offers *Calibrate now* (5 s). The median head/eye position becomes the baseline, so a camera
beside the screen or a different posture is not "looking away". If it is skipped, calibration runs during the first
5 s of the interview. A clearly turned baseline produces a hint to recalibrate (not an error - side cameras are fine).

### Event engine (one path for every detector)
`InterviewMonitor` → `EventReporter` → `POST /api/student/interviews/{id}/integrity-events` → `integrity_events`.
* Each event: type, controlled category, interview-relative start (`t_ms`), duration, confidence (frame agreement),
  whitelisted `details` (`max_faces`, `cause` head/eyes, `edge`, `count`, `reason`), server-assigned severity,
  detection source, review status/notes. API responses add wall-clock `start_timestamp`/`end_timestamp` (the interview
  clock starts at the first consent and **continues across reloads**).
* Consecutive frames are merged into one episode; nothing is sent per frame. Batches every 8 s (or 10 events).
* Duplicates: every event has a `client_event_id`; retries and page-close flushes are stored once (unique index).
* Unsent events survive a reload/crash (sessionStorage) and are flushed on `pagehide` with a keepalive request.
* Server checks: own interview only, consented feature only, interview in progress (3 min grace after finishing), not
  later than the interview clock allows, 50 events per request, 500 per interview, 30 requests/min per interview.
* Reviews never change detected fields; each review is appended to `integrity_reviews` (history visible to admins).

### Security summary (risk score)
`integrity.risk_summary`: rules count related **events** (not frames), multiply by a configurable weight, and are
capped per rule. Defaults: repeated/very long gaze 1, face absent 15 s+ 2, every 3 tab switches (or one 30 s+) 2,
second face 5 s+ 3, every 2 possible additional voices 1, phone 10 s+ 2, long paste 1, fullscreen exit 10 s+ 1,
device interruptions 1. Bands: low ≥ 1, moderate ≥ 4, high ≥ 8. Low-confidence events and events a reviewer marked
no concern / false positive are not counted. Labels are neutral ("Low/Moderate/High number of potential
irregularities"); the response always lists the contributing events and how it was calculated. **These weights are
illustrative engineering values, not validated against real data.** The summary is separate from interview scores
and must never be the sole basis for rejection or any hiring decision.

### Who sees what
* Candidate: their own events, summary, review status (not reviewer notes); can add an explanation.
* Admin: everything, plus review history. Admin → AI & Monitoring → *Interview integrity* and *Security settings*.
* Mentor: with `review_integrity` and only for students they may access (§2e).
* Recruiter (**new**): *Security Reports* page and a section on the candidate page - only **completed** interviews of
  candidates who applied to one of their jobs, only if recruiter access was on **and disclosed when the candidate
  consented** (not retroactive), and only while the admin setting is still on. Recruiters can mark events reviewed /
  false positive / concern noted / further review requested, with notes. They never see consent configuration.

### Admin security settings (`GET/PUT /api/admin/security-settings`, audit-logged with a diff)
Detector switches (face, multiple faces, gaze, focus, full screen, paste, objects, audio), thresholds (frame rate,
calibration time, gaze record/reminder time, yaw/pitch/eye limits, repeat count/window, face and multiple-face
times, tab-switch minimum, audio minimum speech, minimum confidence), reminder cooldown (30 s), pause rule (pause when
no face for N s, default off - the candidate resumes; never ends or fails an interview), severity caps per event type,
risk weights and bands, recruiter access. Global switches stay in platform settings: `monitoring_enabled`,
`monitoring_camera_required`, `monitoring_retention_days` (also editable on the same screen). Each interview stores a
copy of the settings that applied at consent, so later changes affect new interviews only.

### API (all existing paths kept)
| Method | Path | Who |
|---|---|---|
| GET | `/api/monitoring/policy` | signed in (now includes thresholds, cooldown, pause rule) |
| POST | `/api/student/interviews/{id}/monitoring/consent` | student (returns `elapsed_ms`; re-consent = reconnect) |
| POST/GET | `/api/student/interviews/{id}/integrity-events` | student, own interview |
| GET | `/api/monitoring/sessions?q=&date_from=&date_to=&category=&severity=&review_status=&status=&risk=` | admin, mentor*, recruiter* |
| GET | `/api/monitoring/sessions/{id}` | admin, mentor*, recruiter* (report + summary + events) |
| PATCH | `/api/monitoring/events/{id}` | admin, mentor*, recruiter* (status + notes only) |
| GET/PUT | `/api/admin/security-settings` | admin |

### Tests
* `backend/tests/test_security_module.py` (20): own/other interview, duplicates, malformed events, too many events,
  expired interview, future timestamps, rate limit, reconnect + clock, session events, admin-only settings with
  validation/audit/caps/snapshot, monitoring switched off, recruiter access rules, review history, filters, risk.
* `frontend/src/monitoring/security.test.js` (22): calibration, screen-facing / brief glance / prolonged / repeated /
  flickering / low light / no face, partial face, multiple faces, brief dropout, audio attribution, tab switch,
  network outage, reporter ids/retry/reload/429, reminder cooldown and pause rule. Detector inputs are simulated.
* `backend/tests_e2e/security_module_browser.py`: real browser + real MediaPipe + real AI interviewer, fake camera
  built from the app's synthetic 3D interviewer (frontal, head turned 45°, empty room, two faces) and fake microphone.
  Checks reminders, stored events, reconnect, network outage, recruiter report/timeline/review. Result
  2026-10-23: 22/22 (`output/security_module.json`, screenshots `output/sec_*.png`). Headless Chromium did not hide the
  background tab, so the tab switch there is triggered with the real `visibilitychange` event.

### How to try it yourself (real camera and microphone)
1. Start the app, sign in as a student, start a live interview. Tick *Approximate head direction and gaze* and
   *Possible additional voice*, press *Test my camera and microphone*, then *Calibrate now* while looking at the screen.
2. Tick the notice and start. Turn your head away for ~10 s → reminder after ~8 s; leave the frame ~10 s; let a second
   person appear briefly; switch tabs for a few seconds; switch Wi-Fi off for ~10 s; reload the page.
3. While answering, play a voice from your phone without speaking yourself (mouth still) → possible additional voice.
4. Finish, then check *Interview monitoring* on the report; as a recruiter of a job you applied to, open *Security
   Reports*; as admin, *AI & Monitoring → Interview integrity* and *Security settings*.

### Visual attention percentage (2026-10-25)
A live "Visual attention" card (rolling 30 s, coverage, tracking status, Recalibrate) and an "Estimated visual attention" section in
the candidate's, admin's, mentor's and recruiter's monitoring report (overall %, coverage, away time, timeline). Time-based, unobserved
time kept separate, never changes scores. Details, formula, API, tests and limits: `docs/ATTENTION_MONITORING.md`.

### Known limitations (read before relying on it)
* **Not tested with a real human camera or microphone** in this session - only with synthetic faces and recorded audio.
  Thresholds need tuning on real sessions (glasses, beards, masks, poor webcams, different skin tones and lighting).
* Gaze is approximate (head pose + eye blendshapes). It cannot tell what someone looks at; looking away is normal while
  thinking. It is never above "low" severity.
* Additional-voice detection is a heuristic (one microphone cannot separate speakers). A beard, mask, face partly out
  of view or a quiet candidate can cause false signals; speech between answers is not checked.
* **Identity continuity is not implemented**: it would need face recognition / biometric templates, which this
  platform deliberately does not create. The category exists in the taxonomy; there is no detector.
* A web page cannot see other applications, other devices, other tabs' content, or AI tools; it cannot enforce
  lock-down. A modified browser can suppress or forge events - events are signals, the server validates what it can.
* No evidence images are captured (the least intrusive option): reports contain event metadata only.
* Typed interviews (`/student/interviews/:id`) now show the same notice/device check (`InterviewSetup typed`) and run the same detectors via `monitoring/useTypedMonitoring.js` (no microphone / additional-voice check). Browser E2E `tests_e2e	yped_monitoring_browser.py` passes 14/14 (2026-10-25; Chromium's fake camera shows a test pattern, so it checks the wiring - notice, consent, status bar, self-view, stored `focus_change` event, reconnect - not face detection).
* Not built, on purpose: evidence images (metadata only) and face-recognition identity matching (see above).

---

## 3. Tests

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest -q                         # 288 automated tests, ~1.5-3 min, MOCKED models, MongoDB test DB
.\venv\Scripts\python.exe -m pytest tests_integration -s -v    # 9 tests with the REAL local models (LLM, embeddings, TTS, STT), ~3-4 min
.\venv\Scripts\python.exe -m ml.train_question_classifier      # retrain + evaluate the ML component
.\venv\Scripts\python.exe tests_e2e\voice_interview_browser.py # full voice interview in a real browser (needs servers running + playwright)
.\venv\Scripts\python.exe tests_e2e\english_avatar_browser.py  # English practice with Aria: local voice pass + browser voice pass
.\venv\Scripts\python.exe tests_perf\bench_interview_latency.py --runs 6 --mode fast   # stage latencies, real models
.\venv\Scripts\python.exe tests_e2e\latency_monitoring_browser.py   # streamed interview + camera monitoring (set HS_E2E_GPU=1)
.\venv\Scripts\python.exe tests_e2e\face_video_check.py             # face visible / two faces / off-centre, synthetic face video
.\venv\Scripts\python.exe tests_e2e\partial_transcript_check.py     # live partial transcript, no cut-off at sentence pauses
.\venv\Scripts\python.exe tests_e2e\security_module_browser.py    # security module (§2g): gaze/face/two faces/voice/tab/offline/reload + recruiter report
cd ..\frontend; npm test                                       # frontend tests (state machines, lip sync, recorder, speech queue, monitoring)
```
`tests_e2e/voice_interview_browser.py` drives Chromium with a **fake microphone** that plays a spoken answer, and
runs the whole cycle with the real local models. It checks that audio plays, the mouth moves, the mic stays off
while the avatar speaks, transcription works, the next question is generated and spoken, pause/resume and typed
answers work, and the report appears.

`tests/test_local_ai.py` covers resume analysis (valid/empty/corrupted/unsupported files, invalid model output, model missing or not running, removal of invented items, prompt-injection fencing, student corrections), interviews (personalised prompts, evaluation, rule caps, adaptive difficulty up and down, repeated questions, missing/unauthorised sessions), matching (strong/partial/weak, missing required skills, empty profile/job, invalid or unavailable embeddings, eligibility) and system checks (startup without any API key, data isolation, usage logging).
These tests use a **fake model**, so they prove the logic works, not that the real model's answers are good. `tests_integration/` checks the real models on fixed examples.

The original tests cover:
- Authentication and lockout
- Password hashing
- Role-based access
- Mentor-only-assigned-students access
- Recruiter approval and suspension
- Resume upload
- The full interview, reward, and mentor-goal flow (using an AI stub)
- Anti-gaming checks for short answers and copy-paste flagging
- Verified English practice time
- The job application lifecycle and cross-recruiter isolation
- Eligibility checks
- Assessment grading and answer secrecy
- Admin settings and rubric validation

Tests use the MongoDB database `hiresense_test` on the local server (emptied before every test, never the app's
`hiresense` database) and never call the real AI. `tests/test_odm.py` checks the data layer's SQL-style semantics:
unique constraints, ON DELETE cascades, rollback, joins, GROUP BY, NULL handling and ordering.

---

## 4. Database (MongoDB) and file storage

Settings in `backend/.env`:

```
MONGODB_URL=mongodb://127.0.0.1:27017     # or mongodb+srv://user:password@cluster.example.net for Atlas
MONGODB_DB=hiresense
UPLOAD_DIR=                                # optional; default backend/uploads
```

- One collection per model in `backend/app/models.py`; ids are integers from the `_counters` collection.
- No migrations are needed: indexes and unique constraints are created at startup (`database.init_db()`), and a
  field added to a model later simply gets its default when older documents are read.
- `ON DELETE CASCADE / SET NULL` rules declared on the models are applied by the data layer, so deleting a user
  removes their resumes, interviews, applications, etc.
- Uploaded resumes are files on local disk under `backend/uploads/<user id>/`; MongoDB stores only the path.
- **Backup:** `GET /api/admin/backup` (admin only, e.g. from http://127.0.0.1:8000/docs) returns a zip with every collection as MongoDB Extended JSON
  (restore one with `mongoimport --db hiresense --collection <name> --file <name>.json --jsonArray`), or run
  `mongodump --db hiresense`. Copy `backend/uploads/` as well.
- The old SQLite files (`backend/hiresense*.db`) are no longer used and were not imported (they held test and demo
  data: the admin and the three demo accounts with their test interviews). Delete them once you no longer need them.

---

## 5. Project structure

```
backend/
  app/
    main.py            FastAPI app, error logging, security headers
    config.py          settings from .env
    database.py        MongoDB connection, sessions, index setup
    odm/               MongoDB data layer with a SQLAlchemy-style API (select/where/join, Session);
                       coltypes, expressions, statements, mapping, connection, query, session
    models.py          all collections (users, profiles, resumes, interviews, english,
                       assessments, progress, rewards, jobs, applications, mentoring,
                       notifications, audit/AI/error logs, settings)
    schemas.py         request validation
    serializers.py     what each API returns
    security.py        Argon2 hashing, JWT
    deps.py            auth + role guards, mentor-assignment checks
    services/
      ai.py            interview prompts + scoring rules; re-exports every AI feature below
      ai_base.py       the single model gateway (_structured_call): limits, JSON validation, logging
      ai_resume.py, ai_english.py, ai_tasks.py   resume analysis, English practice, smaller AI tasks
      local_llm.py     Ollama client (availability check, timeouts, concurrency limit)
      embeddings.py    Sentence Transformers model (loaded once, cached)
      matching.py      semantic job matching with documented weights
      skills.py        skill aliases + "is this really in the resume?" checks
      question_classifier.py  loads the trained scikit-learn model
      rewards.py       points, badges, streaks, anti-gaming, mentor-goal tracking
      insights.py      shared student performance summary used by all portals
      resume_parser.py PDF/DOCX text extraction
      access.py        who may view which student's detailed records
    routers/           auth, common, students, interviews (+ interview_live: streamed voice turns),
                       english, assessments, jobs/ (student + recruiter), mentors, admin/, voice,
                       monitoring
    seed.py            admin, badges, reward rules, categories, question bank, rubrics
  ml/                  training data, training script, saved model, metrics (see ml/README.md)
  tests/               pytest suite (mocked models)
  tests_integration/   checks with the real local models
frontend/
  src/
    api.js, auth.jsx   API client and session
    components/        UI kit, layout/sidebar/notifications, charts, voice hook
    pages/             login/register/profile/notifications
      student/ recruiter/ mentor/ admin/ shared/
```

---

## 6. API documentation

FastAPI generates interactive docs at **http://127.0.0.1:8000/docs** (Swagger) and **/redoc**. Main route groups:

| Prefix | Who | Purpose |
|---|---|---|
| `/api/auth` | everyone | register (student/recruiter), login, logout, me, change-password |
| `/api/profile`, `/api/notifications` | any signed-in user | profile CRUD, notifications |
| `/api/student/...` | student | dashboard, resumes, interviews, english, assessments, progress, rewards, leaderboard, jobs, applications, mentoring, recommendations |
| `/api/resumes/{id}` | owner / assigned mentor / recruiter with application / admin | view and download a resume |
| `/api/recruiter/...` | recruiter | dashboard, jobs CRUD and publish/close, applications, status updates, AI match, compare, candidate search and detail |
| `/api/assessments` | admin, recruiter | assessment CRUD, results, AI question drafting |
| `/api/mentor/...` | mentor | dashboard, students, student detail, feedback/notes, plans/goals, sessions, AI recommendations |
| `/api/admin/...` | admin | analytics, users, assignments, jobs, categories, question bank, rubrics, badges, reward rules, flagged review, AI usage, errors, audit logs, settings, placement report (JSON/CSV) |

---

## 7. How the portals connect

- **Students** upload a resume and get an AI analysis. They take mock interviews and receive scores and a report. These are stored as progress records, which feed badges and points, update mentor goals, and alert the mentor if a score is low.
- **Mentors** see their assigned students' resume analysis, interviews, English sessions, and assessments. They write feedback and private notes, create improvement plans with goals and deadlines, and schedule sessions. Students are notified, and goals tied to interviews, English, or assessments complete automatically when the student does the work.
- **Recruiters** publish jobs. Eligible students apply and get an instant rule-based match. The recruiter can then run an AI match against the job rubric, compare candidates side by side, and update the status. Every change notifies the student and is recorded in the status history.
- **Admins** approve recruiters, assign mentors, and configure question banks, rubrics, badges, reward rules, and settings. They review flagged activity, which can revoke points, monitor AI usage and errors, and export placement reports. Admin actions are written to the audit log.

---

## 8. Completed features

- Four portals with sidebar navigation, dashboards, summary cards, charts, tables, search and filters, pagination, loading/empty/error states, toasts, notifications, and responsive mobile layout
- Registration and login, with recruiter approval, account suspension and deactivation, roles, and the extra mentor permission `view_all_students`
- AI resume parsing and analysis (skills, education, projects, experience, certifications, strengths, missing skills, improvement areas, readiness score, personalised questions)
- AI mock interviews (technical, HR, behavioral, communication, mixed) in text or voice, with context-aware follow-up questions, per-answer rubric scoring and feedback, and a final report
- AI English conversation practice with live corrections, an evaluation of grammar, vocabulary, fluency, and sentence formation, a pronunciation-clarity estimate in voice mode, and server-verified active time
- Timed MCQ assessments, including job-specific ones, with server-side grading and AI-drafted questions that the author reviews before saving
- Rewards: points, badges with progress, streaks, a leaderboard, daily caps, one award per activity, minimum quality rules, and automatic flagging with admin review and point revocation
- Job management, eligibility checks, applications, status history, interview scheduling, candidate search, explainable AI matching and comparison
- Mentoring: feedback, private notes, improvement plans, auto-tracked goals, follow-up sessions, struggling-student detection, and comparative charts
- Admin analytics, user management, configuration, flagged-activity review, AI quality and usage monitoring, application error log, audit log, and CSV placement report
- MongoDB storage, a seed script, a `.env` configuration, and 288 automated tests

## 9. Known limitations

- **A 4B local model is much weaker than a large cloud model.** It is good enough for practice feedback, and its question quality varies. Scores are practice estimates, not proof of correctness. Since the 2026-11-04 calibration (see "Score calibration" below) it no longer gives 100/100, but it still can't tell a good answer from an excellent one (87 vs 90 on average).
- **Verified with the real model (2026-11-04, `tests_integration/test_real_features.py`, Gemini and Ollama `qwen3:4b`, all 5 tests pass on both):** English conversation and evaluation, AI MCQ generation, code review, student/mentor recommendations (one shared function) and job-role suggestions, plus, from earlier, resume analysis, question generation, answer evaluation, simpler follow-ups and match explanations. Speaking exercises were removed. Problems found and fixed: options numbered by the model ("1: LEFT JOIN"), all-generic recommendations ("technical_skills", every activity a mock interview), Gemini Flash-Lite passing buggy code on a case it fails. **Still possible:** a small model can mark a wrong MCQ answer (seen once with `qwen3:4b`). AI-drafted questions are only a draft that the author reviews before saving.
- **Gemini quota (2026-11-04):** with the configured key, `gemini-3.5-flash` returned HTTP 429 (rate/quota limit) for most requests, so the app answered with `gemini-3.5-flash-lite` and, after timeouts, with Ollama. A request through the HTTP API (`POST /api/student/role-recommendations`) was confirmed answered by `gemini:gemini-3.5-flash-lite` in 2.8 s (perf_metrics `model` field). For steady Gemini use, a paid tier or a higher quota is needed.

### Score calibration (2026-11-04)
`backend/eval/calibration_set.json` holds 16 hand-labelled answers (poor / fair / good / excellent; technical, behavioural and project questions), each with the band a fair interviewer would give. `eval/calibrate_scoring.py` scores them with the live scoring function and reports rank correlation (Spearman), the average per label, the share inside its band, and any 100s. `--baseline` switches the changes below off, so before and after run on the same model. Results are in `eval/results/calibration_*.json`.

| Same model (`qwen3:4b`) | Before | After |
|---|---|---|
| Spearman (label vs score) | 0.80 | **0.95** |
| Inside the expected band | 19% | **56%** |
| Answers scored 100 | 5 | **0** |
| Average: poor / fair / good / excellent | 29 / 70 / 88 / 91 | **13 / 57 / 87 / 90** |

With Gemini (mostly Flash-Lite) before the changes, the first run measured Spearman 0.83, 38% in band and four 100s, one of them a "good" answer missing a key point. A clean Gemini after-run wasn't possible on 2026-11-04 because of the quota: 15 of 16 calls fell back to Ollama.

What changed (`services/ai.py`):
- **Anchored 0-10 scale** in the scoring prompt (`SCORE_ANCHORS`): 10 only when nothing important is missing.
- **`missing_point` before the scores:** the model first names the biggest missing point; if there is one, completeness is capped at 7.
- **Completeness counts:** it was scored but carried no weight in the default rubric, so a shallow but correct answer scored like a complete one. When the rubric leaves it out, it now makes up 20% of the score (`COMPLETENESS_SHARE`).
- **Off-topic bug fixed:** strong, concrete answers to open questions ("Walk me through your most significant project") have only 0.13-0.17 meaning similarity to the question, so the off-topic cap set relevance to 2 and scored them 60-65. Open questions (similarity ≥ 0.60 to a generic "tell me about a project" prompt; specific questions measured 0.11-0.49) now rely on the model's own `answers_the_question`.
- **Mostly wrong technical answers** (correctness ≤ 3) can't keep high relevance, completeness or clarity.
- **Score bands** appear next to the number: Needs work 0-39, Developing 40-59, Competent 60-74, Strong 75-89, Outstanding 90-100 (`services/scoring_bands.py`, `frontend/src/components/scoreBand.js`). Bands and scores never depend on the interviewer persona.
- **Speed:** on a laptop CPU/GPU split, resume analysis takes ~1 minute and each interview answer ~20–40 s (evaluation + next question). Only one AI request runs at a time, so several simultaneous users will queue.
- Skill-name similarity from MiniLM is noisy for very short texts (e.g. Python~Java 0.45). This is why only ≥ 0.50 counts as "partial", and partial matches get half credit.
- The admin **job-match rubric** is no longer used for scoring. Match weights are set by the `MATCH_WEIGHT_*` settings in `.env`.
- The question classifier is trained on a small hand-written development dataset (see `backend/ml/README.md`). Its metrics do not show real-world accuracy.
- No OCR: scanned image-only PDFs are rejected with a clear message.
- **Voice** uses the browser's Web Speech API, which works in Chrome and Edge but not Firefox. "Pronunciation clarity" is estimated from speech-recognition confidence, not a phonetic analysis.
- Scanned (image-only) PDFs can't be parsed because there is no OCR.
- Notifications are in-app only and update every 30 seconds. No emails or SMS are sent.
- Login lockout and rate limiting are tracked in memory per server process. For multi-server production, use Redis or similar.
- The frontend has no automated UI tests; the backend API is covered by pytest.
- For production: set a strong `SECRET_KEY` and `COOKIE_SECURE=true`, serve over HTTPS behind a reverse proxy, and enable MongoDB authentication (a user and password in `MONGODB_URL`).
