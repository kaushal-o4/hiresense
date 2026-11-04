"""Outgoing email over SMTP (optional).

Email is off unless SMTP_HOST is set in backend/.env. When it is off, send() logs the message instead and returns
False, so callers can fall back (e.g. the password-reset link is printed to the server log for an administrator).
Messages are sent on a background thread so a slow mail server never delays an API response.
"""
import logging
import smtplib
from . import background
from email.message import EmailMessage

from ..config import get_settings

logger = logging.getLogger("hiresense.mail")


def enabled() -> bool:
    return bool(get_settings().smtp_host)


def _deliver(msg: EmailMessage) -> None:
    s = get_settings()
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
    except Exception:  # noqa: BLE001 - email is best effort; never break the request that triggered it
        logger.warning("could not send email to %s (%s)", msg["To"], msg["Subject"], exc_info=True)


def send(to: str, subject: str, body: str) -> bool:
    """Queue a plain-text email. Returns False (and logs) when email is not configured."""
    if not enabled():
        logger.info("email disabled (SMTP_HOST empty); not sent to %s: %s", to, subject)
        return False
    msg = EmailMessage()
    msg["From"] = get_settings().smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    background.spawn(_deliver, msg, name="mail")
    return True
