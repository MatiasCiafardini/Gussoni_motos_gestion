"""Utilities for hashing and verifying user passwords."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional


def hash_password(password: Optional[str]) -> str:
    """Return a salted SHA-256 hash in the format ``salt$hash``.

    The function mirrors the hashing scheme already used across the
    application to keep backwards compatibility with stored credentials.
    ``password`` may be ``None`` or empty; in that case an empty string is
    treated as the password value when hashing.
    """

    salt = os.urandom(16).hex()
    digest = hashlib.sha256((salt + (password or "")).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """Validate ``password`` against the stored ``salt$hash`` string."""

    if not stored:
        return False
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False

    candidate = hashlib.sha256((salt + (password or "")).encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, digest)

