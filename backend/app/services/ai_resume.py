"""Resume analysis: extraction schema, evidence checks against the resume text, completeness score."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator
from ..odm import Session

from ..config import get_settings
from .common import get_setting
from .skills import TextIndex

from .ai_base import AIUnavailable, _clean_list, _structured_call, fence


# =========================================================================== resume

SkillCategory = Literal["programming_language", "framework", "tool", "database", "cloud", "domain", "other"]


class ResumeEducation(BaseModel):
    institution: str
    degree: str
    field: str
    year: str
    score: str


class ResumeProject(BaseModel):
    name: str
    description: str
    technologies: list[str]


class ResumeExperience(BaseModel):
    organization: str
    role: str
    duration: str
    summary: str


class ResumeSkillItem(BaseModel):
    name: str
    category: SkillCategory

    @field_validator("category", mode="before")
    @classmethod
    def _known_category(cls, v):
        # Hosted models sometimes invent a category ("language", "devops"); one odd label must not discard the
        # whole analysis (it is display-only), so map it instead of failing validation.
        v = str(v or "").strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {"language": "programming_language", "languages": "programming_language", "library": "framework",
                   "libraries": "framework", "frameworks": "framework", "tools": "tool", "devops": "tool",
                   "databases": "database", "db": "database", "cloud_platform": "cloud"}
        v = aliases.get(v, v)
        return v if v in SkillCategory.__args__ else "other"


class ResumeExtraction(BaseModel):
    full_name: str
    candidate_summary: str
    education: list[ResumeEducation]
    technical_skills: list[ResumeSkillItem]
    soft_skills: list[str]
    projects: list[ResumeProject]
    work_experience: list[ResumeExperience]
    internships: list[ResumeExperience]
    certifications: list[str]
    strengths: list[str]
    missing_information: list[str]
    missing_skills: list[str]
    improvement_areas: list[str]
    recommended_topics: list[str]
    suggested_interview_questions: list[str]


# Deterministic resume-completeness score: points per section, capped. Documented in README.
RESUME_SCORE_RULES = [
    ("Name present", 5), ("Education", 15), ("Technical skills (2.5 each)", 25),
    ("Projects (8 each, 4 if no real description)", 25), ("Experience / internships (10 each)", 20),
    ("Certifications (5 each)", 10),
]


def resume_completeness(a: dict) -> tuple[int, list[dict]]:
    tech = [s for s in a["skills"] if s["category"] != "soft_skill"]
    project_pts = sum(8 if len((p.get("description") or "").split()) >= 8 else 4 for p in a["projects"])
    parts = [
        ("Name present", 5 if a.get("full_name") else 0, 5),
        ("Education", 15 if a["education"] else 0, 15),
        ("Technical skills", min(25, round(2.5 * len(tech))), 25),
        ("Projects", min(25, project_pts), 25),
        ("Experience / internships", min(20, 10 * (len(a["experience"]) + len(a["internships"]))), 20),
        ("Certifications", min(10, 5 * len(a["certifications"])), 10),
    ]
    return sum(p[1] for p in parts), [{"section": n, "points": p, "max": m} for n, p, m in parts]


# Soft skills are often shown rather than named ("Led a team of 4"). A soft skill is kept only if its name, or
# one of these evidence word-stems, appears in the resume.
SOFT_SKILL_EVIDENCE = {
    "leadership": ("led", "lead", "captain", "president", "head", "coordinator", "mentored"),
    "teamwork": ("team", "collaborat", "together"),
    "communication": ("present", "communicat", "speaker", "speech", "anchor", "debate", "wrote", "writing"),
    "problem solving": ("solved", "hackathon", "competitive programming", "leetcode", "codechef", "optimi"),
    "time management": ("deadline", "schedul", "on time"),
    "public speaking": ("speaker", "speech", "anchor", "debate", "talk", "present"),
    "organisation": ("organis", "organiz", "coordinat", "event"),
    "mentoring": ("mentor", "taught", "tutor"),
}


def _soft_skill_evidence(skill: str, idx: TextIndex) -> bool:
    key = " ".join(skill.lower().replace("organization", "organisation").split())
    stems = SOFT_SKILL_EVIDENCE.get(key, ())
    return any(stem in idx.joined if " " in stem else any(t.startswith(stem) for t in idx.set) for stem in stems)


def validate_resume_extraction(ext: ResumeExtraction, resume_text: str) -> dict:
    """Turn raw model output into the stored analysis, dropping anything not supported by the resume text."""
    idx = TextIndex(resume_text)
    removed: list[str] = []

    def keep(label: str, ok: bool) -> bool:
        if not ok:
            removed.append(label)
        return ok

    def short(name: str, max_words: int) -> bool:  # a skill is a name, not a sentence copied from the resume
        return keep(f"not a skill name: {name[:60]}", len(name.split()) <= max_words and len(name) <= 50)

    skills, seen = [], set()
    for s in ext.technical_skills:
        name = " ".join(s.name.split())[:100]
        if name and name.lower() not in seen and short(name, 5) and keep(f"skill: {name}", idx.has_skill(name)):
            seen.add(name.lower())
            skills.append({"name": name, "category": s.category})
    soft = [s for s in _clean_list(ext.soft_skills, 15) if short(s, 4)
            and keep(f"soft skill: {s}", idx.grounded(s, 0.5) or _soft_skill_evidence(s, idx))]
    for s in soft:
        if s.lower() not in seen:
            seen.add(s.lower())
            skills.append({"name": s[:100], "category": "soft_skill"})

    education = [e.model_dump() for e in ext.education
                 if keep(f"education: {e.institution or e.degree}",
                         idx.grounded(e.institution, 0.5) or idx.grounded(e.degree, 0.5))]
    projects = []
    for p in ext.projects:
        if keep(f"project: {p.name}", idx.grounded(p.name, 0.5) or idx.grounded(p.description, 0.7)):
            d = p.model_dump()
            d["technologies"] = [t for t in _clean_list(p.technologies, 15) if idx.has_skill(t)]
            projects.append(d)

    def jobs(items, label):
        return [e.model_dump() for e in items
                if keep(f"{label}: {e.organization}", idx.grounded(e.organization, 0.5) and bool(e.organization.strip()))]

    internships = jobs(ext.internships, "internship")
    intern_orgs = {e["organization"].strip().lower() for e in internships}
    # Small models sometimes list the same internship under work experience too - keep it once.
    experience = [e for e in jobs(ext.work_experience, "experience")
                  if e["organization"].strip().lower() not in intern_orgs]
    certs = [c for c in _clean_list(ext.certifications) if keep(f"certification: {c}", idx.grounded(c, 0.6))]
    name = " ".join(ext.full_name.split())
    full_name = name if name and name.lower() not in ("unknown", "n/a") and idx.has_phrase(name) else None

    a = {
        "full_name": full_name,
        "candidate_summary": ext.candidate_summary.strip()[:1200],
        "education": education, "skills": skills, "soft_skills": soft, "projects": projects,
        "experience": experience, "internships": internships, "certifications": certs,
        "strengths": _clean_list(ext.strengths, 8),
        "missing_information": _clean_list(ext.missing_information, 10),
        "missing_skills": _clean_list(ext.missing_skills, 12),
        "improvement_areas": _clean_list(ext.improvement_areas, 10),
        "recommended_topics": _clean_list(ext.recommended_topics, 12),
        "suggested_interview_questions": _clean_list(ext.suggested_interview_questions, 12),
    }
    for section, empty in (("education", "No education details found"), ("skills", "No technical skills found"),
                           ("projects", "No projects found")):
        if not a[section] and empty not in a["missing_information"]:
            a["missing_information"].append(empty)
    a["resume_score"], a["score_breakdown"] = resume_completeness(a)
    a["validation"] = {"removed_unsupported": removed[:30],
                       "note": "Items the model returned that could not be found in the resume text were removed."}
    return a


def analyze_resume(db: Session, user_id: int, resume_text: str, target_role: str | None) -> dict:
    """AI resume analysis: extract skills, education, projects, experience and certifications that are
    actually in the resume text, then validate them against the text (removing invented items) and compute the
    completeness score. Raises AIUnavailable if the text is too short or the model is unavailable.
    """
    settings = get_settings()
    text = (resume_text or "").strip()
    if len(text.split()) < 8:
        raise AIUnavailable("The resume has too little readable text to analyse. If it is a scanned image, "
                            "upload a text-based PDF or DOCX instead.", 422)
    truncated = len(text) > settings.max_resume_chars
    text = text[:settings.max_resume_chars]
    n_questions = int(get_setting(db, "resume_question_count") or 8)
    system = ("You are a careful resume parser and placement-cell career coach for college students. Extract "
              "ONLY information that is written in the resume. If something is not present, use an empty string "
              "or an empty list - never guess, never invent skills, employers, dates, grades or certifications.")
    prompt = (
        f"Target role: {target_role or 'not specified - suggest for the most suitable entry-level role'}\n\n"
        f"{fence('resume', text)}\n\n"
        "Fill every field. Be brief: each list item is a short phrase or ONE short sentence.\n"
        "- full_name: the candidate's name exactly as written, or \"\".\n"
        "- candidate_summary: 2 factual sentences about the candidate.\n"
        "- education: up to 4 degrees/schools with institution, degree, field, year, score (\"\" if absent).\n"
        "- technical_skills: up to 25 technologies, languages, tools and domains explicitly named (short names "
        "such as 'React', never sentences), with a category.\n"
        "- soft_skills: up to 5, only those the resume states or clearly demonstrates (e.g. 'led a team of 4').\n"
        "- projects: up to 5; name, a description of at most 30 words, technologies used.\n"
        "- work_experience: paid jobs (not internships). internships: internships only. summary at most 25 words.\n"
        "- certifications: exactly as written.\n"
        "- strengths: 3-5 concrete strengths supported by the resume.\n"
        "- missing_information: up to 6 resume sections or details that are missing or unclear (e.g. no dates, "
        "no measurable results, no contact links).\n"
        "- missing_skills: up to 6 skills commonly expected for the target role that do not appear in the resume.\n"
        "- improvement_areas: up to 6 specific, actionable resume improvements.\n"
        "- recommended_topics: up to 8 technical topics to revise for interviews, based on the resume and role.\n"
        f"- suggested_interview_questions: {n_questions} interview questions about this candidate's actual "
        "projects, skills and experience, one sentence each."
    )
    ext = _structured_call(db, user_id, "resume_analysis", system, prompt, ResumeExtraction, max_tokens=2500)
    data = validate_resume_extraction(ext, text)
    data["analysis_method"] = "local_llm"
    data["model"] = settings.ollama_model
    if truncated:
        data["validation"]["truncated"] = f"Only the first {settings.max_resume_chars} characters were analysed."
    return data
