# Live voice interview and interviewer personalities

> **Current speech stack:** speech-to-text is **faster-whisper** (`STT_ENGINE=faster`, base.en) with the transformers Whisper pipeline as fallback; text-to-speech is **Kokoro-82M**. Both run locally. In the cloud profile (`backend/.env.cloud.example`) Kokoro is off and the browser voice is used, and spoken answers are transcribed by Gemini (`STT_ENGINE=gemini`, no live captions). Questions come from the configured language model (Gemini by default, Ollama fallback). The voice room's UI is split into `frontend/src/voice/` (`RoomParts.jsx`, `RoomSidePanels.jsx`, `RoomSettingsPanel.jsx`, `AnswerDock.jsx`, `ControlBar.jsx`, `roomUtils.js`); the streamed turn endpoint is in `backend/app/routers/interview_live.py`.

## Live voice interview (animated AI interviewer)

Choose **Mock interviews → Mode: Live voice (AI interviewer)**. "Aria", an animated interviewer, asks each question
aloud. You answer by speaking, the answer is transcribed, and it goes through the **same** interview API as text
mode (scoring, adaptive difficulty, follow-ups, rewards and report are unchanged).

```
Start ─► AI writes question (Gemini/Ollama) ─► local TTS (Kokoro) ─► Aria speaks, lips follow phoneme timing
   ▲                                                                    │ audio ends
   │                                                                    ▼
next question ◄─ existing /answer API scores it ◄─ you review/edit ◄─ local Whisper ◄─ mic records (auto-stops on pause)
```

| Part | How | Licence |
|---|---|---|
| Avatars | **Realistic 3D humans** (three.js), one per interviewer (see [Interviewer personalities](#interviewer-personalities-aria-victor-marcus-elena)): Microsoft Rocketbox Female_Adult_01 (Aria, `interviewer.glb`), Business_Male_07 (Victor, `victor.glb`), Business_Male_01 (Marcus, `marcus.glb`), Business_Female_01 (Elena, `elena.glb`). 15 viseme blendshapes drive the lips; ARKit blendshapes drive blinks, smiles, brows and eye direction; bones drive head sway, nods and breathing. Converted once with Blender by `frontend/avatar-src/convert_rocketbox.py` into `frontend/public/avatars/`. If WebGL fails, a simplified 2D SVG avatar is used (Aria's drawing, recoloured for the others). | MIT (`public/avatars/ROCKETBOX_LICENSE.md`) |
| Voice (TTS) | **Kokoro-82M**, local, CPU (~2.5× faster than real time on the test laptop) | Apache-2.0 |
| Phonemes | espeak-ng via `phonemizer-fork` + `espeakng-loader` | **GPL-3.0** (see below) |
| Speech-to-text | **Whisper base.en** via **faster-whisper** (default, ~0.8 s for a 16 s answer) or `transformers` (fallback, ~2 s for 7 s of speech), local, CPU | MIT |
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

### Open items noted on 2026-10-10 (historical; the latency items were addressed later, see [PERFORMANCE.md](PERFORMANCE.md))
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
* The camera is used only for the disclosed interview monitoring (the camera monitoring section of [INTERVIEW_SECURITY.md](INTERVIEW_SECURITY.md)): analysed in your browser, never recorded or
  uploaded; only short event records are stored.
* The browser speech input used by the text pages and the cloud-profile fallback (Web Speech API) sends audio to Google/Microsoft in Chrome/Edge. The live interview with local Whisper does **not** use it.

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

## Interviewer personalities (Aria, Victor, Marcus, Elena)

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
  (older sessions = Aria).
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
* **Runs locally if you want it to:** with `LOCAL_AI_PROVIDER=ollama` everything (Ollama, Kokoro, Whisper, Rocketbox models) runs on your computer with no API key. With the default Gemini provider only the language-model prompts go to Google.

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
