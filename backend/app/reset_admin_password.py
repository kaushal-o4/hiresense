# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/reset_admin_password.py
#
# FILE PURPOSE:
# Command-line tool to reset the admin account's password if the one printed by the seed was lost.
#
# WHAT THIS FILE DOES:
# 1. Resets (or re-creates) the account named by ADMIN_EMAIL.
# 2. Uses the password given on the command line or generates a strong one and prints it once.
# 3. Re-activates the account.
#
# HOW THIS FILE WORKS:
# Run `python -m app.reset_admin_password` or `python -m app.reset_admin_password "NewPass@2026"`.
#
# IMPORTANT FUNCTIONS:
#    - reset_admin()
#        Hashes the new password and saves it on the admin account.
#
# INPUT:
# Optional new password from the command line.
#
# OUTPUT:
# Updated admin account; the new password printed to the console.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/application_configuration.py, app/database_connection.py, app/database_models.py,
#    app/mongodb_data_layer/__init__.py, app/password_and_token_security.py,
#    app/seed_initial_data.py
#
# EXECUTION FLOW:
#    Run the script
#       |
#       v
#    Find/create admin
#       |
#       v
#    Hash and store new password
#       |
#       v
#    Print it
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Reset the admin account's password (e.g. when the one printed by the first seed was lost).

    python -m app.reset_admin_password                 # generates a new password and prints it once
    python -m app.reset_admin_password "NewPass@2026"  # sets the given password

Resets the account named by ADMIN_EMAIL, re-creating it if it is missing, and re-activates it.
"""
import secrets
import sys

from .mongodb_data_layer import select

from .application_configuration import get_settings
from .database_connection import SessionLocal
from .database_models import User
from .seed_initial_data import PUBLISHED_ADMIN_PASSWORD
from .password_and_token_security import hash_password


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
