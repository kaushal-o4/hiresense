# HireSense AI: Project Explanation for the Viva

Simple-English explanation of the **actual implementation**, for the project presentation and viva. File names
are the real ones in the repository.

---

## A. Project introduction

HireSense AI is a web application that prepares students for campus placements. A student can:
- upload a resume, which the AI analyses
- practise mock interviews with an AI interviewer, by typing or by speaking with a 3D talking avatar
- get a score and feedback for every answer and a final report
- see a placement-readiness score on a dashboard

The other users are:
- **recruiters**, who post jobs and see applicants ranked by a match score
- **mentors**, who track their assigned students and set goals
- **the placement admin**, who manages users, the question bank and the scoring rubric, and sees reports

The system is an **AI-assisted first-level assessment**. It helps students practise and helps staff find who
needs support, but it never takes a hiring decision on its own.

## B. Problem statement

- Students get very few chances to practise real interviews before campus placements, and almost no detailed
  feedback on *what* was weak in their answers.
- Placement cells cannot interview hundreds of students one by one to find out who is ready.
- Recruiters spend time on applicants who do not match the job.
- Existing online tools are generic. They do not ask questions about *your* resume and do not adapt to your
  answers.

## C. Objectives

1. Conduct realistic, resume-based mock interviews whose difficulty adapts to the student's answers.
2. Evaluate every answer fairly and explainably: per-criterion scores, fixed rules on top of the AI, and
   feedback with a sample answer.
3. Produce an interview report and a placement-readiness score, and show progress over time.
4. Analyse resumes and identify skills and skill gaps against jobs.
5. Give recruiters, mentors and admins dashboards for their tasks.
6. Respect privacy:
   - a fully local AI option (Ollama), and consent before data goes to a hosted AI
   - hashed passwords
   - monitoring only with consent, and never used for scoring

## D. Complete working (student registration to final evaluation)

1. **Register and log in.**
   - `Register.jsx` calls `POST /api/auth/register/student`.
   - The password is hashed with Argon2 and a JWT is set in an httpOnly cookie.
2. **Profile and resume.**
   - The student uploads a PDF or DOCX file to `POST /api/student/resumes`.
   - The text is extracted and the AI pulls out skills, projects and education.
   - Every item is checked against the resume text, and a completeness score is calculated.
3. **Configure the interview.**
   - The student picks an interviewer (Aria, Victor, Marcus or Elena), the job role, the category, text or voice
     mode, and the number of questions.
   - These go to `POST /api/student/interviews`.
4. **Question generation.**
   - The backend builds a prompt from the role, the resume facts, the previous answers and the chosen
     difficulty, and the AI returns a question as JSON.
   - Duplicate or bad questions are rejected and regenerated.
   - If the AI is down, the admin question bank is used.
5. **Answering.**
   - The student types the answer, or speaks it; Whisper converts speech to text.
   - It is submitted with `POST .../answer` (text) or `POST .../turn` (live voice).
6. **Evaluation.**
   - The AI gives 0-10 scores for relevance, correctness, completeness, clarity and communication.
   - Fixed rules cap the scores for off-topic, very short or copied answers.
   - The weighted rubric gives a 0-100 score.
