# Third-party models, assets and libraries

HireSense's own code is MIT-licensed ([LICENSE](LICENSE)). The models and assets below keep their own licences.

| Component | Used for | Licence | In this repo? |
|---|---|---|---|
| Microsoft Rocketbox avatars (Female_Adult_01, Business_Male_07, Business_Male_01, Business_Female_01) | 3D interviewers, converted and compressed into `frontend/public/avatars/*.glb` | MIT, © 2020 Microsoft ([`frontend/public/avatars/ROCKETBOX_LICENSE.md`](frontend/public/avatars/ROCKETBOX_LICENSE.md)) | yes |
| MediaPipe Tasks Vision (`@mediapipe/tasks-vision`, WASM in `frontend/public/mediapipe/`) and its Face Landmarker / EfficientDet-Lite0 models (`frontend/public/models/`) | On-device face, gaze and object detection | Apache-2.0 | yes |
| Kokoro-82M | Interviewer voices (text-to-speech) | Apache-2.0 (weights) | no, downloaded on first use |
| espeak-ng (via `phonemizer-fork` and `espeakng-loader`) | Phonemes for Kokoro | **GPL-3.0** | no, installed by pip |
| Whisper base.en (OpenAI) via faster-whisper / transformers | Speech-to-text | MIT | no, downloaded on first use |
| misaki | Kokoro's text front end | MIT | no, installed by pip |
| `qwen3:4b` / `qwen3:1.7b` (via Ollama) | Local language model | Apache-2.0 | no, `ollama pull` |
| `sentence-transformers/all-MiniLM-L6-v2` | Embeddings for matching and duplicate detection | Apache-2.0 | no, downloaded on first use |
| Google Gemini API | Hosted language model (default provider) | Google's API terms | no, a service |

## espeak-ng caveat

espeak-ng and phonemizer are **GPL-3.0**. They are not part of this repository; pip installs them on the machine
that runs the backend. Running HireSense yourself, including for a college or company, is fine. If you **distribute**
a backend build or container image that contains them, the GPL's source-availability terms may apply to that
distribution. The cloud profile (`backend/requirements-cloud.txt`, used by the Dockerfile) does not install Kokoro or
espeak-ng. Set `TTS_ENABLED=false` to avoid them entirely; the browser voice is then used, with approximate lip sync.

Library licences for the Python and npm dependencies are listed in their own packages (`backend/requirements*.txt`,
`frontend/package-lock.json`).
