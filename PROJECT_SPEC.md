# HireSense

**Full title:** AI-Powered Intelligent Interview and Placement Assessment System
**Project name:** HireSense

---

### 1. Project Overview

Develop a complete, functional, full-stack web application called **AI-Powered Intelligent Interview and Placement Assessment System** (HireSense).

The system should help students prepare for placements through AI-powered interviews, resume analysis, skill assessments, English communication practice, performance tracking, and personalized improvement suggestions.

The application must contain four separate portals:

1. Student Portal
2. Recruiter Portal
3. Admin Portal
4. Mentor Portal

Each portal must have its own dashboard, permissions, and features. All four portals must be connected to the same database and work together seamlessly.

### 2. Student Portal

Create a student dashboard with the following features:

**A. Student Registration and Login**

* Allow students to register and log in securely.
* Create and manage student profiles.
* Store educational details, skills, projects, experience, and career interests.

**B. AI Resume Analysis**

* Allow students to upload resumes in PDF or DOCX format.
* Use AI to extract education, skills, projects, experience, and certifications.
* Identify strengths, missing skills, and areas for improvement.
* Generate personalized interview questions based on the uploaded resume.

**C. AI Mock Interview**

* Conduct AI-powered mock interviews based on the student's resume, skills, and selected job role.
* Ask technical, HR, behavioral, and communication-related questions.
* Support text-based interviews and voice-based interviews.
* For voice interviews, convert speech to text and analyze the student's answers.
* Generate relevant follow-up questions based on previous answers.
* Evaluate answers for relevance, correctness, clarity, and communication quality.
* Provide a final score, detailed feedback, strengths, weaknesses, and improvement suggestions.

**D. English Communication Practice**

* Allow students to practise spoken English through AI conversations.
* Evaluate grammar, vocabulary, fluency, pronunciation where supported, and sentence formation.
* Track English-speaking practice time.
* Display progress reports and personalized suggestions.

**E. Assessment and Performance Tracking**

* Display interview history, scores, assessment results, and skill development.
* Show progress through charts and reports.
* Identify weak subjects and recommend suitable practice activities.

**F. Rewards and Achievement System**

* Award points and badges when students complete mock interviews, practise English, achieve milestones, or improve their scores.
* Track total points, earned badges, completed challenges, and practice streaks.
* Provide achievements such as:
  * First Interview
  * Communication Champion
  * Consistent Learner
  * Technical Expert
  * Interview Master
* Award practice-time achievements based on verified active practice time.
* Prevent rewards from being earned through repeated or invalid activities.
* Display rewards prominently on the student dashboard.

**G. Placement Opportunities**

* Display job openings published by recruiters.
* Show eligibility criteria and required skills.
* Allow students to apply for suitable jobs.
* Track application status, interview invitations, and selection results.

### 3. Recruiter Portal

Create a separate dashboard for recruiters and hiring companies.

**A. Recruiter Registration and Login**

* Allow recruiters to register and manage company profiles.
* Provide appropriate access permissions.

**B. Job Management**

* Create, edit, publish, and close job postings.
* Specify job title, description, required skills, eligibility, experience, and location.
* Manage applications received for each job.

**C. Candidate Management**

* View student profiles, resumes, skills, assessments, and interview reports.
* Search and filter candidates based on skills, qualifications, scores, and job eligibility.
* Shortlist, reject, and select candidates.
* Track each candidate's recruitment status.

**D. AI Candidate Assessment**

* Analyze how well a candidate's skills match a job description.
* Generate a job-specific assessment using predefined evaluation criteria.
* Display interview performance and relevant skill scores.
* Provide explainable candidate comparisons based on job requirements.
* Allow recruiters to review AI recommendations and make the final hiring decision.

**E. Recruitment Dashboard**

* Display job postings, applications, shortlisted candidates, interviews, and hiring statistics.
* Allow recruiters to update application statuses and communicate relevant updates to students.

### 4. Admin Portal

Create a powerful administration dashboard to manage the entire platform.

**A. User Management**

