# Performance baseline

Hardware: Windows 11 laptop, i5-12450H, 15.7 GB RAM, RTX 3050 Laptop 4 GB, Ollama 0.40.5, `num_ctx` 8192.
Everything below was measured on this machine; nothing is estimated. Raw data: `backend/tests_perf/results/`.

## 1. Interview pipeline (measured earlier, see [PERFORMANCE.md](PERFORMANCE.md))
`bench_interview_latency.py`, `qwen3:4b`, Fast mode, p50 / p95: question 4.1 / 4.5 s, answer scoring 3.3 / 3.4 s,
answer → first spoken sentence 6.1 / 6.4 s, answer → next question complete 7.4 / 7.7 s, first call after start (model
preloaded) 4.7 s. Findings that drove the work: Ollama URL `localhost` cost ~2.1 s per connection on Windows,
token generation (~17-25 tok/s) is the bottleneck, background feedback competed with candidate-facing work.

## 2. Model comparison (2026-10-25, `bench_models.py`, 3 runs, real prompts, in-memory DB)
`tests_perf/results/model_compare.json`. n = 9 chat turns and 18 scored answers per model.

| | qwen3:4b | qwen3:1.7b |
|---|---|---|
| Cold load | 9.3 s | 10.2 s |
| Placement on this GPU | 45% CPU / 55% GPU (4.15 GB) | 100% GPU (2.18 GB) |
| English chat turn, p50 / p95 | **21.9 s / 39.5 s** | **2.3 s / 12.3 s** |
| Chat: correction given on the 2 flawed messages | 5 of 6 | 5 of 6 |
| Answer scoring, p50 / p95 | 2.6 s / 3.3 s | 0.6 s / 0.8 s |
| Strong answer (expect 65-100) | 92, 100, 92 | 100, 100, 100 |
| Concise correct (45-100) | 82.5 ×3 | 90 ×3 |
| Partial (25-70) | 60-62 | **90 ×3 (outside band)** |
| Vague (0-50) | 20-24 | **90 ×3 (outside band)** |
| Incorrect (0-40) | 23, 23, **51** | 0 ×3 |
| Irrelevant (0-25) | 0 ×3 | 0 ×3 |

Reading it: the 1.7B model is fast but **cannot tell a vague or partial answer from a strong one** (the generosity
problem), so it must not score. The 4B model separates the cases, though it gave one incorrect answer 51 (once in 3).
The "expected band" ranges are my sanity ranges, not a validated accuracy figure; six answers × 3 runs is a smoke
test, not an evaluation. Chat quality was only spot-checked by reading 4 replies (grammar fixes correct, followed a
topic switch); it was not scored.

## 3. Model switching on a 4 GB GPU
* Only one of the two models fits on the GPU. Switching costs **5-8 s** (measured: 4b→1.7b 5.6 s, 1.7b→4b 6.7-8.2 s).
* Problem found: with both resident, Ollama put the 1.7B on the **CPU only** and it generated at ~19 tok/s, a whole
  turn taking 13-27 s. Fix: `local_llm._switch_model` unloads the previous model before using a different one.
* After the fix (streaming endpoint, real server, 3 turns): **first text after 0.2 s, whole turn 2.7-4.7 s**, the first
  turn 9.5 s including the 7.2 s load. Ollama's own numbers: generation 1.7-2.5 s for 150-230 tokens.

## 4. Decision
* `english_chat` → `qwen3:1.7b` (`OLLAMA_MODEL_FAST`, enabled in the developer's `backend/.env`). Everything else stays
  on `qwen3:4b`, including answer scoring and the end-of-session English evaluation.
* Trade-off: an English session pays one swap at its start (~6 s) and one at the end (evaluation, ~8 s). If students
  alternate between English chat and interviews on one GPU, each switch costs 5-8 s; with many concurrent users this
  thrashes. On a host with enough VRAM for both models, set `OLLAMA_MAX_LOADED_MODELS=2` and the unload step can be
  removed. Not measured on any other hardware.
* To revert: empty `OLLAMA_MODEL_FAST` in `backend/.env` and restart the backend.

## 5. Not measured
Resume analysis, job matching, mentor/recommendation prompts, grammar correction as a separate task (there is none:
corrections come with the chat turn), CPU/RAM/GPU usage over time, concurrent users, low-memory behaviour, and any
CPU-only host. Browser E2E timings with a real microphone have not been taken.
