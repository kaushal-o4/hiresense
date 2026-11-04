# English practice

Spoken and typed English practice with Aria (the English companion), plus vocabulary review, a daily plan, a progress
view and English rewards (added 2026-11-04). The old pronunciation/speaking drills were removed on 2026-10-11 at the
owner's request; their data is kept and the `/student/english-learning` route redirects to `/student/english`.

Code: `backend/app/routers/english.py`, `services/english_companion.py`, `services/english_profile.py`,
`services/english_vocab.py`, `services/ai_english.py`; `frontend/src/pages/student/English.jsx`,
`EnglishSession.jsx`, `EnglishAvatarSession.jsx`, `Vocabulary.jsx`, `components/DailyPlan.jsx`,
`components/EnglishProgress.jsx`, `src/english/vocab.js`.

## Speak with Aria (avatar)

`/student/english` → Mode **Speak with Aria (avatar)**, Practice **English free talk** or **Job interview practice**.
The session page (`frontend/src/pages/student/EnglishAvatarSession.jsx`, loop in `src/voice/englishMachine.js`) runs
hands-free: Aria speaks with lip sync and highlighted subtitles → the mic opens → the student talks → a ~4 s pause
or **Done** → local Whisper (`POST /api/student/english/{id}/transcribe`) → Aria thinks → replies. Text-mode
sessions keep the plain chat page, whose replies stream from `POST /api/student/english/{id}/message/stream`.

- Persona: `ARIA_SYSTEM` in `backend/app/services/ai_english.py`. Each reply returns `reply`, `avatar_mode`
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

## English conversation companion (2026-10-11)

**English conversation companion** (`services/english_companion.py`): a separate personality from the interviewers
(Aria's avatar and voice, no interview pressure). Three learning modes chosen on the start screen:
*Free conversation* (at most one on-screen tip, spaced out, never spoken), *English learning* (a short spoken "a more
natural way to say that is...", then the conversation continues; the same correction is never repeated) and
*Confidence* (short easy questions, 0.85x speech, 6.5 s before the turn ends, example answers). Topic changes such as
"Actually, can we talk about movies?" are detected in code; if the model ignores one, the reply is regenerated.
A compact memory (current/earlier topics, interests, details, questions asked, corrections given; sensitive details
are never stored) is sent instead of the full transcript and shown as "What Aria remembers". Wrong corrections are
filtered (British/American spelling, rewrites much longer than what was said, invented quotes).

Evaluation of the companion (topic following, 3 sessions, 100% incl. 2 topic switches) is in
[AI_MODELS_AND_SCORING.md](AI_MODELS_AND_SCORING.md#interview-intelligence-and-the-english-conversation-companion-2026-10-11).

## Recurring-mistake profile (2026-10-25)

`services/english_profile.py`, collection `english_mistake_patterns`. Rule-based categories (verb tense, articles,
prepositions, subject-verb agreement) from corrections already given; "recurring" needs 3 corrections in 2+ sessions.
Students can dismiss one or clear all (card on the English page). In "English learning" mode the top 2 recurring
patterns are added to the chat prompt. Categories are approximate; the effect on learning has **not** been measured.

## Vocabulary review (spaced repetition, 2026-11-04)

Page `/student/english/vocabulary`, `services/english_vocab.py`, collections `english_vocabulary` and
`english_vocabulary_reviews`.

- Each correction Aria gives becomes a card automatically: what the student said → the better way to say it, plus
  her explanation. Students can also add or delete their own words.
- Leitner boxes 1-5, shown again after 1, 2, 4, 7 and 14 days. "Not yet" sends a card back to box 1; knowing a box-5
  card marks it mastered. Making the same mistake again restarts that card.
- A "not yet" card is shown once more at the end of the session (on screen only, not saved).
- No AI call is involved in reviewing.

## Daily plan (2026-11-04)

`GET /api/student/english/daily-plan`, shown on the English page and as a card on the student dashboard. Up to three
items, each ticked automatically from what the student did today:

1. review up to 10 due words;
2. one conversation in the mode suggested by the weakest skill of the last evaluated session (grammar or sentences →
   English learning, fluency → confidence building, vocabulary → free conversation);
3. answer one interview question.

Finishing the whole plan awards points once a day. Days are counted in UTC like the rest of the app. Because the
interview item is completed outside the English pages, viewing the plan is what checks it and can award the daily
points; it never pays twice for the same day.

## Progress and rewards (2026-11-04)

- `GET /api/student/english/progress`: words in the list, learned (box ≥ 4) and mastered, review accuracy by week,
  skill scores per session (grammar, vocabulary, fluency, sentence formation) and days with the whole plan finished.
- Reward rules (seeded, repeatable): `english_daily_plan` (15 points, once a day) and `english_word_mastered`
  (5 points, at most 10 a day).
- Badges: Word Collector (25 learned), Vocabulary Builder (10 mastered), Daily Planner (7 plan days). The Daily
  Planner badge counts days on which the plan points were paid, so it can't be earned if an admin switches that rule
  off.
- Weekly challenge "Word workout" (30 reviews, metric `english_reviews`). The new badge criteria are selectable in
  Admin → Rewards.

## Session evaluation

Each finished session is scored on grammar, vocabulary, fluency and sentence formation. Checked with the real models
on 2026-11-04 (`backend/tests_integration/test_real_features.py`): for messages with clear tense/agreement errors
Gemini Flash-Lite gave grammar 4/10 and `qwen3:4b` 6/10.

## Limits

- English only: Kokoro and Whisper base.en support only English.
- The effect of the vocabulary review and daily plan on learning has not been measured.
- Not tried with a real human microphone yet.
