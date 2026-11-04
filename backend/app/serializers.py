"""Convert ORM objects to API dictionaries (single place to control what each role sees)."""
from .models import (
    Assessment, AssessmentResult, EnglishSession, ImprovementPlan, InterviewSession, Job,
    JobApplication, MentorSession, Notification, Resume, User,
)


def iso(dt):
    return dt.isoformat() if dt else None


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "status": u.status,
            "permissions": u.permissions or [], "preferences": u.preferences or {}, "created_at": iso(u.created_at),
            "last_login_at": iso(u.last_login_at), "last_active_at": iso(u.last_active_at),
            "ai_data_consent_at": iso(u.ai_data_consent_at)}


def student_profile_out(u: User) -> dict:
    p = u.student_profile
    data = user_out(u)
    data["profile"] = None if not p else {
        "phone": p.phone, "college": p.college, "degree": p.degree, "branch": p.branch,
        "graduation_year": p.graduation_year, "cgpa": p.cgpa, "skills": p.skills or [],
        "projects": p.projects or [], "experience": p.experience or [], "career_interests": p.career_interests,
        "target_role": p.target_role, "bio": p.bio, "linkedin_url": p.linkedin_url, "github_url": p.github_url,
        "share_with_recruiters": p.share_with_recruiters,
    }
    return data


def recruiter_profile_out(u: User) -> dict:
    p = u.recruiter_profile
    data = user_out(u)
    data["profile"] = None if not p else {
        "company_name": p.company_name, "company_website": p.company_website, "designation": p.designation,
        "company_description": p.company_description, "location": p.location, "phone": p.phone,
        "industry": p.industry, "company_verified": p.company_verified}
    return data


def mentor_profile_out(u: User) -> dict:
    p = u.mentor_profile
    data = user_out(u)
    data["profile"] = None if not p else {
        "department": p.department, "expertise": p.expertise or [], "bio": p.bio, "max_students": p.max_students}
    return data


def profile_out(u: User) -> dict:
    return {"student": student_profile_out, "recruiter": recruiter_profile_out,
            "mentor": mentor_profile_out}.get(u.role, user_out)(u)


def resume_out(r: Resume, include_text: bool = False) -> dict:
    d = {"id": r.id, "student_id": r.student_id, "filename": r.filename, "content_type": r.content_type,
         "is_current": r.is_current, "analysis_status": r.analysis_status, "analysis": r.analysis,
         "analysis_error": r.analysis_error, "created_at": iso(r.created_at), "analyzed_at": iso(r.analyzed_at),
         "skills": [{"name": s.name, "category": s.category} for s in r.skills]}
    if include_text:
        d["raw_text"] = r.raw_text
    return d


def interview_out(s: InterviewSession, detail: bool = False, own: bool = False) -> dict:
    """own=True only for the student's own requests: adds their monitoring consent settings. Recruiters and
    mentors never get monitoring data through this serializer (reviewers use routers/monitoring.py)."""
    d = {"id": s.id, "student_id": s.student_id, "job_role": s.job_role, "category": s.category, "mode": s.mode,
         "difficulty": s.difficulty, "subject": s.subject, "interviewer": s.interviewer or "aria",
         "response_mode": s.response_mode or "fast",
         "status": s.status, "planned_questions": s.planned_questions, "question_source": s.question_source,
         "created_at": iso(s.created_at), "completed_at": iso(s.completed_at), "overall_score": s.overall_score,
         "report_status": s.report_status, "flagged": s.flagged, "flag_reason": s.flag_reason,
         "answered": sum(1 for q in s.questions if q.answer)}
    if own:
        d["monitoring"] = s.monitoring
    if detail:
        d["report"] = s.report
        d["questions"] = [{
            "id": q.id, "position": q.position, "text": q.text, "question_type": q.question_type,
            "is_followup": q.is_followup, "difficulty": q.difficulty, "preface": q.preface,
            "source": (q.meta or {}).get("source"),
            "answer": None if not q.answer else {
                "text": q.answer.text, "input_mode": q.answer.input_mode,
                "response_seconds": q.answer.response_seconds, "evaluation_status": q.answer.evaluation_status,
                "scores": q.answer.scores, "score": q.answer.score, "feedback": q.answer.feedback,
                "sample_answer": q.answer.sample_answer, "details": q.answer.details},
        } for q in s.questions]
    return d


def english_out(s: EnglishSession, detail: bool = False) -> dict:
    d = {"id": s.id, "student_id": s.student_id, "topic": s.topic, "mode": s.mode,
         "style": s.style or "free_talk", "status": s.status,
         "created_at": iso(s.created_at), "ended_at": iso(s.ended_at), "active_seconds": s.active_seconds,
         "scores": s.scores, "overall_score": s.overall_score, "feedback": s.feedback,
         "evaluation_status": s.evaluation_status}
    if detail:
        d["messages"] = [{"id": m.id, "sender": m.sender, "content": m.content, "input_mode": m.input_mode,
                          "corrections": m.corrections, "meta": m.meta, "created_at": iso(m.created_at)}
                         for m in s.messages]
    return d