7. **Adaptive next question.**
   - A score of 75 or more makes the next question harder; below 45 makes it easier.
   - Gaps in the answer (for example "we did it" without the student's own role) produce a follow-up question.
8. **Feedback.** Detailed tips and a sample answer are written in the background.
9. **Completion and report.**
   - The overall score is the average of the answer scores.
   - The AI writes the report: summary, strengths, weaknesses and suggestions.
   - Calculated metrics are added: technical and communication averages, pace and filler words.
10. **After the interview.**
    - Progress records, points and badges are saved, and mentors are alerted if the score is low or drops.
    - The dashboard shows the readiness score and trends.

## E. Frontend explanation

- Built with **React 18** and **Vite**, styled with **Tailwind CSS**.
- `main.jsx` renders `App.jsx` inside `AuthProvider` (who is signed in) and `ToastProvider` (pop-up messages).
- `App.jsx` defines every URL. `RequireRole` sends users of the wrong role to their own home page. Most pages
  are loaded only when opened (`lazy`), so the first load is fast.
- `apiClient.js`:
  - every page calls the backend through it, with `get`, `post`, `put`, `patch` and `del`
  - it sends the login cookie and turns server errors into readable messages
- `AuthContext.jsx` calls `GET /api/auth/me` on load, so the session survives a page refresh.
- Pages are grouped by role: `pages/student`, `pages/recruiter`, `pages/mentor`, `pages/admin`.
- Shared building blocks are in `components/`:
  - `SharedUiComponents.jsx`: buttons, cards, tables and the `useApi` loading hook
  - `DashboardCharts.jsx`: charts drawn with Recharts
- The live interview room (`LiveVoiceInterview.jsx` + `voice/`):
  - records the microphone (`recorder.js`)
  - plays the interviewer's voice (`speechPlayer.js`)
  - shows a **three.js** 3D avatar whose lips follow the audio (`Avatar3D.jsx`)
  - uses state machines (`interviewMachine.js`) to stop double submissions
- `monitoring/` (optional, with consent): MediaPipe checks the camera in the browser and sends only short event
  records.

## F. Backend explanation

- Built with **FastAPI** (Python) and run by **uvicorn**. `main.py` creates the app, registers all route files,
  adds security headers, logs unhandled errors to the database and warms up the AI models at startup.
- **Routers** (`app/routers/`) define the 203 endpoints:
  - **Pydantic** models in `request_validation_schemas.py` validate input
  - `Depends(get_db)` gives each request a database session
  - `Depends(require_student)` (and similar) checks the logged-in user and role
- **Services** (`app/services/`) hold the logic, grouped into folders:
  - interview, resume_and_jobs, english, voice, monitoring, student_progress, platform_support
  - ai_models, the single gateway to the AI
- **Security:**
  - Argon2 password hashes
  - JWT in an httpOnly cookie
  - login lockout after repeated wrong passwords
  - role checks on every endpoint, and ownership checks (a student can only open their own interviews)
  - audit logs
- **Background jobs** (`background_jobs.py`) write the slow detailed feedback after the response is sent, so the
  student does not wait.

## G. AI integration

- **Language model:**
  - Two providers, chosen with `LOCAL_AI_PROVIDER` in `backend/.env`:
    - Google **Gemini** (the setting in `.env.example`). It is fast. Students must accept a data notice first.
    - A local **Ollama** model, `qwen3:4b`, running on the same computer, so nothing leaves the machine. When
      Gemini is selected but fails (no key, no quota, no internet), the app automatically falls back to Ollama
      (`AI_FALLBACK_TO_OLLAMA=true`).
- **One gateway:** every AI call goes through `_structured_call()` in `ai_structured_call_base.py`, which:
  - checks that AI is enabled and the daily usage limit
  - forces the model to answer in a fixed **JSON schema** and validates it with Pydantic, retrying once
  - logs status, time and token counts, never the content
  - wraps untrusted text (resume, answer) in tags as a prompt-injection guard
- **What the AI does:**
  - writes interview questions
  - scores answers (0-10 per criterion)
  - writes feedback and sample answers, and the final report
  - extracts resume details
  - explains job matches, writes recommendations, drafts MCQs, reviews code
  - acts as the English conversation partner
- **What the AI does NOT decide:**
  - the final 0-100 score (calculated by the rubric formula after the rule caps)
  - the next difficulty (rule-based)
  - the job match score (formula)
  - the readiness score (formula)
- **Other models:**
  - **Sentence Transformers** (`all-MiniLM-L6-v2`): meaning similarity for job matching and off-topic answers
  - **our own scikit-learn classifier**: predicts question type and difficulty as a cross-check
  - **Whisper** (speech-to-text) and **Kokoro** (text-to-speech with lip-sync data)

## H. Database explanation

- **MongoDB** stores 49 collections defined in `database_models.py`. The main ones:
  - `users`
  - `student_profiles`
  - `resumes` (text + AI analysis)
  - `interview_sessions` (settings, overall score, report)
  - `interview_questions`
  - `interview_answers` (scores, feedback)
  - `jobs`, `job_applications`
  - `assessments`, `assessment_results`
  - `english_sessions`, `english_messages`
  - `notifications`, `audit_logs`, `ai_usage_logs`
- The project has its own data layer, `mongodb_data_layer/`. Code is written SQLAlchemy-style, e.g.
  `db.scalars(select(User).where(User.email == email))`, but the data is stored as MongoDB documents.
- Documents are linked by integer ids, for example `interview_answers.question_id` points to
  `interview_questions.id`.
- Unique indexes stop duplicates, such as two applications to the same job.

## I. File structure (main folders)

- `frontend/src/pages/*`: screens per role
- `frontend/src/components/*`: shared UI
- `frontend/src/voice/*`: live interview room
- `frontend/src/monitoring/*`: opt-in camera checks
- `backend/app/routers/*`: API endpoints
- `backend/app/services/*`: business logic
- `backend/app/database_models.py`: database
- `backend/app/mongodb_data_layer/*`: database access layer
- `backend/ml/`: our classifier
- `backend/tests/`: automated tests
- `documentation/`: these documents

Every source file begins with a "comment index" that explains it.

## J. Important functions (simple language)

| Function | File | What it does |
|---|---|---|
| `login()` | `routers/authentication_routes.py` | Checks the password hash, applies the lockout, sets the JWT cookie |
| `get_current_user()` | `authentication_dependencies.py` | Reads the cookie, verifies the JWT, loads the user |
| `upload_resume()` | `routers/student_portal_routes.py` | Saves the file, extracts the text, runs the AI analysis |
| `analyze_resume()` / `validate_resume_extraction()` | `services/resume_and_jobs/ai_resume_analyzer.py` | AI extraction, then removes anything not in the resume text |
| `start_interview()` | `routers/interview_routes.py` | Creates the interview and its first question |
| `_add_next_question()` | `routers/interview_routes.py` | Builds the context, gets an AI question, rejects duplicates, falls back to the bank |
| `next_interview_question()` | `services/interview/ai_interview_service.py` | The prompt + JSON schema for one question |
| `score_answer()` | same | AI criterion scores, then rule caps, then the weighted score |
| `apply_answer_rules()` | same | Caps scores for off-topic, empty, short, copied or mostly wrong answers |
| `weighted_score()` | same | Rubric-weighted average converted to 0-100 |
| `next_difficulty()` | same | 75 or more: harder; below 45: easier |
| `answer_feedback()` | same | Strengths, missing concepts, tips, sample answer (in the background) |
| `interview_report()` | same | Final AI report |
| `report_metrics()` | `services/interview/interview_report_metrics.py` | Calculated report numbers (no AI) |
| `compute_match()` | `services/resume_and_jobs/semantic_job_matcher.py` | Job match score and missing skills |
| `readiness_score()` | `services/student_progress/student_performance_insights.py` | Weighted placement readiness |
| `award_points()` | `services/student_progress/rewards_and_badges.py` | Points with anti-gaming rules |
| `_structured_call()` | `services/ai_models/ai_structured_call_base.py` | The single, validated, logged path to the AI |

## K. Technology stack and responsibilities

| Technology | Responsibility |
|---|---|
| React 18, React Router, Vite | User interface, page routing, dev server and build |
| Tailwind CSS, lucide-react, Recharts, three.js | Styling, icons, charts, the 3D avatar |
| MediaPipe (browser) | Optional on-device camera checks |
| FastAPI, uvicorn, Pydantic | REST API, server, validation |
| PyJWT, argon2-cffi | Login tokens, password hashing |
| MongoDB, pymongo | Database |
| Ollama (qwen3:4b) / Gemini | Language model |
| Sentence Transformers | Meaning similarity |
| scikit-learn | Our question classifier |
| faster-whisper / Kokoro | Speech-to-text / text-to-speech |
| pytest, Vitest, Playwright, GitHub Actions | Testing and CI |

## L. Real-time example

Riya, a final-year CSE student, wants to practise for a "Python Backend Developer" role.

1. She registers and uploads her resume.
   - The AI finds the skills Python, Django and MySQL, and a project, a "Hospital bed allocation system".
   - The completeness score is 72/100, and the page suggests adding certifications.
2. She starts a **technical**, **voice** interview with **Aria**: 5 questions, medium difficulty.
3. **Q1** (medium): "In your hospital bed allocation system, how did you design the database tables for beds and
   patients?"
   - She answers well. The scores are relevance 8, correctness 8, completeness 7, clarity 7, communication 8.
   - The weighted score is about 77, so the next question becomes **hard**.
4. **Q2** (hard): a scaling question.
   - She says "we made it faster" without numbers.
   - The answer signal "unmeasured claim" leads to the follow-up **Q3**: "How did you measure that improvement?"
5. One short answer, "I am not sure", is capped at 3/10 per criterion by the rules, so that question scores low.
6. She finishes. The overall score is the average of the 5 answer scores, for example 64.
   - The report lists her strengths (database design) and weaknesses (performance measurement, caching).
   - Its metrics show a speaking pace and a few filler words.
7. She earns points and the "First Interview" badge. Her mentor gets no alert, because her score is above the
   threshold.
8. Later she applies to a "Backend Developer" job.
   - The recruiter sees her match score with "Redis" listed as a missing preferred skill, and her interview
     scores.

## M. Viva questions and answers

**1. What is HireSense AI?**
A web platform where students practise AI mock interviews and get scores, feedback and a readiness score, while
recruiters, mentors and admins have their own dashboards. It is an AI-assisted first-level assessment, not a
replacement for recruiters.

**2. Which technologies did you use?**
- Frontend: React 18 with Vite and Tailwind.
- Backend: FastAPI (Python).
- Database: MongoDB.
- AI: Google Gemini or local Ollama `qwen3:4b` (the fallback), Sentence Transformers, a scikit-learn classifier, and Whisper and
  Kokoro for voice.

**3. Why FastAPI?**
- It is fast and easy to write.
- It validates requests automatically with Pydantic.
- Dependency injection (`Depends`) handles the database session and the login check.
- It generates interactive API docs at `/docs`.
- Python also has the best AI/ML libraries.

**4. Why MongoDB?**
Interview reports, resume analyses and scores are nested JSON-like data, which fits documents naturally. We kept
an SQLAlchemy-style API through our own data layer so the code stays readable.

**5. How does login work?**
1. `POST /api/auth/login` checks the password against the stored Argon2 hash.
2. It creates a JWT signed with the secret key, holding the user id and role.
3. It stores the JWT in an httpOnly cookie, so JavaScript cannot read it.
4. Every request sends the cookie, and `get_current_user()` verifies it.

**6. How are passwords stored?**
Only as Argon2 hashes with a random salt (`password_and_token_security.hash_password`). The plain password is
never stored.

**7. How do you stop brute-force login attempts?**
`rate_limiter.py` counts failed logins per email. After too many in the time window, login returns HTTP 429 for
15 minutes.

**8. How do you make sure a student cannot see another student's interview?**
- `require_student` checks the role.
- `_get_session()` checks `session.student_id == user.id` and otherwise returns 404.
- Recruiters and mentors go through `student_record_access.py`, which checks for an application or a mentor
  assignment.

**9. How is the resume analysed?**
1. The text is extracted with pypdf or python-docx.
2. The AI returns the skills, education, projects and experience as JSON.
3. `validate_resume_extraction()` removes anything not found in the resume text.
4. `resume_completeness()` calculates a 0-100 score from fixed rules.

**10. How do you prevent the AI from inventing skills?**
Each extracted skill or item is checked against the resume text (`skill_name_normalizer.TextIndex`, with
aliases such as JS = JavaScript). If there is no evidence, it is dropped.

**11. How are interview questions generated?**
`next_interview_question()` builds a prompt from:
- the job role, category, position and difficulty
- the resume facts
- the last answers and the topics already covered
- the interviewer's style

The model returns JSON in the `NextQuestion` schema.

**12. What if the AI writes the same question twice?**
`interview_intelligence_rules.is_duplicate()` compares the new question with the earlier ones by words, topic
and embedding similarity, and `validate_question()` checks its form. A rejected question is regenerated up to 3
times (2 in voice mode), and then a fallback is used.

**13. What happens if the AI model is not running?**
- The interview uses the admin **question bank**, and this is shown to the student.
- Answers are marked `unavailable`, not given fake scores. The student can press *Retry evaluation* later.
- Resume analysis shows an error and offers a retry.

**14. How is an answer scored?**
1. The AI gives five 0-10 scores: relevance, correctness, completeness, clarity and communication.
2. `apply_answer_rules()` applies caps.
3. `weighted_score()` combines them with the rubric weights (relevance 0.25, correctness 0.30, clarity 0.25,
   communication 0.20).
4. Completeness is blended in at 20%, and the result is scaled to 0-100.

**15. Give an example of a rule cap.**
- "I don't know" or an empty answer: every criterion is capped at 1.
- Under 8 words: capped at 3.
- An off-topic answer (meaning similarity below 0.20): relevance and completeness are capped at 2.
- Correctness can never be more than relevance + 3.

**16. Why not trust the AI score directly?**
Small models make mistakes, for example giving a well-written but wrong answer a high score. Rules make scoring
consistent and explainable. Our calibration script (`eval/calibrate_scoring.py`) measured this.

**17. How is the interview adaptive?**
- Difficulty: a score of 75 or more moves up a level (easy, medium, hard), below 45 moves down
  (`next_difficulty()`).
- Content: `answer_signals()` spots gaps such as no personal role, unmeasured claims or uncertainty, and the next
  prompt asks for a matching follow-up.

**18. How is the overall interview score calculated?**
It is the average of the 0-100 scores of the answered questions, rounded to one decimal place
(`_finalize_scores_and_report()`). A band label such as "Strong (75-89)" is shown next to it.

**19. What does the interview report contain?**
- From the AI: a summary, strengths, weaknesses, improvement suggestions, recommended practice and closing
  remarks.
- Calculated by `report_metrics()`: technical and communication averages, and response indicators such as
  words, timing, pace and filler words.

**20. Why is feedback generated in the background?**
Detailed feedback takes about 900 tokens and is slow. The fast score is enough to choose the next question, so
the feedback is written afterwards by `feedback_job()` at background priority, which pauses whenever the student
is waiting.

**21. How does the voice interview work?**
1. The browser records the answer, and Whisper (`speech_to_text.py`) transcribes it.
2. The text goes to `POST .../turn`, which scores it and streams the next question.
3. Each finished sentence is turned into speech by Kokoro (`text_to_speech.py`).
4. The audio is played by `speechPlayer.js`, and the 3D avatar's lips follow the mouth-shape (viseme) timeline.

**22. What are Server-Sent Events and where do you use them?**
A one-way stream from the server to the browser over HTTP. We use it for:
- the live interview turn (score, then sentences, then audio)
- streamed English replies
- live notifications

**23. What is the role of Sentence Transformers?**
It turns text into vectors so we can measure meaning similarity. We use it for:
- the job-match semantic part
- detecting off-topic answers
- spotting duplicate questions

**24. What machine-learning model did you train yourselves?**
A scikit-learn classifier, trained with `ml/train_question_classifier.py` on a labelled CSV. It predicts a
question's type and difficulty. The prediction is stored with each AI question as a cross-check and does not
change the flow.

**25. How is the job match score calculated?**
`compute_match()` takes a weighted average of:
- required-skill coverage (0.50)
- preferred-skill coverage (0.15)
- semantic similarity (0.20)
- experience (0.15)

If required skills are missing, the score is capped. The AI can explain the match but cannot change the score.

**26. What is the placement-readiness score?**
A transparent weighted score: interviews 30%, assessments 20%, English 20%, resume 20%, profile 10%. Missing
parts count as 0 (`readiness_score()`).

**27. How is skill-gap analysis done?**
- Missing concepts for each answer (from the AI feedback).
- Separate technical and communication averages.
- Weak-area trends with suggested remedies (`remedies()`).
- Missing job skills from the matcher.
- Recurring English mistakes.

**28. How are coding questions evaluated?**
MCQs are graded on the server. For coding, the AI reviews the code against the test cases; the code is not
executed on the server. If the AI is unavailable, the result stays "pending" and no score is invented.

**29. What can recruiters do?**
- Post jobs.
- See applicants sorted by match score.
- Compare 2 to 4 candidates.
- Open a printable candidate report.
- Change the application status, which notifies the student.
- Create tests.
- Search students who share their profile.

**30. What can mentors do?**
- See their assigned students, trends and alerts.
- Give feedback and private notes.
- Create improvement plans with goals that update automatically from student activity.
- Schedule mentoring sessions.

**31. What can the admin do?**
- Manage users and approve recruiters.
- Assign mentors.
- Edit categories, the question bank, scoring rubrics, badges and rewards.
- Create placement drives and announcements.
- View analytics, placement reports, flagged activity, AI usage, errors and audit logs.
- Download a backup.

**32. Is the interview proctored?**
Only if the student agrees. The camera is analysed in the browser with MediaPipe, and only short event records
(for example "face not visible for 4 s") are sent. They are shown to a human reviewer as neutral signals and
never change scores.

**33. How do you protect against prompt injection?**
Untrusted text (resume, answer, messages) is wrapped in tags by `fence()`, and the system prompt tells the model
to treat it as data. The output must also match a strict JSON schema.

**34. How do you keep student data private?**
- AI can run fully locally (Ollama).
- When Gemini is used, students must give explicit consent first.
- AI logs store no content.
- Passwords are hashed.
- Recruiters only see the details of students who applied to their jobs.
- Students can delete their own account.

**35. How is the frontend connected to the backend?**
All calls go through `apiClient.js` to `/api/...`. In development, Vite proxies `/api` to the FastAPI server on
port 8000, so the cookie is same-origin.

**36. How are the four roles separated in the UI?**
`App.jsx` defines the routes per role, and `RequireRole` redirects anyone else. The backend checks the role
again on every endpoint, so the UI guard is only for convenience.

**37. How did you test the project?**
- **pytest:** 369 automated backend tests with the AI mocked, run in GitHub Actions.
- **Vitest:** 141 frontend unit tests.
- **Playwright:** real-browser end-to-end scripts.
- **Integration tests:** run with the real local models.
- **Benchmark scripts:** measure latency.

**38. What are the limitations?**
- AI scores are estimates with a few points of noise, which is why score bands are shown.
- A small local model is slower than cloud models.
- Coding answers are reviewed by the AI, not executed.
- There is no separate "confidence" score in interviews.
- Live notifications work within a single server process.
- Some recruiter tools (bulk screening, CSV export, messages) exist only as API endpoints.

**39. How can the project be extended?**
- Execute code in a sandbox.
- Add UI screens for the API-only recruiter tools.
- Support more languages.
- Use a larger model on a GPU server.
- Calibrate scores with more labelled answers.

**40. Why did you rename files and add comment indexes?**
Generic names such as `ai.py`, `common.py` or `Dashboard.jsx` (there were four) made the code hard to follow.
Every file now says what it does, the services are grouped by area, and each file starts with an explanation of
its purpose, functions, inputs, outputs and connected files. `FILE_RENAMING_MAPPING.md` lists every change.
