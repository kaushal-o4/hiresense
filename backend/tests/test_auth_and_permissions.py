# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/tests/test_auth_and_permissions.py
#
# FILE PURPOSE:
# Tests registration, login and the current-user endpoint, password rules, wrong-password lockout,
# password hashing, role-based access, recruiter approval, and that mentors and students can only see
# the data they are allowed to see.
#
# WHAT THIS FILE DOES:
# 1. Automated test (pytest, mocked AI - no real model needed).
# 2. Contains 9 test(s), e.g.: register login me; password rules and duplicates; wrong password and
#    lockout; passwords are hashed; role based access; recruiter requires approval; admin cannot
#    demote self; mentor only sees assigned students; ....
# 3. Run from backend/: python -m pytest tests -q. These tests run in CI on every push.
#
# IMPORTANT FUNCTIONS:
#    Other helper functions: test_register_login_me, test_password_rules_and_duplicates,
#    test_wrong_password_and_lockout, test_passwords_are_hashed, test_role_based_access,
#    test_recruiter_requires_approval, test_admin_cannot_demote_self,
#    test_mentor_only_sees_assigned_students, test_student_cannot_access_other_students_data
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/database_models.py
#
# IMPORTANT NOTE:
# Test/tool file: it checks or measures the application and is not used by the running app.
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

from conftest import admin_login, login, register_student


def test_register_login_me(client):
    user = register_student(client)
    assert user["role"] == "student"
    me = client.get("/api/auth/me").json()
    assert me["user"]["email"] == "stu@test.dev"
    assert me["ai"]["configured"] is False
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    login(client, "stu@test.dev", "Passw0rd!")
    assert client.get("/api/auth/me").status_code == 200


def test_password_rules_and_duplicates(client):
    r = client.post("/api/auth/register/student", json={"full_name": "X Y", "email": "a@b.dev", "password": "short"})
    assert r.status_code == 422
    register_student(client, email="dup@test.dev")
    r = client.post("/api/auth/register/student", json={"full_name": "X Y", "email": "dup@test.dev", "password": "Passw0rd!"})
    assert r.status_code == 409


def test_wrong_password_and_lockout(client):
    register_student(client, email="lock@test.dev")
    client.post("/api/auth/logout")
    for _ in range(8):
        assert client.post("/api/auth/login", json={"email": "lock@test.dev", "password": "wrongpass1"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "lock@test.dev", "password": "Passw0rd!"}).status_code == 429


def test_passwords_are_hashed(client, db):
    from app.database_models import User
    register_student(client, email="hash@test.dev")
    u = db.query(User).filter_by(email="hash@test.dev").one()
    assert u.password_hash != "Passw0rd!" and u.password_hash.startswith("$argon2")


def test_role_based_access(client, new_client):
    register_student(client)
    assert client.get("/api/admin/dashboard").status_code == 403
    assert client.get("/api/recruiter/dashboard").status_code == 403
    assert client.get("/api/mentor/dashboard").status_code == 403
    assert client.get("/api/student/dashboard").status_code == 200

    anon = new_client()
    assert anon.get("/api/student/dashboard").status_code == 401

    admin = new_client()
    admin_login(admin)
    assert admin.get("/api/admin/dashboard").status_code == 200
    assert admin.get("/api/student/dashboard").status_code == 403


def test_recruiter_requires_approval(client, new_client):
    r = client.post("/api/auth/register/recruiter", json={"full_name": "Rita Recruiter", "email": "rec@corp.dev",
                                                           "password": "Passw0rd!", "company_name": "Acme"})
    assert r.status_code == 201 and r.json()["pending_approval"] is True
    assert client.post("/api/auth/login", json={"email": "rec@corp.dev", "password": "Passw0rd!"}).status_code == 403

    admin = new_client()
    admin_login(admin)
    users = admin.get("/api/admin/users", params={"status": "pending"}).json()["items"]
    rec = next(u for u in users if u["email"] == "rec@corp.dev")
    assert admin.patch(f"/api/admin/users/{rec['id']}", json={"status": "active"}).status_code == 200
    login(client, "rec@corp.dev", "Passw0rd!")
    assert client.get("/api/recruiter/dashboard").status_code == 200

    # Suspension takes effect immediately, even with a valid token.
    admin.patch(f"/api/admin/users/{rec['id']}", json={"status": "suspended"})
    assert client.get("/api/recruiter/dashboard").status_code == 403
    logs = admin.get("/api/admin/audit-logs", params={"action": "user.update"}).json()["items"]
    assert len(logs) >= 2