* View and manage students, recruiters, and mentors.
* Approve, suspend, or deactivate accounts when appropriate.
* Assign roles and permissions.
* Monitor user activity and account status.

**B. Platform Management**

* Manage job postings and placement activities.
* Monitor assessments, interviews, and system usage.
* Manage reward rules, badges, points, and achievement criteria.
* Configure platform settings.

**C. Analytics and Reports**

* Display total registered users, active students, recruiters, and mentors.
* Track mock interviews, assessments, placement applications, and selections.
* Generate performance and placement reports.
* Show charts for platform usage and student progress.

**D. AI and Assessment Management**

* Configure interview categories and assessment criteria.
* Manage question banks and evaluation rubrics.
* Monitor AI assessment quality and system errors.
* Review flagged or suspicious assessment activity.

**E. Security and Monitoring**

* Enforce role-based access control.
* Maintain audit logs for important administrative actions.
* Monitor account activity and application errors.
* Protect student information and prevent unauthorized access.

### 5. Mentor Portal

Create a dedicated mentor dashboard that allows mentors to guide assigned students.

**A. Mentor Login and Profile**

* Allow mentors to log in securely.
* Display their profile, assigned students, and mentoring responsibilities.

**B. Student Progress Monitoring**

* Display the list of students assigned to each mentor.
* View each student's resume analysis, mock interview scores, assessment results, English practice time, and progress history.
* Identify students who are struggling or showing limited improvement.
* Display individual and comparative progress charts.

**C. Personalized Guidance**

* Identify students' weak technical skills, communication problems, and interview difficulties.
* Allow mentors to recommend specific practice activities, learning resources, and improvement plans.
* Create goals and deadlines for assigned students.
* Track whether students complete their recommended activities.

**D. Feedback and Follow-Up**

* Allow mentors to provide written feedback and suggestions.
* Add notes about student progress.
* Schedule follow-up sessions.
* Monitor improvements after guidance is provided.

**E. Mentor Dashboard Analytics**

* Display the number of assigned students.
* Show students who are improving, struggling, or meeting their goals.
* Track completed mentoring sessions and pending follow-ups.

Mentors must only be able to access students assigned to them unless an administrator grants additional permissions.

### 6. AI Integration

Integrate real AI capabilities into the application rather than using hardcoded responses.

The AI system should support:

* Resume parsing and analysis.
* Resume-based interview question generation.
* Technical and HR mock interviews.
* Context-aware follow-up questions.
* Answer evaluation and personalized feedback.
* English communication practice.
* Skill-gap identification.
* Job-description and candidate skill matching.
* Personalized student improvement recommendations.

Use an appropriate AI API or model, configured through environment variables.

If an external AI service is unavailable, display a clear error message and provide a controlled fallback where appropriate. Do not pretend that simulated responses are genuine AI assessments.

Keep API keys on the backend, never expose them in frontend code, and implement appropriate error handling and usage limits.

### 7. Recommended Technology Stack

Use the following technology stack unless the existing project already uses a suitable alternative:

* **Frontend:** React.js with a responsive UI.
* **Styling:** Tailwind CSS or an equivalent modern styling framework.
* **Backend:** Python FastAPI.
* **Database:** PostgreSQL.
* **Authentication:** Secure session-based authentication or JWT with appropriate token handling.
* **AI Integration:** A suitable large language model API.
* **Resume Processing:** PDF and DOCX parsing libraries.
* **Charts:** Recharts or an equivalent charting library.
* **Voice Features:** Speech-to-text and text-to-speech services where required.

Keep the frontend, backend, database, and AI integration modular and maintainable.

### 8. Database Design

Create appropriate database tables and relationships for:

* Users and roles
* Student profiles
* Recruiter profiles
* Mentor profiles
* Mentor-student assignments
* Resumes and extracted skills
* Interview sessions and questions
* Interview answers and evaluations
* Assessments and assessment results
* English practice sessions
* Student progress records
* Rewards, points, badges, and achievements
* Jobs and job requirements
* Job applications and application statuses
* Mentor feedback and improvement plans
* Notifications
* Audit logs

Use appropriate primary keys, foreign keys, indexes, validation, and database constraints.

