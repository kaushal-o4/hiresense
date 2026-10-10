"""Semantic job matching: explicit skill checks + sentence-embedding similarity, combined transparently.

Score (0-100) = weighted average of the parts that apply to the job, using the MATCH_WEIGHT_* settings:

  required   coverage of required skills   (matched = 1, partial = 0.5, missing = 0)
  preferred  coverage of preferred skills  (same rule)
  semantic   cosine similarity between the job text and the candidate profile text, rescaled from
             [SEM_LOW, SEM_HIGH] to [0, 1]  (needs the embedding model)
  experience 1 if the job needs 0 years; otherwise 0.5 if the candidate lists any job/internship, else 0

Then a gap cap is applied: score <= 40 + 60 x required coverage. A candidate missing required skills can
never get a high score from similarity alone. Eligibility rules (CGPA, branch, year) are reported separately.

A job skill counts as:
  matched  - the candidate lists it (after alias normalisation, e.g. "JS" = "JavaScript"), or it is named in
             their project/experience descriptions
  partial  - not listed, but a listed skill is semantically close (cosine >= PARTIAL_SIM, e.g. MySQL ~ PostgreSQL)
  missing  - otherwise
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import get_settings
from . import embeddings
from .skills import TextIndex, normalize_skill

# Thresholds calibrated on all-MiniLM-L6-v2 (2026-10-10, see README "Job matching"):
#   skill pairs:  PostgreSQL~MySQL 0.55, PostgreSQL~SQL 0.51, Python~Django 0.50, ML~Deep Learning 0.69,
#                 but Python~Java 0.45, Java~JavaScript 0.40, Git~Photoshop 0.36 -> partial threshold 0.50
#   profile vs job: strong candidate 0.83, related 0.23, unrelated 0.05 -> rescale 0.15..0.65 to 0..1
SEM_LOW, SEM_HIGH = 0.15, 0.65
PARTIAL_SIM = 0.50
PROJECT_SIM = 0.30


class MatchInputError(ValueError):
    pass


def candidate_profile(db: Session, student) -> dict:
    """Collect the candidate's job-relevant evidence from their profile and current resume analysis."""
    from .insights import current_resume
    p = student.student_profile
    resume = current_resume(db, student.id)
    a = (resume.analysis or {}) if resume and resume.analysis_status == "completed" else {}
    skills = list((p.skills if p else []) or [])
    skills += [s["name"] for s in a.get("skills", []) if s.get("category") != "soft_skill" and s.get("name")]
    seen, uniq = set(), []
    for s in skills:
        if normalize_skill(s) not in seen:
            seen.add(normalize_skill(s))
            uniq.append(s)

    def merge(a_items, b_items, key):
        out, keys = [], set()
        for x in list(a_items or []) + list(b_items or []):
            k = (x.get(key) or "").strip().lower()
            if k and k not in keys:
                keys.add(k)
                out.append(x)
        return out

    edu = [f"{p.degree or ''} {p.branch or ''} {p.college or ''}".strip()] if p else []
    edu += [f"{e.get('degree', '')} {e.get('field', '')} {e.get('institution', '')}".strip()
            for e in a.get("education", [])]
    return {
        "target_role": (p.target_role if p else None) or "",
        "skills": uniq,
        "projects": merge(p.projects if p else [], a.get("projects"), "name"),
        "experience": merge(p.experience if p else [], a.get("experience"), "organization"),
        "internships": list(a.get("internships") or []),
        "certifications": list(a.get("certifications") or []),
        "education": [e for e in edu if e],
    }


def job_profile(job) -> dict:
    return {"title": job.title, "description": job.description or "", "experience_years": job.experience_years or 0,
            "required_skills": [r.skill for r in job.requirements if r.importance == "required"],
            "preferred_skills": [r.skill for r in job.requirements if r.importance == "preferred"]}


def _project_text(p: dict) -> str:
    return f"{p.get('name', '')}. {p.get('description', '')} {' '.join(p.get('technologies') or [])}"


def _work_text(e: dict) -> str:
    return f"{e.get('role', '')} at {e.get('organization', '')}. {e.get('summary', '')}"