def test_admin_cannot_demote_self(client):
    me = admin_login(client)
    assert client.patch(f"/api/admin/users/{me['id']}", json={"status": "suspended"}).status_code == 400


def test_mentor_only_sees_assigned_students(client, new_client):
    s1 = register_student(client, email="s1@test.dev")
    s2c = new_client()
    s2 = register_student(s2c, email="s2@test.dev")

    admin = new_client()
    admin_login(admin)
    m = admin.post("/api/admin/users", json={"full_name": "Meera Mentor", "email": "m@test.dev",
                                            "password": "Passw0rd!", "role": "mentor"}).json()
    assert admin.post("/api/admin/assignments", json={"mentor_id": m["id"], "student_ids": [s1["id"]]}).status_code == 201

    mentor = new_client()
    login(mentor, "m@test.dev", "Passw0rd!")
    ids = [s["id"] for s in mentor.get("/api/mentor/students").json()]
    assert ids == [s1["id"]]
    assert mentor.get(f"/api/mentor/students/{s1['id']}").status_code == 200
    assert mentor.get(f"/api/mentor/students/{s2['id']}").status_code == 403
    assert mentor.post(f"/api/mentor/students/{s2['id']}/feedback", json={"content": "hi"}).status_code == 403

    # Admin grants extra permission -> mentor can view all students.
    admin.patch(f"/api/admin/users/{m['id']}", json={"permissions": ["view_all_students"]})
    assert mentor.get(f"/api/mentor/students/{s2['id']}").status_code == 200


def test_student_cannot_access_other_students_data(client, new_client):
    register_student(client, email="a1@test.dev")
    other = new_client()
    register_student(other, email="a2@test.dev")
    from app.database_models import Resume  # noqa: F401
    # Notifications are private
    n = other.get("/api/notifications").json()["items"][0]
    assert client.post(f"/api/notifications/{n['id']}/read").status_code == 404


def test_cross_site_writes_with_session_cookie_are_blocked(client):
    """CSRF: a page on another site must not be able to make a signed-in browser send writes (body-less POSTs and
    multipart uploads are "simple" requests that CORS does not stop from being sent)."""
    register_student(client, email="csrf@test.dev")  # leaves the hs_session cookie in the client
    evil = {"Origin": "https://evil.example"}
    # body-less write from a foreign origin: refused, and it did not run (still signed in)
    r = client.post("/api/auth/logout", headers=evil)
    assert r.status_code == 403 and r.json()["detail"] == "Cross-site request blocked."
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/notifications/read-all", headers=evil).status_code == 403
    assert client.put("/api/settings", json={"subtitles": False}, headers=evil).status_code == 403
    # opaque origin (sandboxed iframe / no-referrer form) and a foreign Referer without Origin are refused too
    assert client.post("/api/notifications/read-all", headers={"Origin": "null"}).status_code == 403
    assert client.post("/api/notifications/read-all", headers={"Referer": "https://evil.example/page"}).status_code == 403
    # the real frontend origin, the API's own origin and non-browser clients (no Origin/Referer) still work
    assert client.post("/api/notifications/read-all", headers={"Origin": "http://localhost:5173"}).status_code == 200
    assert client.post("/api/notifications/read-all", headers={"Origin": "http://testserver"}).status_code == 200
    assert client.post("/api/notifications/read-all").status_code == 200
    # reads are never blocked
    assert client.get("/api/auth/me", headers=evil).status_code == 200


def test_cross_site_check_ignores_requests_without_session_cookie(client):
    """No session cookie = nothing for a forged request to ride on (Bearer clients, sign-in itself)."""
    r = client.post("/api/auth/login", json={"email": "nobody@test.dev", "password": "Wrong-pass-1"},
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 401  # normal login handling, not the CSRF block
