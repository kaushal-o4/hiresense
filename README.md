# HireSense

**AI-Powered Intelligent Interview and Placement Assessment System.** It has four portals (Student, Recruiter, Mentor, Admin) that share one database and API.

The full requirements are in [PROJECT_SPEC.md](PROJECT_SPEC.md).

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Recharts, React Router |
| Backend | Python FastAPI, SQLAlchemy 2, Alembic migrations |
| Database | SQLite by default. PostgreSQL is supported by changing `DATABASE_URL`. |
| Auth | JWT in an httpOnly cookie (Bearer header also accepted). Argon2 password hashing. Role-based access is enforced on the backend. |
| AI (text) | **Local** language model via [Ollama](https://ollama.com): `qwen3:4b` by default, with JSON-schema-constrained outputs. No API key is needed and no student data leaves the computer. |
| AI (matching) | **Local** Sentence Transformers embeddings (`all-MiniLM-L6-v2`) + transparent skill rules |
| ML | scikit-learn question-type classifier, trained offline (`backend/ml/`) |
| Resumes | `pypdf` (PDF) and `python-docx` (DOCX) |
| Voice | Browser Web Speech API for speech-to-text and text-to-speech (Chrome/Edge) |

---

## 1. Run it (Windows, VS Code)

You need **Python 3.12+** (`py --version`), **Node.js 20+** (`node --version`) and **Ollama** for the AI features (see section 2).

### Easiest way
Double-click these two files, or run them from the VS Code terminal:

```
start-backend.bat     -> API on http://127.0.0.1:8000  (docs: http://127.0.0.1:8000/docs)
start-frontend.bat    -> App on http://localhost:5173
```

Then open **http://localhost:5173**.

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
alembic upgrade head                  # create/upgrade database tables
python -m app.seed --demo             # admin + defaults (+ demo accounts)
uvicorn app.main:app --reload --port 8000

# Terminal 2 - frontend
cd frontend
npm install                           # first time only
npm run dev
```

### Accounts after seeding

| Role | Email | Password |
|---|---|---|
| Admin | admin@hiresense.app | Admin@12345 (set in `backend/.env`) |
| Student (demo) | student@demo.hiresense | Demo@12345 |
| Mentor (demo) | mentor@demo.hiresense | Demo@12345 |
| Recruiter (demo) | recruiter@demo.hiresense | Demo@12345 |

The demo accounts are empty, with no fake scores or activity. The `--demo` flag creates them; leave it out in production and change the admin password.

---

## 2. Turn on the AI features (local, free, private)

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
* The camera is optional, off by default, only shown to you, and never recorded or uploaded.
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

## 3. Tests

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest -q                         # 95 automated tests, ~1.5 min, MOCKED models
.\venv\Scripts\python.exe -m pytest tests_integration -s -v    # 9 tests with the REAL local models (LLM, embeddings, TTS, STT), ~3-4 min
.\venv\Scripts\python.exe -m ml.train_question_classifier      # retrain + evaluate the ML component
.\venv\Scripts\python.exe tests_e2e\voice_interview_browser.py # full voice interview in a real browser (needs servers running + playwright)
.\venv\Scripts\python.exe tests_e2e\english_avatar_browser.py  # English practice with Aria: local voice pass + browser voice pass
cd ..\frontend; npm test                                       # 27 frontend tests (state machines, lip sync, recorder)
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

Tests use an in-memory database and never call the real AI.

---

## 4. Switching to PostgreSQL

```powershell
cd backend
pip install -r requirements-postgres.txt
# in .env:
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/hiresense
alembic upgrade head
python -m app.seed
```

---

## 5. Project structure

```
backend/
  app/
    main.py            FastAPI app, error logging, security headers
    config.py          settings from .env
    models.py          all database tables (users, profiles, resumes, interviews, english,
                       assessments, progress, rewards, jobs, applications, mentoring,
                       notifications, audit/AI/error logs, settings)
    schemas.py         request validation
    serializers.py     what each API returns
    security.py        Argon2 hashing, JWT
    deps.py            auth + role guards, mentor-assignment checks
    services/
      ai.py            every AI feature: prompts, JSON schemas, validation rules, limits, logging
      local_llm.py     Ollama client (availability check, timeouts, concurrency limit)
      embeddings.py    Sentence Transformers model (loaded once, cached)
      matching.py      semantic job matching with documented weights
      skills.py        skill aliases + "is this really in the resume?" checks
      question_classifier.py  loads the trained scikit-learn model
      rewards.py       points, badges, streaks, anti-gaming, mentor-goal tracking
      insights.py      shared student performance summary used by all portals
      resume_parser.py PDF/DOCX text extraction
      access.py        who may view which student's detailed records
    routers/           auth, common, students, interviews, english, assessments,
                       jobs (student + recruiter), mentors, admin
    seed.py            admin, badges, reward rules, categories, question bank, rubrics
  alembic/             migrations
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
- Alembic migrations, a seed script, a `.env` configuration, and 19 automated tests

## 9. Known limitations

- **A 4B local model is much weaker than a large cloud model.** It is good enough for practice feedback, but it can be generous (a strong answer scored 100/100 in testing), and its question quality varies. Scores are practice estimates, not proof of correctness.
- **Verified with the real model:** resume analysis, question generation, answer evaluation, simpler follow-ups and match explanations (`tests_integration/`, plus a live end-to-end run). **Not yet verified with the real model:** English conversation/evaluation, speaking exercises, AI MCQ generation, code review, student/mentor recommendations and job-role suggestions. They use the same validated pipeline, but test each once.
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
- For production: set a strong `SECRET_KEY` and `COOKIE_SECURE=true`, serve over HTTPS behind a reverse proxy, and use PostgreSQL.
