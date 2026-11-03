# AI and ML Use in HireSense

# AI and ML Use in HireSense
## Detailed Guide to Models, Training, Prompts, Inference, and Integration

## 1. What AI and ML Mean


### Artificial Intelligence (AI)

AI is software that can read, understand, and produce human-like text. In HireSense, AI helps analyse resumes, generate and evaluate interview questions, explain job matches, and coach English.


### Machine Learning (ML)

ML is a branch of AI where software learns patterns from examples. A traditional ML model (small) can be trained on a dataset. A large language model is also learned, but we usually use one that someone else already trained.


### Our simple rule

Ask: did we change the model's weights using our own dataset? If yes, that is training. If no, we are only using a pretrained model or ordinary code.


### AI vs ML vs rules

- AI feature: uses a language model to read/write text (resume analysis, question generation).
- ML feature: a trained classifier (question type).
- Rule-based feature: difficulty thresholds, score caps, matching weights, points table. These are ordinary programming logic, not AI.

## 2. What AI and ML Components Exist

| Component | Type | Where used |
| ---|---|--- |
| Ollama qwen3:4b | Pretrained local LLM | Resume analysis, interview Q/A/evaluation, English coach, match explanation |
| Sentence Transformers all-MiniLM-L6-v2 | Pretrained local embedding model | Job matching, duplicate question detection |
| TF-IDF + logistic regression classifier | Our own trained ML model | Question-type cross-check |
| Kokoro-82M TTS | Pretrained local speech model | Live voice interview speech |
| Whisper base.en STT | Pretrained local speech model | Live voice transcription |
| MediaPipe Face Landmarker | Pretrained browser vision model | Camera monitoring |

## 3. Detailed AI and ML Model-by-Model Explanation


### A. Ollama local LLM: qwen3:4b

- Model name/family: qwen3:4b. A 4-billion parameter general-purpose language model.
- Provider/source: Ollama; Apache-2.0 licensed model.
- Runs locally: Yes. No API key needed.
- Used by: resume analysis, interview question generation, answer evaluation, English coach, AI match explanation.
- Where called: backend/app/services/local_llm.py and backend/app/services/ai.py.
- Configuration: OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_NUM_CTX, OLLAMA_KEEP_ALIVE, AI_TEMPERATURE, AI_MAX_OUTPUT_TOKENS, AI_TIMEOUT_SECONDS, AI_MAX_CONCURRENT, AI_DAILY_LIMIT_PER_USER.
- Typical input: prompt plus context (resume text, skills, previous answers).
- Typical output: structured JSON (skills, education, scores, feedback, questions).
- Validation: JSON schema checks, one retry if invalid, and resume-grounded cleanup removes invented items.
- Training by us: No. It is a downloaded pretrained model. We configure it, build prompts, and parse/validate outputs.

### B. Sentence Transformers: all-MiniLM-L6-v2

- Model: sentence-transformers/all-MiniLM-L6-v2.
- Type: embedding model that turns text into a vector of numbers.
- Runs locally: Yes, downloaded from Hugging Face (~90 MB), Apache-2.0.
- Used by: job matching and near-duplicate question detection.
- Where used: backend/app/services/embeddings.py, matching.py, interview_engine.py.
- Example: similarities between job description and candidate profile; paraphrase detection above 0.78 cosine similarity.
- Training by us: No. We use it pretrained and combine with transparent skill rules.

### C. Our own ML model: question-type classifier

- Task: predict question type (technical, hr, behavioral, communication, project).
- Data: backend/ml/data/interview_questions_dev.csv with 176 hand-written questions, plus 15 de-duplicated admin seed questions = 191 total.
- Method: TF-IDF (word 1-2 grams + character 3-5 grams) + class-balanced logistic regression.
- Training: stratified 75/25 hold-out split and 5-fold cross-validation; final model refit on all data.
- Metrics: hold-out accuracy 0.917; five-fold CV accuracy 0.885 (see backend/ml/README.md).
- Use: stored in InterviewQuestion.meta.classifier as a review cross-check only. It never changes the interview.
- Training by us: Yes. Evidence: backend/ml/train_question_classifier.py and dataset.

### D. Kokoro-82M and Whisper base.en (speech)

- TTS: Kokoro-82M local model for Aria's voice (~330 MB), uses espeak-ng phonemes (GPL-3.0).
- STT: Whisper base.en via transformers for transcription (~150 MB).
- Runs locally: Yes, CPU, downloaded on first use.
- Used by: live voice interview and English avatar sessions.
- Where used: backend/app/services/tts.py, stt.py, speech_stream.py; frontend/src/pages/student/VoiceInterview.jsx.
- Training by us: No. Pretrained models.

### E. MediaPipe Face Landmarker (vision)

