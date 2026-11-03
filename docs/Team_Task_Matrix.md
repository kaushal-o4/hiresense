# Team Task Matrix — HireSense

Roles below are proposed, not verified historical contributions (Git shows one contributor).

## Matrix by member

| Member | Module Ownership | Tasks Completed (Evidence) | Tasks Remaining | Relevant Files | Dependencies | Testing Criteria | Deliverables |
|---|---|---|---|---|---|---|---|
| Member 1 | AI engine, architecture, integration | FastAPI wiring, settings, AI service, LLM client, matching, adaptive logic, monitoring/perf (`main.py`, `config.py`, `services/ai.py`, `matching.py`) | Real-model verification, integration regression tests, demo | backend/app/main.py, config.py, services/ai.py, local_llm.py, matching.py, interview_engine.py, interviews.py, monitoring.py; frontend/src/pages/student/VoiceInterview.jsx | All modules | Integration tests, latency benchmarks | Architecture notes, AI config, final demo |
| Member 2 | Student portal & frontend | Student pages (dashboard, resume, interviews, English, assessments, progress, rewards, jobs, applications) | Responsive polish, accessibility, automated UI tests | frontend/src/pages/student/*, components/*, voice/* | Backend APIs (Member 3) | Vitest state machines, manual UX | Student UI package, UX checklist |
| Member 3 | Backend & database | Models, migrations, auth, routers, serializers, seed | DB indexing/performance, PostgreSQL migration tests, validation | backend/app/models.py, schemas.py, serializers.py, seed.py, database.py, routers/auth.py, common.py, students.py, alembic/* | AI (Member 1), portals (Members 2/4/5) | pytest auth/permissions/workflows | DB ER diagram, API contract docs |
| Member 4 | Recruiter & admin portals | Recruiter dashboard/jobs/candidates, admin users/settings/monitoring/reports | Report export polish, permission edge cases, UI polish | backend/app/routers/jobs.py, admin.py; frontend/src/pages/recruiter/*, admin/* | Backend (Member 3), Data (Member 1) | Recruiter isolation tests | Recruiter/admin UI, admin reports |
| Member 5 | Mentor portal, testing, learning | Mentor pages, English routes/companion, test suite | More integration tests, user guides, bug triage | backend/app/routers/mentors.py, english.py, services/english_companion.py; frontend/src/pages/mentor/*; backend/tests/* | All modules | Full pytest, regression list | Test report, user guide |

## Module responsibility matrix

| Major Module | Responsible Member |
|---|---|
| System architecture & AI | Member 1 |
| Student frontend | Member 2 |
| Backend & database | Member 3 |
| Recruiter portal | Member 4 |
| Admin portal | Member 4 |
| Mentor portal | Member 5 |
| Testing & QA | Member 5 |
| English learning | Member 5 / Member 1 |
| Job matching | Member 1 / Member 3 |
| Voice/avatar | Member 1 / Member 2 |
