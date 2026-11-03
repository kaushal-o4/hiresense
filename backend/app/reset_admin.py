"""Reset the admin account's password (e.g. when the one printed by the first seed was lost).

    python -m app.reset_admin                 # generates a new password and prints it once
    python -m app.reset_admin "NewPass@2026"  # sets the given password

Resets the account named by ADMIN_EMAIL, re-creating it if it is missing, and re-activates it.
"""
import secrets
import sys

from .odm import select

from .config import get_settings
from .database import SessionLocal
from .models import User
from .seed import PUBLISHED_ADMIN_PASSWORD
from .security import hash_password


def reset_admin(password: str | None = None) -> None:
    settings = get_settings()
    email = settings.admin_email.lower()
    if password == PUBLISHED_ADMIN_PASSWORD:
        sys.exit("Refusing to use the old published admin password. Choose another one.")
    generated = not password
    password = password or secrets.token_urlsafe(12)
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email, full_name="Platform Administrator", role="admin", password_hash="")
            db.add(user)
        user.password_hash = hash_password(password)
        user.role = "admin"
        user.status = "active"
        db.commit()
    finally:
        db.close()
    print(f"Admin password reset for {email}")
    if generated:
        print(f"  New password (shown only now - store it safely): {password}")


if __name__ == "__main__":
    reset_admin(sys.argv[1] if len(sys.argv) > 1 else None)