- Model: MediaPipe Face Landmarker running in the browser.
- Purpose: detect face presence, multiple faces, gaze/approx direction, lighting for interview monitoring.
- Runs locally in browser; only event records uploaded, never frames/video.
- Used by: frontend/src/monitoring/* and integrity review (backend/app/services/integrity.py).
- Training by us: No. Pretrained.

## 4. Does Our Project Use a Trained Model?

Short answer: We trained one small traditional ML model. We did NOT train or fine-tune the large AI models. Those are pretrained models that we download and run locally.

| Question | Answer |
| ---|--- |
| Did we train a language model from scratch? | No; qwen3:4b is downloaded and run. |
| Did we fine-tune qwen3:4b? | No evidence; none found. |
| Did we train the embedding model? | No; all-MiniLM-L6-v2 is pretrained. |
| Did we train the STT/TTS/vision models? | No. |
| Did we train any ML model? | Yes; the question-type classifier (scikit-learn). |
| Can training evidence be shown? | Yes via backend/ml/train_question_classifier.py and README. |

## 5. How We Use AI in Simple Steps


### A. Resume analysis workflow

```
Student uploads PDF/DOCX
-> frontend src/pages/student/Resume.jsx
-> POST /api/student/resumes
-> backend app/routers/students.py
-> resume_parser.py extracts text
-> services/ai.py builds prompt (resume text wrapped in tags)
-> local_llm.py calls Ollama
-> model returns JSON
-> schema validation + cleanup of invented items
-> resume analysis + completeness score saved
-> frontend shows analysis
```

### B. Interview question generation workflow

```
Start interview request
-> interviews.py creates interview
-> interview_engine.py builds candidate facts from resume
-> services/ai.py builds question prompt
-> local_llm.py gets question from Ollama
-> duplicate checks (wording/meaning/topic)
-> schema validation and output cleanup
-> question stored in DB and returned
```

### C. Answer evaluation workflow

```
Student submits answer
-> interviews.py / answer endpoint
-> ai.py builds evaluation prompt
-> Ollama returns scores 0-10
-> fixed rules apply: empty/'I don't know'<=1, short answers capped
-> adaptive difficulty updated
-> feedback stored and returned
```

### D. Job matching workflow

```
Student applies for job
-> matching.py compares profile and job
-> required/preferred skills coverage
-> semantic similarity via MiniLM embedding
-> experience fit
-> gap cap prevents high score despite missing required skills
-> AI can explain result but cannot change score
```

### E. English practice workflow

```
Student sends message
-> english.py routes
-> english_companion.py manages memory and corrections
-> ai.py/ARIA system prompt
-> Ollama reply + corrections
-> frontend shows coaching and confidence meter
```

## 6. Prompt Engineering

We do not train the model for each feature. Instead we send carefully designed instructions called prompts. A prompt includes context (resume facts, previous answers, role) and asks the model to return structured JSON. The backend validates that output. Prompt engineering means designing and testing these instructions.

- Resume text is wrapped in <resume> tags and the model is told to ignore instructions inside it (prompt-injection protection).
- Each skill/project is checked against the resume text; invented items are removed.
- Questions are checked for duplicates using wording and embedding similarity.
- Answer scoring includes strict caps and meaning checks.

## 7. Why We Chose Local AI

- Privacy: resume text stays on the student's computer.
- No API key needed; no cloud service charges.
- Works offline after models are downloaded.
- Limitation: slower and less accurate than large cloud models; 4B model on laptop hardware takes seconds per response.
- One AI request runs at a time to protect memory.

## 8. Limitations of AI and ML in HireSense

- The 4B LLM can be generous, can repeat questions, and can ignore some instructions.
- Scores are practice estimates, not proof of real interview performance.
- The embedding match can be noisy for short skill text (only >=0.5 similarity counts as partial).
- The trained classifier's data is synthetic and hand-written, so it is not production-ready.
- Voice and webcam depend on browser/GPU/CPU performance and permission; coverage is lower on some browsers.
- No OCR for scanned resumes.

## 9. Evidence from Code

- backend/app/services/ai.py - prompts, schemas, validation, limits, logging.
- backend/app/services/local_llm.py - Ollama client and availability checks.
- backend/app/services/embeddings.py - local embedding model loader.
- backend/app/services/matching.py - transparent weights and gap cap.
- backend/app/services/interview_engine.py - candidate facts, duplicate detection.
- backend/ml/train_question_classifier.py - trained ML script.
- backend/ml/data/interview_questions_dev.csv - training data.
- backend/ml/README.md - method, metrics, limitations.
- backend/.env.example - model names and settings (names only, values not printed).

## 10. Simple Explanation for Viva

For most features, we are using pretrained AI through prompts and validation rules. For one feature, we trained a small scikit-learn model on a hand-written dataset. This is honest engineering: AI helps, but rules and checks keep results reliable.
