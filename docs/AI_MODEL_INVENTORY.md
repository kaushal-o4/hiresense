# AI model inventory

Verified against the source on 2026-10-25. Nothing here was trained or fine-tuned by this project; every model
is a pretrained, publicly available model used as-is, except the small scikit-learn classifier, which this project
trained on its own data (`backend/ml`).

| Model | Provider / runtime | Where it runs | Used for | Config | Notes |
|---|---|---|---|---|---|
| `qwen3:4b` | Ollama 0.40.5 | Local (this laptop: RTX 3050 4 GB, partly CPU) | Resume analysis, interview questions, answer scoring and feedback, interview report, English chat and evaluation, job-match explanation, recommendations, assessment generation, code review | `OLLAMA_MODEL`, `OLLAMA_NUM_CTX`, `OLLAMA_KEEP_ALIVE`, `AI_MAX_CONCURRENT` | Apache-2.0. Thinking disabled (`think: false`). JSON-schema constrained output. |
| `qwen3:1.7b` | Ollama | Local | Candidate for the *fast* tier only; **not enabled**, benchmarked in `PERFORMANCE_BASELINE.md` | `OLLAMA_MODEL_FAST` | Pulled for benchmarking. |
| `sentence-transformers/all-MiniLM-L6-v2` | sentence-transformers (CPU torch) | Local | Job matching similarity, duplicate-question detection, off-topic cap on answer scores | `EMBEDDING_MODEL` | Apache-2.0. |
| `openai/whisper-base.en` | transformers | Local | Speech-to-text for voice interviews and English practice | `STT_MODEL` | The browser's own speech APIs (`speechSynthesis`, `SpeechRecognition`) are also used as a fallback in `components/useSpeech.jsx` and `voice/speechPlayer.js` (not benchmarked). |
| Kokoro-82M | `kokoro` (installed `--no-deps`) | Local | Text-to-speech for all avatar voices | `TTS_VOICE`, `TTS_SPEED` | espeak-ng G2P (GPL-3.0). |
| MediaPipe Face Landmarker | In the browser | Candidate's device | Face/gaze/multiple-face detection for the interview security module | static files in `frontend/public/models` | Frames never leave the browser. |
| Question-type classifier | scikit-learn | Local | Cross-check of question type | `QUESTION_CLASSIFIER_PATH` | **Trained by this project** on its own question set. < 1 MB. |
| Rocketbox avatars | three.js (MIT assets) | Browser | Animated interviewers | n/a | Not an AI model. |

## Not AI (so it is not described as AI anywhere)
* Resume completeness score: a fixed points table.
* Job-match score: weighted formula plus a gap cap; the language model only writes the explanation and cannot change the score.
* Answer-score caps (empty / very short / off-topic answers): deterministic rules applied after the model.
* English topic-switch detection, repeat detection, correction filtering: deterministic code (embeddings for the semantic part).
* Interview-integrity risk summary: deterministic aggregation of browser-detected events.

## Hosted AI
None. No API key is read anywhere. A hosted provider is **not** configured and would need an explicit privacy and
cost decision (see `DEPLOYMENT_READINESS.md`).

## Routing (added 2026-10-25)
`backend/app/services/model_router.py` maps each feature to a tier (`fast`, `strong`, default). Both tier variables
are empty by default, so every feature still uses `OLLAMA_MODEL`. A tier model that is not downloaded falls back to
`OLLAMA_MODEL`, never to a hosted service. `GET /api/health/ready` shows the routing table.
