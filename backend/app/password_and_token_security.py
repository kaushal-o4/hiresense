# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/password_and_token_security.py
#
# FILE PURPOSE:
# Security helpers for passwords and login tokens: Argon2 password hashing and JWT creation/checking,
# including password-reset tokens.
#
# MAIN RESPONSIBILITY:
# Password hashing and JSON Web Token handling.
#
# WHAT THIS FILE DOES:
# 1. Hashes passwords with Argon2 (with a random salt) before they are stored.
# 2. Verifies a typed password against the stored hash.
# 3. Creates the signed session JWT (user id + role, expiry) and decodes it.
# 4. Creates password-reset tokens that become invalid once the password changes.
#
# HOW THIS FILE WORKS:
# Passwords are never stored in plain text: only the Argon2 hash is saved in User.password_hash.
# Tokens are signed with SECRET_KEY using HS256, so a changed token fails verification.
#
# IMPORTANT FUNCTIONS:
#    - hash_password()
#        Argon2 hash of a password (includes a random salt), stored in `User.password_hash`.
#    - verify_password()
#        True if the password matches the stored Argon2 hash; False for a wrong password or a
#        broken hash.
#    - create_access_token()
#        Signed session JWT (HS256 with SECRET_KEY) carrying the user id and role, valid for
#        ACCESS_TOKEN_MINUTES.
#    - decode_access_token()
#        Payload of a valid, unexpired session JWT, or None (bad signature, expired,
#        malformed).
#    - create_reset_token()
#        Password-reset JWT: signed with the reset key, tied to the current password hash,
#        valid for PASSWORD_RESET_MINUTES.
#    - read_reset_token()
#        Payload of a valid, unexpired reset token, or None.
#    - reset_token_matches()
#        True if the token was issued for the user's CURRENT password (so used/old links are
#        rejected).
#    Other helper functions: _reset_key, _password_fingerprint
#
# IMPORTANT VARIABLES / SETTINGS:
#    ALGORITHM, COOKIE_NAME
#
# INPUT:
# Plain passwords, user ids/roles, tokens.
#
# OUTPUT:
# Password hashes, True/False checks, signed token strings, decoded token payloads.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/application_configuration.py
#    Used by: app/authentication_dependencies.py, app/main.py, app/reset_admin_password.py,
#    app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
#    app/routers/profile_and_notification_routes.py, app/seed_initial_data.py
#    Tested by: tests/test_account_security.py, tests_e2e/account_browser.py
#
# EXECUTION FLOW:
#    User logs in
#       |
#       v
#    verify_password() checks hash
#       |
#       v
#    create_access_token() makes JWT
#       |
#       v
#    authentication_routes.py sets it as an httpOnly cookie
#
# IMPORTANT DEPENDENCIES:
#    argon2, jwt
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Password hashing (Argon2) and JWT creation/verification helpers.
"""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .application_configuration import get_settings

_hasher = PasswordHasher()
ALGORITHM = "HS256"
COOKIE_NAME = "hs_session"


def hash_password(password: str) -> str:
    """Argon2 hash of a password (includes a random salt), stored in `User.password_hash`."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True if the password matches the stored Argon2 hash; False for a wrong password or a broken hash."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, role: str) -> str:
    """Signed session JWT (HS256 with SECRET_KEY) carrying the user id and role, valid for
    ACCESS_TOKEN_MINUTES. Set as the httpOnly cookie by routers/authentication_routes.py.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Payload of a valid, unexpired session JWT, or None (bad signature, expired, malformed)."""
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


# Password-reset tokens. Signed with a key DERIVED from the secret (never the session key), so a reset link can
# never be used as a login session. They carry a fingerprint of the current password hash, so a token stops
# working as soon as the password changes: every link is single-use and older links die with it.
def _reset_key() -> str:
    return hashlib.sha256(f"{get_settings().secret_key}:password-reset".encode()).hexdigest()


def _password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:20]


def create_reset_token(user_id: int, password_hash: str) -> str:
    """Password-reset JWT: signed with the reset key, tied to the current password hash, valid for
    PASSWORD_RESET_MINUTES.
    """
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "pwf": _password_fingerprint(password_hash), "purpose": "password-reset",
               "iat": now, "exp": now + timedelta(minutes=get_settings().password_reset_minutes)}
    return jwt.encode(payload, _reset_key(), algorithm=ALGORITHM)


def read_reset_token(token: str) -> dict | None:
    """Payload of a valid, unexpired reset token, or None. The caller must still call reset_token_matches()."""
    try:
        payload = jwt.decode(token, _reset_key(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("purpose") == "password-reset" else None


def reset_token_matches(payload: dict, password_hash: str) -> bool:
    """True if the token was issued for the user's CURRENT password (so used/old links are rejected)."""
    return hmac.compare_digest(payload.get("pwf", ""), _password_fingerprint(password_hash))
