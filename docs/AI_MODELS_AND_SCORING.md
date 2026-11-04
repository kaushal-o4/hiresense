# AI models, scoring and interview intelligence

How HireSense uses language models: providers (Gemini by default, local Ollama as fallback or for fully offline use), what each AI feature does, the deterministic checks around the model, the interview question engine and the 2026-11-04 score calibration. Model inventory: [AI_MODEL_INVENTORY.md](AI_MODEL_INVENTORY.md).

> **Provider (current):** `backend/.env.example` sets `LOCAL_AI_PROVIDER=gemini`. With a key, prompts go to Google Gemini and Ollama answers only when Gemini fails (`AI_FALLBACK_TO_OLLAMA=true`). Set `LOCAL_AI_PROVIDER=ollama` to keep every prompt on your own computer. Students must accept the AI data notice before the first AI feature when the provider is Gemini (`services/consent.py`, `/privacy`).

## Local AI (Ollama): setup and how each feature works

With `LOCAL_AI_PROVIDER=ollama`, all AI runs on your own computer: nothing is sent to an outside AI service and no API key is needed.

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

## Gemini API (fast, hosted) - default provider since 2026-10-29

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

## Interview intelligence and the English conversation companion (2026-10-11)

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

## Known limitations of the AI

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
