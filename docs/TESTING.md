# Testing

| Suite | Where | Count (2026-11-05) | Models |
|---|---|---|---|
| Backend unit + API | `backend/tests/` | **358 passed, 2 skipped** (the 2 Redis tests need `fakeredis`) | mocked, MongoDB test database |
| Frontend unit | `frontend/src/**/*.test.js` (Vitest) | **141 passed** | none |
| Real-model checks | `backend/tests_integration/` | 14 tests (`test_real_models.py` 5, `test_real_features.py` 5, `test_voice_real.py` 4) | real Gemini / Ollama, Kokoro, Whisper |
| Browser E2E | `backend/tests_e2e/` | 14 scripts (Playwright) | real or mocked, see below |
| Benchmarks | `backend/tests_perf/` | latency, prompts, STT, models | real |
| Calibration / behaviour eval | `backend/eval/` | `calibrate_scoring.py`, `run_eval.py` | real |

## CI (`.github/workflows/tests.yml`)

Runs on every push and pull request; no GPU and no real models.

- **backend**: MongoDB service container, CPU-only torch, `pytest tests -q`, then the seed twice (must be repeatable).
- **backend-cloud**: the slim `requirements-cloud.txt` environment (no torch/numpy/Whisper); deployment tests plus an
  import-and-seed check.
- **frontend**: `npm ci`, `npm test`, `npm run build`.
- **e2e-smoke**: MongoDB + the API in cloud mode with AI, speech and embeddings off, `vite preview`, then
  `tests_e2e/ci_smoke_browser.py`: registers a student, signs in through the form, opens 15 pages and does one typed
  turn in the live interview room with a fake camera. Screenshots are uploaded as the `e2e-smoke-output` artifact.

## Commands

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests -q                    # mocked suite; temp files go to backend/.pytest_tmp (pytest.ini)
.\venv\Scripts\python.exe -m pytest tests_integration -s -v     # REAL models (Gemini/Ollama, embeddings, TTS, STT)
.\venv\Scripts\python.exe -m ml.train_question_classifier       # retrain + evaluate the ML component
.\venv\Scripts\python.exe eval\calibrate_scoring.py             # score calibration (add --baseline for the old scoring)
.\venv\Scripts\python.exe eval\run_eval.py                      # interview/English behaviour eval (real model)
.\venv\Scripts\python.exe tests_e2e\ci_smoke_browser.py         # the CI smoke test
.\venv\Scripts\python.exe tests_e2e\voice_interview_browser.py  # full voice interview in a real browser (needs servers + playwright)
.\venv\Scripts\python.exe tests_e2e\english_avatar_browser.py   # English practice with Aria: local voice pass + browser voice pass
.\venv\Scripts\python.exe tests_e2e\latency_monitoring_browser.py   # streamed interview + camera monitoring (set HS_E2E_GPU=1)
.\venv\Scripts\python.exe tests_e2e\face_video_check.py         # face visible / two faces / off-centre, synthetic face video
.\venv\Scripts\python.exe tests_e2e\partial_transcript_check.py # live captions, no cut-off at sentence pauses
.\venv\Scripts\python.exe tests_e2e\security_module_browser.py  # interview security module + recruiter report
.\venv\Scripts\python.exe tests_e2e\consent_browser.py          # AI data consent flow
.\venv\Scripts\python.exe tests_perf\bench_interview_latency.py --runs 6 --mode fast   # stage latencies, real models
cd ..\frontend; npm test                                        # Vitest: state machines, lip sync, recorder, monitoring, vocab, SSE
```

Use a separate test database per parallel run with `HS_TEST_MONGODB_DB=<name>` (default `hiresense_test`).
Headless Chromium without a GPU renders the 3D avatar on the CPU and makes E2E steps 3-10x slower; set `HS_E2E_GPU=1`
for representative timings.

## What the suites cover

`tests_e2e/voice_interview_browser.py` drives Chromium with a **fake microphone** that plays a spoken answer and runs
the whole cycle with the real local models. It checks that audio plays, the mouth moves, the mic stays off while the
avatar speaks, transcription works, the next question is generated and spoken, pause/resume and typed answers work,
and the report appears.

`tests/test_local_ai.py` covers resume analysis (valid/empty/corrupted/unsupported files, invalid model output, model
missing or not running, removal of invented items, prompt-injection fencing, student corrections), interviews
(personalised prompts, evaluation, rule caps, adaptive difficulty up and down, repeated questions,
missing/unauthorised sessions), matching (strong/partial/weak, missing required skills, empty profile/job, invalid or
unavailable embeddings, eligibility) and system checks (startup without any API key, data isolation, usage logging).
These tests use a **fake model**, so they prove the logic works, not that the real model's answers are good.
`tests_integration/` checks the real models on fixed examples.

Other backend areas covered: authentication and lockout (memory and Redis limiter), password hashing and reset,
role-based access, mentor-only-assigned-students access, recruiter approval and suspension, recruiter isolation for
compare/report, resume upload, the full interview → reward → mentor-goal flow, anti-gaming checks, verified English
practice time, vocabulary/daily plan/English rewards, the job application lifecycle, eligibility, assessment grading
and answer secrecy, admin settings and rubric validation, live notification streams, AI data consent, score
calibration rules, the interview security module and deployment settings.

Tests use the MongoDB database `hiresense_test` (emptied before every test, never the app's `hiresense` database)
and never call the real AI (`tests/conftest.py`). `tests/test_odm.py` checks the data layer's SQL-style semantics:
unique constraints, ON DELETE cascades, rollback, joins, GROUP BY, NULL handling and ordering.

## Not covered

- No test has used a real person's microphone or camera; detectors and thresholds were checked with fake devices and
  synthetic faces only.
- The Docker images have not been built (Docker isn't installed on the development laptop).