Store passwords securely using a modern password-hashing algorithm. Protect sensitive information and enforce authorization on the backend.

### 9. Dashboard UI and Design

Create a professional, modern, responsive interface suitable for a college placement platform.

Each portal must have:

* A dedicated dashboard.
* Sidebar navigation.
* Profile management.
* Summary cards.
* Tables and charts where appropriate.
* Notifications.
* Search and filtering where required.
* Loading states, empty states, and error messages.
* Responsive layouts for desktop, tablet, and mobile devices.

Use a consistent design system, clear typography, accessible controls, and intuitive navigation.

The student dashboard should emphasize learning progress, upcoming activities, interview performance, rewards, and job opportunities.

The recruiter dashboard should emphasize candidates, job postings, applications, and hiring progress.

The admin dashboard should emphasize platform management, analytics, users, and system monitoring.

The mentor dashboard should emphasize assigned students, individual progress, weaknesses, recommendations, and follow-ups.

### 10. Connections Between the Four Portals

All four portals must work together through shared database records and secure APIs.

Implement these workflows:

1. Students upload resumes and complete AI interviews.
2. Interview scores and feedback are stored and displayed in the student portal.
3. Assigned mentors can review student progress and recommend improvements.
4. Students can follow mentor recommendations and track their improvement.
5. Recruiters publish jobs and review eligible student applications.
6. Recruiters can view relevant student assessment results according to access permissions.
7. Students receive updates about applications and recruitment decisions.
8. Admins manage users, mentors, recruiters, jobs, assessment settings, and platform analytics.
9. Student achievements update automatically when verified reward conditions are satisfied.
10. Changes made by authorized users appear consistently across the relevant dashboards.

Use role-based permissions to prevent students, recruiters, mentors, and administrators from accessing unauthorized information.

### 11. Important Functional Requirements

* Every visible button, form, filter, and navigation link must work.
* Implement real CRUD operations wherever applicable.
* Connect the frontend to the backend and the backend to the database.
* Do not use hardcoded dashboard statistics or fake student records in production.
* Validate all forms and handle invalid input.
* Provide clear success and error messages.
* Add pagination or other suitable methods for large datasets.
* Protect APIs against unauthorized access.
* Use environment variables for secrets and configuration.
* Include database migrations and initial setup instructions.
* Add automated tests for important features and permissions.

### 12. Development Instructions

Before making changes, inspect the existing project files, technology stack, folder structure, database configuration, and implemented features.

If a project already exists, improve and extend it instead of unnecessarily rebuilding everything.

Follow these steps:

1. Inspect the existing code and identify completed, incomplete, and missing features.
2. Design the architecture and database relationships.
3. Implement authentication and role-based access control.
4. Develop the four dashboards and their core workflows.
5. Connect the database and implement backend APIs.
6. Integrate AI resume analysis, interviews, assessments, and recommendations.
7. Implement mentor guidance, recruiter hiring workflows, and student rewards.
8. Connect notifications and cross-portal updates.
9. Test the complete application and fix errors.
10. Provide setup instructions and verify that the project runs successfully.

Do not stop after creating the frontend or a basic dashboard. Continue until the frontend, backend, database, authentication, and core business workflows are connected and tested.

If a feature requires an external API key, explain how to configure it and test the feature. Never claim that a feature is complete without verifying its functionality.

### 13. Final Deliverables

Provide:

* Complete frontend source code.
* Complete backend source code.
* Database schema and migrations.
* Working authentication and role-based permissions.
* All four functional portals.
* AI integration and assessment workflows.
* Student reward and achievement system.
* Mentor progress monitoring and recommendation system.
* Recruiter job and candidate management system.
* Admin management and analytics.
* API documentation.
* Environment configuration example.
* Installation and execution instructions.
* Automated tests for critical features.
* A list of completed features and any remaining limitations.

**Final Objective:** Build a complete, secure, maintainable, and fully functional AI-Powered Intelligent Interview and Placement Assessment System in which students improve their placement readiness, recruiters identify suitable candidates, mentors guide student development, and administrators manage the entire platform.
