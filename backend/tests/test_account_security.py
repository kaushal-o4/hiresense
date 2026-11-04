"""Password reset, self-service account deletion, upload storage and the admin password policy."""
import io
import re
from pathlib import Path

from docx import Document
from app.odm import select

from app.config import get_settings
from app.models import AuditLog, Resume, User
from app.routers import auth as auth_router
from app.security import COOKIE_NAME, create_reset_token
from conftest import login, register_student


def docx_bytes(text: str) -> bytes:
    d = Document()
    d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def upload(c, text="Python developer. Skills: Python, SQL, Docker. Built REST APIs with Flask."):
    return c.post("/api/student/resumes", files={"file": ("cv.docx", docx_bytes(text),
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})


def capture_mail(monkeypatch):
    sent = []

    def fake_send(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})
        return True
    monkeypatch.setattr(auth_router.mailer, "send", fake_send)
    from app.services import limiter
    limiter.reset()
    return sent


def token_from(mail) -> str:
    return re.search(r"token=([\w.\-]+)", mail["body"]).group(1)


# ---------------------------------------------------------------- password reset

def test_forgot_password_does_not_reveal_accounts(client, monkeypatch):
    sent = capture_mail(monkeypatch)
    register_student(client, email="known@test.dev")
    a = client.post("/api/auth/forgot-password", json={"email": "known@test.dev"})
    b = client.post("/api/auth/forgot-password", json={"email": "nobody@test.dev"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert [m["to"] for m in sent] == ["known@test.dev"]


def test_reset_password_flow_is_single_use(client, new_client, monkeypatch):
    sent = capture_mail(monkeypatch)
    register_student(client, email="reset@test.dev")
    client.post("/api/auth/forgot-password", json={"email": "reset@test.dev"})
    token = token_from(sent[0])

    other = new_client()
    r = other.post("/api/auth/reset-password", json={"token": token, "new_password": "NewPassw0rd"})
    assert r.status_code == 200, r.text
    login(other, "reset@test.dev", "NewPassw0rd")
    assert other.post("/api/auth/login", json={"email": "reset@test.dev", "password": "Passw0rd!"}).status_code == 401
    # the same link can't be used twice (the password fingerprint changed)
    again = other.post("/api/auth/reset-password", json={"token": token, "new_password": "Another1pass"})
    assert again.status_code == 400


def test_reset_rejects_weak_password_and_garbage_token(client, monkeypatch):
    sent = capture_mail(monkeypatch)
    register_student(client, email="weak@test.dev")
    client.post("/api/auth/forgot-password", json={"email": "weak@test.dev"})
    assert client.post("/api/auth/reset-password",
                       json={"token": token_from(sent[0]), "new_password": "short"}).status_code == 422
    assert client.post("/api/auth/reset-password",
                       json={"token": "x" * 40, "new_password": "GoodPassw0rd"}).status_code == 400


def test_reset_token_cannot_be_used_as_a_session(client, new_client, db):
    register_student(client, email="sess@test.dev")
    user = db.scalar(select(User).where(User.email == "sess@test.dev"))
    other = new_client()
    other.cookies.set(COOKIE_NAME, create_reset_token(user.id, user.password_hash))
    assert other.get("/api/auth/me").status_code == 401


def test_reset_requests_are_rate_limited(client, monkeypatch):
    sent = capture_mail(monkeypatch)
    register_student(client, email="flood@test.dev")
    for _ in range(6):
        assert client.post("/api/auth/forgot-password", json={"email": "flood@test.dev"}).status_code == 200
    assert len(sent) == auth_router.MAX_RESET_REQUESTS


# ---------------------------------------------------------------- account deletion

def test_student_can_delete_own_account_and_files(client, db, fake_ai):
    register_student(client, email="gone@test.dev")
    assert upload(client).status_code == 201
    uid = db.scalar(select(User.id).where(User.email == "gone@test.dev"))
    files = [Path(p) for p in db.scalars(select(Resume.stored_path).where(Resume.student_id == uid))]
    assert files and all(f.exists() for f in files)

    bad = client.request("DELETE", "/api/auth/me", json={"password": "wrong", "confirm": "DELETE"})
    assert bad.status_code == 400
    r = client.request("DELETE", "/api/auth/me", json={"password": "Passw0rd!", "confirm": "DELETE"})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.scalar(select(User).where(User.email == "gone@test.dev")) is None
    assert not db.scalars(select(Resume).where(Resume.student_id == uid)).all()  # cascaded
    assert not any(f.exists() for f in files)
    assert db.scalar(select(AuditLog).where(AuditLog.action == "user.self_delete", AuditLog.entity_id == uid))
    assert client.get("/api/auth/me").status_code == 401  # signed out


def test_only_students_can_self_delete(client):
    from conftest import admin_login
    admin_login(client)
    r = client.request("DELETE", "/api/auth/me", json={"password": get_settings().admin_password, "confirm": "DELETE"})
    assert r.status_code == 403


# ---------------------------------------------------------------- uploads

def test_uploads_go_to_temp_dir_not_backend_uploads(client, db, fake_ai):
    register_student(client, email="up@test.dev")
    assert upload(client).status_code == 201
    stored = Path(db.scalar(select(Resume.stored_path)))
    real = (Path(__file__).resolve().parent.parent / "uploads").resolve()
    assert real not in stored.resolve().parents


def test_resume_history_is_capped(client, db, fake_ai, monkeypatch):
    from app.routers import students
    monkeypatch.setattr(students, "RESUME_HISTORY", 3)
    register_student(client, email="many@test.dev")
    for i in range(5):
        assert upload(client, text=f"Version {i}. Skills: Python, SQL.").status_code == 201
    rows = db.scalars(select(Resume).order_by(Resume.id)).all()
    assert len(rows) == 3 and rows[-1].is_current
    folder = Path(rows[0].stored_path).parent
    assert len(list(folder.iterdir())) == 3  # files of pruned versions were deleted too


# ---------------------------------------------------------------- admin password

def test_seed_generates_random_admin_password_when_unset(db_session_factory, monkeypatch, capsys):
    from app import seed as seed_module
    s = get_settings()
    monkeypatch.setattr(s, "admin_password", "")
    monkeypatch.setattr(s, "admin_email", "fresh-admin@test.dev")
    seed_module.seed()
    out = capsys.readouterr().out
    generated = re.search(r"Generated password .*: (\S+)", out).group(1)
    assert generated and generated != seed_module.PUBLISHED_ADMIN_PASSWORD
    db = db_session_factory()
    from app.security import verify_password
    admin = db.scalar(select(User).where(User.email == "fresh-admin@test.dev"))
    assert verify_password(generated, admin.password_hash)
    assert not verify_password(seed_module.PUBLISHED_ADMIN_PASSWORD, admin.password_hash)
