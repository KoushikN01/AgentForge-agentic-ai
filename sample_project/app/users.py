"""
A tiny fake user store, in place of a real database.

Passwords are hashed with plain SHA-256 here purely to keep this sample
project's dependency list small (no passlib/bcrypt) — this is NOT how you
should hash passwords in a real application. That's a deliberate
simplification for a learning sandbox, not a bug for AgentForge to find.
"""

import hashlib


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return _hash_password(password) == password_hash


USERS = {
    "alice@example.com": {
        "user_id": 1,
        "password_hash": _hash_password("wonderland123"),
    },
    "bob@example.com": {
        "user_id": 2,
        "password_hash": _hash_password("builder456"),
    },
}
