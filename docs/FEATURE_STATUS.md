# Feature status

As of 2026-10-25, from the source, the README and the tests that exist. Legend: **Done** = implemented and covered by
tests; **Done (mocked)** = tests use a fake model; **Real-model checked** = also run against `qwen3:4b`;
**Partial**; **Not built**; **Unmeasured** / **Not tested with a person** = no evidence either way.

| Area | Status | Notes |
|---|---|---|
| Four portals, auth, roles, approvals | Done | Backend suite covers permissions. No automated UI tests except vitest unit tests (101). |
| Resume upload + analysis | Done, Real-model checked | Output is validated against the resume text (invented items removed). ~60 s on this laptop. No OCR. |
| AI interview (text + live voice, 4 personalities) | Done, Real-model checked | Browser E2E with a fake microphone only. **Not tested with a person.** |
| Answer scoring | Done, Real-model checked | Rubric + deterministic caps. README §2f documents an eval; the generosity of the 4B model is a known limit. A labelled six-answer check is in `tests_perf/bench_models.py`. |
| Interview security module | Done | Event-based, never changes scores. **Not tested with a real camera/mic.** No identity matching by design. |
| Visual attention % (live card, rolling window, coverage, timeline, report for candidate/admin/mentor/recruiter) | Added 2026-10-25, Done (unit + API tests + real-MediaPipe browser test with a synthetic face) | `docs/ATTENTION_MONITORING.md`. Time-based formula, unobserved time kept separate, client-measured and not tamper-proof. **Not tested with a human face or real webcam; thresholds not tuned on real candidates.** |
| English companion (3 learning modes, topic memory) | Done, Real-model checked (eval, 3 sessions) | Memory is per session (`EnglishSession.memory`). |
| English streamed replies (text chat) | Added 2026-10-25, Done (mocked) | `POST /english/{id}/message/stream`. The avatar voice page still uses the non-streamed endpoint. |
| English session evaluation | Done | Scores grammar/vocabulary/fluency/sentence formation at the end of a session. |
| English recurring-mistake profile | Added 2026-10-25, Done (mocked) | `services/english_profile.py`, table `english_mistake_patterns` (migration `a1d5c8e2f490`). Rule-based categories (verb tense, articles, prepositions, subject-verb agreement) from corrections already given; "recurring" needs 3 corrections in 2+ sessions; students can dismiss one or clear all (card on the English page); in "English learning" mode the top 2 recurring patterns are added to the chat prompt. Categories are approximate; the effect on learning has **not** been measured and the prompt note has not been checked with the real model. |
| English vocabulary review, daily plan, progress dashboard, rewards for English milestones | **Not built** | Close to the drills removed on 2026-10-11, so left out pending the owner's decision. General weakness→remedy suggestions from interviews/assessments exist (`services/insights.py`) but do not use English corrections. |
| Speaking/pronunciation drills | Removed on purpose | Removed at the owner's request on 2026-10-11; data kept; not to be re-added without asking. |
| Job matching | Done | Formula + embeddings; the LLM only explains. Labelled "keyword only" without embeddings. |
| Assessments (MCQ), AI-drafted questions | Done; drafted questions Done (mocked) | |
| Rewards / badges | Done | English practice earns points through verified active time. |
| Mentor features, admin analytics, audit log | Done | |
| Perf instrumentation | Done | `perf_metrics` table, admin Performance page. CPU/GPU/memory usage is **not** recorded. |
| Model routing | Added 2026-10-25, Done (mocked) | Off in the code defaults; enabled for English chat only (`qwen3:1.7b`) in the developer's `backend/.env` after the benchmark in `PERFORMANCE_BASELINE.md`. See `AI_MODEL_INVENTORY.md`. |
| Health/readiness endpoints, request IDs, secret-key check | Added 2026-10-25, Done | |
| Deployment (Docker, process manager, PostgreSQL run) | **Not built / not tested** | See `DEPLOYMENT_READINESS.md`. |

## Stale statements in README.md
§8–9 were written early and are partly out of date: "19 automated tests" (now 230+), "Voice uses the browser's Web
Speech API" (voice now uses Whisper + Kokoro, with the browser as a fallback), "no emails" (SMTP is supported).
Prefer the dated sections §2b–2g.