def assessment_out(a: Assessment, with_answers: bool = False) -> dict:
    qs = []
    for q in a.questions or []:
        kind = q.get("type") or "mcq"
        item = {"type": kind, "question": q["question"], "marks": q.get("marks", 1 if kind == "mcq" else 5)}
        if kind == "mcq":
            item["options"] = q["options"]
            if with_answers:
                item["answer_index"] = q["answer_index"]
                item["explanation"] = q.get("explanation", "")
        else:
            item.update(language=q.get("language", "python"), function_name=q.get("function_name", "solution"),
                        starter_code=q.get("starter_code", ""), test_cases=q.get("test_cases", []))
        qs.append(item)
    return {"id": a.id, "title": a.title, "description": a.description, "topic": a.topic,
            "category": a.category, "difficulty": a.difficulty, "total_marks": sum(q["marks"] for q in qs),
            "time_limit_minutes": a.time_limit_minutes, "pass_percent": a.pass_percent, "job_id": a.job_id,
            "active": a.active, "question_count": len(a.questions or []), "questions": qs,
            "has_coding": any(q["type"] == "coding" for q in qs),
            "created_by": a.created_by, "created_at": iso(a.created_at)}


def result_out(r: AssessmentResult) -> dict:
    return {"id": r.id, "assessment_id": r.assessment_id, "assessment_title": r.assessment.title if r.assessment else None,
            "topic": r.assessment.topic if r.assessment else None,
            "category": r.assessment.category if r.assessment else None, "student_id": r.student_id,
            "started_at": iso(r.started_at), "submitted_at": iso(r.submitted_at), "score": r.score,
            "correct_count": r.correct_count, "passed": r.passed, "flagged": r.flagged, "flag_reason": r.flag_reason,
            "marks_obtained": r.marks_obtained, "max_marks": r.max_marks, "evaluation_status": r.evaluation_status,
            "pass_percent": r.assessment.pass_percent if r.assessment else None}


def job_out(j: Job) -> dict:
    return {"id": j.id, "recruiter_id": j.recruiter_id, "title": j.title, "company_name": j.company_name,
            "description": j.description, "location": j.location, "job_type": j.job_type,
            "experience_years": j.experience_years, "salary": j.salary, "min_cgpa": j.min_cgpa,
            "eligible_branches": j.eligible_branches or [], "graduation_years": j.graduation_years or [],
            "status": j.status, "deadline": iso(j.deadline), "created_at": iso(j.created_at),
            "company_verified": bool(j.recruiter and j.recruiter.recruiter_profile and j.recruiter.recruiter_profile.company_verified),
            "industry": j.recruiter.recruiter_profile.industry if j.recruiter and j.recruiter.recruiter_profile else None,
            "updated_at": iso(j.updated_at), "published_at": iso(j.published_at),
            "required_skills": [r.skill for r in j.requirements if r.importance == "required"],
            "preferred_skills": [r.skill for r in j.requirements if r.importance == "preferred"]}


def application_out(a: JobApplication, include_student: bool = False) -> dict:
    d = {"id": a.id, "job_id": a.job_id, "student_id": a.student_id, "status": a.status,
         "cover_letter": a.cover_letter, "created_at": iso(a.created_at), "updated_at": iso(a.updated_at),
         "interview_at": iso(a.interview_at), "match": a.match,
         "job": {"id": a.job.id, "title": a.job.title, "company_name": a.job.company_name,
                 "location": a.job.location, "status": a.job.status} if a.job else None,
         "history": [{"from_status": h.from_status, "to_status": h.to_status, "note": h.note,
                      "created_at": iso(h.created_at)} for h in a.history]}
    if include_student and a.student:
        p = a.student.student_profile
        d["student"] = {"id": a.student.id, "full_name": a.student.full_name, "email": a.student.email,
                        "college": p.college if p else None, "branch": p.branch if p else None,
                        "cgpa": p.cgpa if p else None, "graduation_year": p.graduation_year if p else None,
                        "skills": (p.skills if p else []) or []}
        d["recruiter_notes"] = a.recruiter_notes
    return d


def plan_out(p: ImprovementPlan, progress: dict | None = None) -> dict:
    progress = progress or {}
    return {"id": p.id, "mentor_id": p.mentor_id, "mentor_name": p.mentor.full_name if p.mentor else None,
            "student_id": p.student_id, "title": p.title, "description": p.description, "status": p.status,
            "created_at": iso(p.created_at),
            "goals": [{"id": g.id, "title": g.title, "description": g.description, "goal_type": g.goal_type,
                       "resource_url": g.resource_url, "target_count": g.target_count,
                       "target_score": g.target_score, "deadline": iso(g.deadline), "status": g.status,
                       "completed_at": iso(g.completed_at), "created_at": iso(g.created_at),
                       "progress": progress.get(g.id)} for g in p.goals]}


def mentor_session_out(s: MentorSession) -> dict:
    return {"id": s.id, "mentor_id": s.mentor_id, "mentor_name": s.mentor.full_name if s.mentor else None,
            "student_id": s.student_id, "student_name": s.student.full_name if s.student else None,
            "scheduled_at": iso(s.scheduled_at), "agenda": s.agenda, "meeting_link": s.meeting_link,
            "status": s.status, "outcome_notes": s.outcome_notes, "created_at": iso(s.created_at)}


def drive_out(d) -> dict:
    return {"id": d.id, "title": d.title, "company_name": d.company_name, "description": d.description,
            "drive_date": iso(d.drive_date), "location": d.location, "min_cgpa": d.min_cgpa,
            "eligible_branches": d.eligible_branches or [], "status": d.status,
            "registration_count": len(d.registrations), "created_at": iso(d.created_at)}


def notification_out(n: Notification) -> dict:
    return {"id": n.id, "title": n.title, "message": n.message, "kind": n.kind, "link": n.link,
            "read": n.read, "created_at": iso(n.created_at)}
