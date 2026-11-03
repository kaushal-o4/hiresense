"""Sample job openings and placement drives so students have something to apply for.

    python -m app.seed_jobs            # adds what is missing; safe to run again (skips existing titles)

Jobs are published under the first active recruiter account (recruiters own their postings and see the applicants);
drives are created by the first admin, and eligible students get the usual drive notification. Company names are
fictional. Remove them from the recruiter / admin portals like any other posting.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .database import SessionLocal, init_db
from .models import Job, JobRequirement, PlacementDrive, User
from .odm import select
from .services.common import audit, normalize_skills, notify

CS = ["Computer Science", "Computer Engineering", "Information Technology"]
ALL_TECH = CS + ["Electronics and Telecommunication", "Electrical", "Mechanical", "Civil"]
YEARS = [2026, 2027]

# title, company, location, type, salary, min_cgpa, branches, years, deadline_days, required, preferred, description
JOBS = [
    ("Backend Developer (Node.js)", "Brightlabs Software", "Pune", "full_time", "₹6–8 LPA", None, CS, YEARS, 30,
     ["Node.js", "Express", "MongoDB", "REST APIs"], ["Docker", "Redis", "TypeScript"],
     "Build and maintain the REST APIs behind our SaaS products used by 2 lakh+ users. You will design endpoints, "
     "write MongoDB queries, add tests and work with the frontend team on new features. Freshers with solid "
     "projects are welcome; you get a 6-week onboarding with a mentor."),
    ("Frontend Developer (React)", "Pixelcraft Studios", "Bengaluru", "full_time", "₹5–7 LPA", None, CS, YEARS, 28,
     ["React", "JavaScript", "HTML", "CSS"], ["TypeScript", "Tailwind CSS", "Redux"],
     "Turn designs into fast, accessible web interfaces for e-commerce and fintech clients. You will build reusable "
     "React components, connect them to APIs and fix performance issues. A portfolio or GitHub link helps."),
    ("Software Engineer Intern", "Northwind Systems", "Hyderabad", "internship", "₹25,000 / month", None, CS, YEARS, 21,
     ["Java", "Data Structures", "Algorithms"], ["Spring Boot", "SQL", "Git"],
     "6-month internship on our logistics platform team, with a pre-placement offer for strong performers. Expect "
     "code reviews, real tickets and weekly learning sessions."),
    ("Full Stack Developer (MERN)", "Campuskart", "Pune", "full_time", "₹7–9 LPA", 6.5, CS, YEARS, 35,
     ["MongoDB", "Express", "React", "Node.js"], ["AWS", "Docker", "JWT"],
     "Own features end to end on a student marketplace app: database schema, API, UI and deployment. Small team, "
     "lots of ownership."),
    ("Data Analyst", "Insightloop Analytics", "Mumbai", "full_time", "₹4.5–6 LPA", None, [], YEARS, 30,
     ["SQL", "Python", "Excel"], ["Power BI", "Pandas", "Statistics"],
     "Help retail and healthcare clients make decisions from their data: clean datasets, write SQL, build "
     "dashboards and present findings. Open to all branches."),
    ("Machine Learning Intern", "Cortex AI Labs", "Remote", "internship", "₹30,000 / month", 7.0, CS, YEARS, 25,
     ["Python", "scikit-learn", "Pandas"], ["PyTorch", "NLP", "Git"],
     "Work on real ML problems - document classification and forecasting - with our research team. You will "
     "prepare data, train and evaluate models and write up results. 3–6 months, remote."),
    ("Cloud & DevOps Engineer Trainee", "Stratus Cloudworks", "Chennai", "full_time", "₹5–6.5 LPA", None, CS, YEARS, 40,
     ["Linux", "AWS", "Docker"], ["Kubernetes", "CI/CD", "Terraform"],
     "A 12-month trainee programme: you start with Linux and networking, then move to AWS, containers and CI/CD "
     "pipelines on customer projects. AWS certification is sponsored."),
    ("QA Automation Engineer", "Testwise Technologies", "Noida", "full_time", "₹4–5.5 LPA", None, CS, YEARS, 30,
     ["Java", "Selenium", "Testing"], ["TestNG", "API Testing", "Jenkins"],
     "Write automated tests for web and mobile apps, find bugs before users do and improve our test pipelines."),
    ("Android Developer Intern", "Appforge Mobile", "Remote", "internship", "₹20,000 / month", None, CS, YEARS, 20,
     ["Kotlin", "Android"], ["Jetpack Compose", "Firebase"],
     "Build features for Android apps with 1M+ downloads. Remote internship, 3 months, with a chance to convert to "
     "full time."),
    ("Business Analyst Trainee", "Meridian Consulting", "Gurugram", "full_time", "₹5–6 LPA", None, [], YEARS, 32,
     ["Communication", "Excel", "Problem Solving"], ["SQL", "Presentation Skills"],
     "Work with client teams to understand business problems, gather requirements and turn them into clear "
     "documents and dashboards. Strong communication matters more than your branch."),
    ("Cybersecurity Analyst Trainee", "Shieldbyte Security", "Bengaluru", "full_time", "₹5.5–7 LPA", None, CS, YEARS, 30,
     ["Networking", "Linux", "Security Fundamentals"], ["Python", "SIEM", "Ethical Hacking"],
     "Join our security operations centre: monitor alerts, investigate incidents and help harden client systems. "
     "Training and certifications provided."),
    ("Graduate Engineer Trainee (Electronics)", "Voltaris Embedded", "Pune", "full_time", "₹4.5–5.5 LPA", 6.0,
     ["Electronics and Telecommunication", "Electrical"], YEARS, 30,
     ["Embedded C", "Microcontrollers"], ["RTOS", "PCB Design"],
     "Design and test firmware for industrial IoT devices. Open to Electronics and Electrical students."),
]

# title, company, days_from_now, location, min_cgpa, branches, description
DRIVES = [
    ("Brightlabs Software Campus Drive", "Brightlabs Software", 16, "Main auditorium + online test", None, CS,
     "Roles: Backend Developer, Frontend Developer. Rounds: online aptitude + coding test, technical interview, HR "
     "interview. Carry your resume and college ID."),
    ("Pool Campus Drive - 6 Companies", "Multiple companies", 24, "Seminar hall, Block A", None, ALL_TECH,
     "Brightlabs, Pixelcraft, Testwise, Stratus Cloudworks, Meridian Consulting and Insightloop recruit together. "
     "One common aptitude test, then company-wise interviews."),
    ("Northwind Systems Internship Drive", "Northwind Systems", 31, "Online", None, CS,
     "6-month internship with pre-placement offer. Online coding round (2 problems, 90 minutes), then a technical "
     "interview on data structures and your projects."),
    ("Insightloop Analytics Hiring Day", "Insightloop Analytics", 38, "Online + Mumbai office", None, [],
     "Data Analyst roles, open to all branches. SQL and Excel test, case-study round and a short HR conversation."),
    ("Cortex AI Labs Hackathon Hiring", "Cortex AI Labs", 45, "Online, 24 hours", 7.0, CS,
     "Solve a real ML problem in 24 hours in teams of up to 3. Top teams are interviewed for ML internships."),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        recruiter = db.scalar(select(User).where(User.role == "recruiter", User.status == "active").order_by(User.id))
        admin = db.scalar(select(User).where(User.role == "admin").order_by(User.id))
        now = datetime.now(timezone.utc)
        added_jobs = added_drives = notified = 0

        if recruiter is None:
            print("No active recruiter account - jobs skipped. Register/approve a recruiter first, then run again.")
        else:
            existing = {(j.title, j.company_name) for j in db.scalars(select(Job))}
            for (title, company, location, jtype, salary, cgpa, branches, years, days, req, pref, desc) in JOBS:
                if (title, company) in existing:
                    continue
                job = Job(recruiter_id=recruiter.id, company_name=company, title=title, description=desc,
                          location=location, job_type=jtype, experience_years=0, salary=salary, min_cgpa=cgpa,
                          eligible_branches=normalize_skills(branches), graduation_years=sorted(set(years)),
                          deadline=now + timedelta(days=days), status="published", published_at=now)
                required = normalize_skills(req)
                for s in required:
                    job.requirements.append(JobRequirement(skill=s, importance="required"))
                for s in normalize_skills(pref):
                    if s.lower() not in {r.lower() for r in required}:
                        job.requirements.append(JobRequirement(skill=s, importance="preferred"))
                db.add(job)
                db.flush()
                audit(db, recruiter.id, "job.create", "job", job.id, {"title": title, "status": "published", "seed": True})
                added_jobs += 1

        existing_d = {d.title for d in db.scalars(select(PlacementDrive))}
        students = list(db.scalars(select(User).where(User.role == "student", User.status == "active")))
        for (title, company, days, location, cgpa, branches, desc) in DRIVES:
            if title in existing_d:
                continue
            when = (now + timedelta(days=days)).replace(hour=4, minute=30, second=0, microsecond=0)  # 10:00 IST
            d = PlacementDrive(title=title, company_name=company, description=desc, drive_date=when,
                               location=location, min_cgpa=cgpa, eligible_branches=normalize_skills(branches),
                               status="upcoming", created_by=admin.id if admin else None)
            db.add(d)
            db.flush()
            for st in students:
                p = st.student_profile
                if cgpa is not None and (not p or p.cgpa is None or p.cgpa < cgpa):
                    continue
                if d.eligible_branches and (not p or not p.branch or
                                            p.branch.lower() not in {b.lower() for b in d.eligible_branches}):
                    continue
                notify(db, st.id, f"Placement drive: {company}",
                       f"{title} on {when.strftime('%d %b %Y')}. Register from the Placement Drives page.",
                       "drive", "/student/drives")
                notified += 1
            audit(db, admin.id if admin else None, "drive.create", "placement_drive", d.id, {"title": title, "seed": True})
            added_drives += 1
        db.commit()
        print(f"Added {added_jobs} job(s) and {added_drives} drive(s); {notified} drive notification(s) sent.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
