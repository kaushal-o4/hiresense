# Performance

Measured on the development laptop (i5-12450H, 16 GB RAM, RTX 3050 4 GB). Raw results are in `backend/tests_perf/results/`; per-model benchmarks in [PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md).

## Frontend bundle (2026-11-04)

| What | Before | After |
|---|---|---|
| JavaScript on first load | 1,130 kB | 236 kB (76 kB gzipped) |
| Four avatar models (GLB) | 16.5 MB | 5.4 MB |

- Every page except sign-in, registration and password reset is lazy-loaded (`React.lazy` in `frontend/src/App.jsx`); react, three and recharts are separate chunks (`vite.config.js`).
- Avatars use meshopt geometry compression and WebP textures (`frontend/avatar-src/compress_avatars.py`, re-runnable from the original exports); `Avatar3D.jsx` loads them with `MeshoptDecoder`. Skinning, 80 bones and 44 morph targets are preserved. The before/after look has not yet been compared on screen.
- MediaPipe (camera monitoring) is only loaded by the pages that use the camera.
- The login page still shows the 3D interviewer, so it downloads the three.js chunk and one model after the form appears.

## Gemini speed (2026-11-04)

`GEMINI_MODEL=gemini-3.5-flash` with automatic switching to `GEMINI_BACKUP_MODELS` (3.5-flash, 3.5-flash-lite) on 503/429/404, when no first token arrives within `GEMINI_SWITCH_AFTER_SECONDS=8`, or on cut-off JSON (non-streamed calls). A busy model is skipped for `GEMINI_MODEL_COOLDOWN_SECONDS`. Measured with `tests_perf/bench_prompts.py` (results `tests_perf/results/prompts_*.json`): scoring 2.2 → 1.1 s (max 24.6 → 1.4 s), feedback/report ~11 → ~2.3 s, resume analysis 56 → 5.3 s; live answer → next question 1-3.8 s. Admin → AI & Monitoring → Performance has an "AI speed by task" card with per-model counts.

## Local models: what made the interviewer slow (2026-10-11)

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
