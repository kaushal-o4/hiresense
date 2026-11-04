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
| English vocabulary review (spaced repetition) | Added 2026-11-04, Done (mocked) | `services/english_vocab.py`, collections `english_vocabulary` + `english_vocabulary_reviews`, page `/student/english/vocabulary`. Aria's corrections become cards automatically (said → better way to say it + her explanation); students can add or delete their own words. Leitner boxes 1-5 with 1/2/4/7/14-day gaps; "not yet" → box 1, knowing a box-5 card = mastered; the same mistake again restarts its card. No AI call. Effect on learning **not measured**. |
| English daily plan | Added 2026-11-04, Done (mocked) | `GET /student/english/daily-plan`; on the English page and the student dashboard. Items tick themselves: review up to 10 due words, one conversation in the mode suggested by the weakest skill of the last evaluated session (grammar/sentences → English learning, fluency → confidence, vocabulary → free conversation), one interview answer. UTC days. |
| English progress view | Added 2026-11-04, Done (mocked) | `GET /student/english/progress`: words in list / learned (box ≥ 4) / mastered, review accuracy by week, skill scores per session, plan days completed. |
| Rewards for English milestones | Added 2026-11-04, Done (mocked) | Seeded (repeatable): rules `english_daily_plan` (15 pts, once a day) and `english_word_mastered` (5 pts, max 10/day); badges Word Collector (25 learned), Vocabulary Builder (10 mastered), Daily Planner (7 plan days); weekly challenge "Word workout" (30 reviews, metric `english_reviews`). New badge criteria are selectable in Admin → Rewards. |
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
