"""The MongoDB data layer (app/odm.py): SQL semantics the routers rely on."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    ApplicationStatusHistory, Badge, InterviewAnswer, InterviewQuestion, InterviewSession, Job, JobApplication,
    Notification, Resume, ResumeSkill, StudentBadge, StudentProfile, User,
)
from app.odm import IntegrityError, delete, func, or_, select, update


def _user(db, email, role="student", **kw):
    u = User(email=email, password_hash="x", full_name=email.split("@")[0], role=role, **kw)
    db.add(u)
    db.flush()
    return u


def test_ids_defaults_and_roundtrip(db_session_factory):
    db = db_session_factory()
    u = _user(db, "a@t.dev")
    assert isinstance(u.id, int) and u.status == "active" and u.permissions == [] and u.created_at.tzinfo
    db.commit()
    other = db_session_factory()
    again = other.get(User, u.id)
    assert again is not u and again.email == "a@t.dev" and again.created_at.tzinfo is not None
    assert db_session_factory().get(User, 10**9) is None


def test_only_changed_fields_are_written(db_session_factory):
    a, b = db_session_factory(), db_session_factory()
    u = _user(a, "c@t.dev")
    a.commit()
    ua, ub = a.get(User, u.id), b.get(User, u.id)
    ua.full_name = "From A"
    ub.preferences = {"subtitles": True}
    a.commit()
    b.commit()  # must not overwrite A's full_name with the stale value it read
    fresh = db_session_factory().get(User, u.id)
    assert fresh.full_name == "From A" and fresh.preferences == {"subtitles": True}


def test_in_place_json_changes_are_saved(db_session_factory):
    db = db_session_factory()
    u = _user(db, "j@t.dev")
    db.commit()
    u.permissions.append("view_all_students")
    db.commit()
    assert db_session_factory().get(User, u.id).permissions == ["view_all_students"]


def test_unique_constraint_raises_and_flush_is_undone(db_session_factory):
    db = db_session_factory()
    _user(db, "dup@t.dev")
    db.commit()
    db.add(User(email="new@t.dev", password_hash="x", full_name="n", role="student"))
    db.add(User(email="dup@t.dev", password_hash="x", full_name="d", role="student"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert db.scalar(select(func.count()).select_from(User).where(User.email == "new@t.dev")) == 0


def test_null_values_do_not_collide_in_unique_constraints(db_session_factory):
    """uq_integrity_client_event covers a nullable column: like SQL, several NULLs are allowed."""
    from app.models import IntegrityEvent
    db = db_session_factory()
    s = InterviewSession(student_id=_user(db, "n@t.dev").id, job_role="Dev", category="technical")
    db.add(s)
    db.flush()
    for _ in range(2):
        db.add(IntegrityEvent(session_id=s.id, event_type="tab_switch", t_ms=1, client_event_id=None))
    db.commit()
    db.add(IntegrityEvent(session_id=s.id, event_type="tab_switch", t_ms=2, client_event_id="e1"))
    db.commit()
    db.add(IntegrityEvent(session_id=s.id, event_type="tab_switch", t_ms=3, client_event_id="e1"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_begin_nested_skips_only_the_failing_row(db_session_factory):
    db = db_session_factory()
    _user(db, "x@t.dev")
    db.commit()
    stored = 0
    for email in ("x@t.dev", "y@t.dev"):
        try:
            with db.begin_nested():
                db.add(User(email=email, password_hash="x", full_name="n", role="student"))
            stored += 1
        except IntegrityError:
            pass
    db.commit()
    assert stored == 1
    assert sorted(db.scalars(select(User.email).where(User.email.in_(["x@t.dev", "y@t.dev"])))) == \
        ["x@t.dev", "y@t.dev"]


def test_relationships_one_to_one_one_to_many_and_orphans(db_session_factory):
    db = db_session_factory()
    u = User(email="r@t.dev", password_hash="x", full_name="R", role="student")
    u.student_profile = StudentProfile(branch="CSE", skills=[], projects=[], experience=[])
    db.add(u)
    db.commit()
    assert db_session_factory().get(StudentProfile, u.id).branch == "CSE"

    s = InterviewSession(student_id=u.id, job_role="Dev", category="technical")
    db.add(s)
    for pos in (2, 1):
        s.questions.append(InterviewQuestion(position=pos, text=f"Q{pos}"))
    db.commit()
    fresh = db_session_factory().get(InterviewSession, s.id)
    assert [q.text for q in fresh.questions] == ["Q1", "Q2"]  # order_by="InterviewQuestion.position"
    assert fresh.questions[0].session is fresh

    q1 = s.questions[0]
    q1.answer = InterviewAnswer(text="answer")
    db.commit()
    assert db_session_factory().get(InterviewQuestion, q1.id).answer.text == "answer"

    s.questions.remove(q1)  # delete-orphan
    db.commit()
    assert db_session_factory().get(InterviewQuestion, q1.id) is None
    assert db.scalar(select(func.count()).select_from(InterviewAnswer)) == 0  # cascaded


def test_delete_cascades_and_sets_null(db_session_factory):
    db = db_session_factory()
    stu, rec = _user(db, "s@t.dev"), _user(db, "rc@t.dev", role="recruiter")
    resume = Resume(student_id=stu.id, filename="cv.pdf", stored_path="x", content_type="application/pdf")
    resume.skills.append(ResumeSkill(name="Python"))
    db.add(resume)
    job = Job(recruiter_id=rec.id, title="Dev", company_name="Co", description="d")
    db.add(job)
    db.flush()
    app_ = JobApplication(job_id=job.id, student_id=stu.id)
    db.add(app_)
    db.flush()
    app_.history.append(ApplicationStatusHistory(to_status="applied", changed_by=rec.id))
    db.add(Notification(user_id=stu.id, title="hi", message="b"))
    db.commit()

    db.execute(delete(User).where(User.id == rec.id))  # recruiter: their jobs and applications go too
    db.commit()
    check = db_session_factory()
    assert check.get(Job, job.id) is None and check.get(JobApplication, app_.id) is None
    assert check.scalar(select(func.count()).select_from(ApplicationStatusHistory)) == 0

    db.delete(db.get(User, stu.id))
    db.commit()
    for model in (Resume, ResumeSkill, Notification, StudentProfile):
        assert check.scalar(select(func.count()).select_from(model)) == 0, model


def test_set_null_on_delete(db_session_factory):
    from app.models import AuditLog
    db = db_session_factory()
    u = _user(db, "actor@t.dev")
    db.add(AuditLog(actor_id=u.id, action="x"))
    db.commit()
    db.delete(u)
    db.commit()
    log = db_session_factory().scalar(select(AuditLog).where(AuditLog.action == "x"))
    assert log is not None and log.actor_id is None


def test_where_semantics_joins_groups_and_ordering(db_session_factory):
    db = db_session_factory()
    users = [_user(db, f"u{i}@t.dev", status="active" if i % 2 else "pending") for i in range(5)]
    for i, u in enumerate(users):
        db.add(StudentProfile(user_id=u.id, branch=None if i == 0 else ("CSE" if i < 3 else "ECE"),
                              skills=[], projects=[], experience=[]))
        db.add(InterviewSession(student_id=u.id, job_role="Dev", category="technical", status="completed",
                                overall_score=None if i == 4 else 50.0 + i * 10))
    db.commit()

    # != never matches NULL (SQL), is_(None) does
    assert db.scalar(select(func.count()).select_from(StudentProfile).where(StudentProfile.branch != "CSE")) == 2
    assert db.scalar(select(func.count()).select_from(StudentProfile).where(StudentProfile.branch.is_(None))) == 1
    assert db.scalar(select(func.count()).select_from(User).where(
        or_(User.email.ilike("U1@%"), User.email.ilike("%u2@t.DEV")))) == 2

    # GROUP BY with an aggregate over a join; AVG skips NULL
    rows = dict(db.execute(select(StudentProfile.branch, func.avg(InterviewSession.overall_score))
                           .join(InterviewSession, InterviewSession.student_id == StudentProfile.user_id)
                           .where(StudentProfile.branch.is_not(None)).group_by(StudentProfile.branch)).all())
    assert rows == {"CSE": 65.0, "ECE": 80.0}
    assert db.scalar(select(func.sum(InterviewSession.overall_score)).where(InterviewSession.id < 0)) is None
    assert db.scalar(select(func.coalesce(func.sum(InterviewSession.overall_score), 0))
                     .where(InterviewSession.id < 0)) == 0

    # outer join keeps users without a match; join inferred from the foreign key
    assert len(db.scalars(select(User).outerjoin(StudentProfile).where(StudentProfile.branch.is_(None))).all()) == 2
    assert len(db.scalars(select(User).outerjoin(StudentProfile).where(  # the admin has no profile at all
        User.role == "admin", StudentProfile.user_id.is_(None))).all()) == 1
    assert len(db.scalars(select(InterviewSession).join(User).where(User.status == "pending")).all()) == 3

    # NULLs sort lowest unless asked otherwise
    asc_ = db.scalars(select(InterviewSession.overall_score).order_by(InterviewSession.overall_score)).all()
    assert asc_[0] is None
    desc_last = db.scalars(select(InterviewSession.overall_score)
                           .order_by(InterviewSession.overall_score.desc().nullslast())).all()
    assert desc_last[-1] is None and desc_last[0] == 80.0
    first_two = db.scalars(select(User).order_by(User.id.desc()).offset(1).limit(2)).all()
    assert [u.id for u in first_two] == [users[3].id, users[2].id]

    # IN (sub-select) and labelled aggregate rows
    pending = select(User.id).where(User.status == "pending")
    assert len(db.scalars(select(InterviewSession).where(InterviewSession.student_id.in_(pending))).all()) == 3
    row = db.execute(select(func.count(InterviewSession.overall_score).label("n"))).one()
    assert row.n == 4


def test_bulk_update_refreshes_loaded_objects(db_session_factory):
    db = db_session_factory()
    u = _user(db, "bulk@t.dev")
    n = Notification(user_id=u.id, title="t", message="b")
    db.add(n)
    db.commit()
    assert db.execute(update(Notification).where(Notification.user_id == u.id).values(read=True)).rowcount == 1
    assert n.read is True


def test_rollback_reloads_and_unique_partial_insert(db_session_factory):
    db = db_session_factory()
    u = _user(db, "rb@t.dev")
    db.commit()
    u.full_name = "changed"
    db.rollback()
    assert u.full_name == "rb"


def test_onupdate_timestamp(db_session_factory):
    db = db_session_factory()
    rec = _user(db, "on@t.dev", role="recruiter")
    job = Job(recruiter_id=rec.id, title="Dev", company_name="Co", description="d")
    db.add(job)
    db.commit()
    before = job.updated_at
    job.updated_at = before - timedelta(days=1)  # set explicitly: kept
    db.commit()
    assert db_session_factory().get(Job, job.id).updated_at < before
    job.title = "Senior Dev"
    db.commit()
    assert db_session_factory().get(Job, job.id).updated_at > datetime.now(timezone.utc) - timedelta(minutes=1)


def test_unique_student_badge(db_session_factory):
    db = db_session_factory()
    u = _user(db, "b@t.dev")
    badge = db.scalars(select(Badge)).first()
    db.add(StudentBadge(student_id=u.id, badge_id=badge.id))
    db.commit()
    assert db.scalars(select(StudentBadge).where(StudentBadge.student_id == u.id)).one().badge is badge
    db.add(StudentBadge(student_id=u.id, badge_id=badge.id))
    with pytest.raises(IntegrityError):
        db.commit()