def compute_match(job: dict, cand: dict, *, eligibility_issues: list[str] | None = None,
                  embed_fn=None) -> dict:
    """Pure function: job + candidate dicts -> match result. `embed_fn(list[str]) -> unit vectors`."""
    s = get_settings()
    raw_embed = embed_fn or embeddings.embed

    def embed_fn(texts):
        return embeddings.validate(raw_embed(texts), len(texts))

    required = [x for x in job.get("required_skills") or [] if x and x.strip()]
    preferred = [x for x in job.get("preferred_skills") or [] if x and x.strip()]
    job_text = " ".join(filter(None, [job.get("title"), (job.get("description") or "")[:3000],
                                      "Skills: " + ", ".join(required + preferred) if required or preferred else ""]))
    if not (job.get("description") or "").strip() and not required and not preferred:
        raise MatchInputError("The job has no description or skills to match against.")

    cand_skills = [x for x in cand.get("skills") or [] if x and x.strip()]
    work = list(cand.get("experience") or []) + list(cand.get("internships") or [])
    projects = list(cand.get("projects") or [])
    evidence = TextIndex(" ".join([_project_text(p) for p in projects] + [_work_text(e) for e in work] +
                                  list(cand.get("certifications") or [])))
    have = {normalize_skill(x): x for x in cand_skills}
    profile_empty = not cand_skills and not projects and not work

    # ---------------- embeddings (optional)
    semantic_ok, sem_error = True, None
    try:
        if profile_empty:
            raise embeddings.EmbeddingUnavailable("empty profile")
        cand_text = " ".join(filter(None, [cand.get("target_role"), "Skills: " + ", ".join(cand_skills),
                                           *[_project_text(p) for p in projects], *[_work_text(e) for e in work],
                                           *(cand.get("education") or [])]))
        doc_vecs = embed_fn([job_text, cand_text])
        skill_vecs = embed_fn(cand_skills) if cand_skills else None
        proj_vecs = embed_fn([_project_text(p) for p in projects]) if projects else None
    except embeddings.EmbeddingUnavailable as exc:
        semantic_ok, sem_error = False, (None if profile_empty else exc.message)

    def classify(skill: str) -> dict:
        n = normalize_skill(skill)
        if n in have:
            return {"skill": skill, "status": "matched", "via": "listed skill"}
        if evidence.has_skill(skill):
            return {"skill": skill, "status": "matched", "via": "mentioned in projects/experience"}
        if semantic_ok and skill_vecs is not None and len(skill_vecs):
            try:
                v = embed_fn([skill])[0]
            except embeddings.EmbeddingUnavailable:
                return {"skill": skill, "status": "missing"}
            sims = skill_vecs @ v
            best = int(sims.argmax())
            if float(sims[best]) >= PARTIAL_SIM:
                return {"skill": skill, "status": "partial", "closest": cand_skills[best],
                        "similarity": round(float(sims[best]), 2)}
        return {"skill": skill, "status": "missing"}

    req_rows, pref_rows = [classify(x) for x in required], [classify(x) for x in preferred]

    def coverage(rows):
        return sum(1.0 if r["status"] == "matched" else 0.5 if r["status"] == "partial" else 0.0
                   for r in rows) / len(rows) if rows else None

    req_cov, pref_cov = coverage(req_rows), coverage(pref_rows)
    parts: list[tuple[str, float, float, str]] = []  # (name, value 0-1, weight, reason)
    if req_cov is not None:
        n_ok = sum(r["status"] == "matched" for r in req_rows)
        n_part = sum(r["status"] == "partial" for r in req_rows)
        parts.append(("Required skills", req_cov, s.match_weight_required,
                      f"{n_ok} of {len(req_rows)} required skills matched" + (f", {n_part} partially" if n_part else "")))
    if pref_cov is not None:
        parts.append(("Preferred skills", pref_cov, s.match_weight_preferred,
                      f"{sum(r['status'] == 'matched' for r in pref_rows)} of {len(pref_rows)} preferred skills matched"))
    semantic_cos = None
    if semantic_ok:
        semantic_cos = float(doc_vecs[0] @ doc_vecs[1])
        val = min(1.0, max(0.0, (semantic_cos - SEM_LOW) / (SEM_HIGH - SEM_LOW)))
        parts.append(("Profile relevance (semantic)", val, s.match_weight_semantic,
                      f"Cosine similarity {semantic_cos:.2f} between the job description and the candidate's "
                      "skills, projects and experience"))
    need_years = float(job.get("experience_years") or 0)
    if need_years <= 0:
        exp_val, exp_reason = 1.0, "The job does not require prior experience"
    elif work:
        exp_val, exp_reason = 0.5, (f"Job asks for {need_years:g} year(s); candidate lists {len(work)} job(s)/"
                                    "internship(s) - duration not verified")
    else:
        exp_val, exp_reason = 0.0, f"Job asks for {need_years:g} year(s); candidate lists no work experience"
    parts.append(("Experience", exp_val, s.match_weight_experience, exp_reason))

    total_w = sum(w for _, _, w, _ in parts) or 1.0
    raw = 100 * sum(v * w for _, v, w, _ in parts) / total_w
    score, capped = raw, False
    if req_cov is not None and raw > 40 + 60 * req_cov:
        score, capped = 40 + 60 * req_cov, True
    if profile_empty:
        score = 0.0
    score = int(round(score))

    matched = [r["skill"] for r in req_rows + pref_rows if r["status"] == "matched"]
    partial = [{k: r[k] for k in ("skill", "closest", "similarity")} for r in req_rows + pref_rows
               if r["status"] == "partial"]
    miss_req = [r["skill"] for r in req_rows if r["status"] == "missing"]
    miss_pref = [r["skill"] for r in pref_rows if r["status"] == "missing"]

    relevant = []
    if semantic_ok and proj_vecs is not None:
        sims = proj_vecs @ doc_vecs[0]
        relevant = sorted(({"name": p.get("name") or "Untitled project", "similarity": round(float(x), 2)}
                           for p, x in zip(projects, sims) if float(x) >= PROJECT_SIM), key=lambda r: -r["similarity"])[:3]
    else:
        wanted = {normalize_skill(x) for x in required + preferred}
        relevant = [{"name": p.get("name") or "Untitled project", "similarity": None} for p in projects
                    if wanted & {normalize_skill(t) for t in p.get("technologies") or []}][:3]

    issues = list(eligibility_issues or [])
    if not issues and score >= 75 and not miss_req:
        rec = "strong_fit"
    elif not issues and score >= 50:
        rec = "potential_fit"
    else:
        rec = "not_a_fit"

    strengths, concerns = [], []
    if matched:
        strengths.append("Has " + ", ".join(matched[:8]))
    if relevant:
        strengths.append("Relevant project(s): " + ", ".join(r["name"] for r in relevant))
    if miss_req:
        concerns.append("Missing required skill(s): " + ", ".join(miss_req))
    if partial:
        concerns.append("Related but not exact: " + ", ".join(f"{p['skill']} (has {p['closest']})" for p in partial))
    concerns += issues
    if profile_empty:
        concerns.append("The candidate has not added skills, projects or experience, or uploaded an analysed resume.")

    expl = [f"Overall {score}/100 from " + "; ".join(f"{n.lower()} {round(v * 100)}%" for n, v, _, _ in parts) + "."]
    if capped:
        expl.append(f"The score was capped at {score} because some required skills are missing - similarity "
                    "alone cannot make up for them.")
    if not semantic_ok and sem_error:
        expl.append(f"Semantic similarity was not used: {sem_error}")
    if issues:
        expl.append("Eligibility: " + "; ".join(issues) + ".")

    return {
        "score": score,
        "method": "semantic" if semantic_ok else "rule_based",
        "recommendation": rec,
        "matched_skills": matched,
        "missing_skills": miss_req + miss_pref,
        "missing_required_skills": miss_req,
        "missing_preferred_skills": miss_pref,
        "partially_matched_skills": partial,
        "relevant_projects": relevant,
        "suggested_skills": (miss_req + [p["skill"] for p in partial] + miss_pref)[:8],
        "criteria_scores": [{"criterion": n, "score": round(v * 100), "reason": r} for n, v, _, r in parts],
        "weights": {n: round(w / total_w, 3) for n, _, w, _ in parts},
        "semantic_similarity": round(semantic_cos, 3) if semantic_cos is not None else None,
        "score_capped": capped,
        "eligible": not issues,
        "eligibility_issues": issues,
        "strengths": strengths,
        "concerns": concerns,
        "explanation": " ".join(expl),
        "embedding_model": get_settings().embedding_model if semantic_ok else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
