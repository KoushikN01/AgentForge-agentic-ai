"""
Authentication logic for the sample project.

NOTE: This module is part of the intentionally-buggy sample_project used
to demo AgentForge's investigation workflow. See
docs/sample-project-bugs.md at the AgentForge project root for the list of
bugs and why each one was introduced. (That file deliberately lives
outside sample_project/ so AgentForge's own tools don't just read the
answer key instead of investigating.)
"""

import hashlib
import os
import time

from app.users import USERS, verify_password


class InvalidCredentialsError(Exception):
    """Raised when an email/password combination doesn't match a user."""


def authenticate(email: str, password: str) -> int:
    """Check credentials and return the user_id if they're valid."""
    user = USERS.get(email)
    if user is None or not verify_password(password, user["password_hash"]):
        raise InvalidCredentialsError("Invalid email or password.")
    return user["user_id"]


def create_access_token(user_id: int) -> str:
    """
    Build a simple signed token for the given user.

    This is a simplified stand-in for a real JWT (to avoid adding a JWT
    library dependency to a small sample project) — it's a
    timestamp + user_id signed with HMAC-SHA256.
    """
    secret = os.environ["JWT_SECRET_KEY"]
    payload = f"{user_id}:{int(time.time())}"
    signature = hashlib.sha256(f"{payload}:{secret}".encode("utf-8")).hexdigest()
    return f"{payload}:{signature}"
