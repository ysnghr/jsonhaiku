"""Opt-in PII redaction for sample values.

Replaces values that look like PII (emails, phone numbers) and fields with
sensitive-sounding names (password, token, secret, etc.) with safe placeholders.
"""

from __future__ import annotations

import copy
import re

__all__ = ["redact"]

_SENSITIVE_FIELD_NAMES = frozenset(
    {
        "password",
        "token",
        "secret",
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "private_key",
        "secret_key",
    }
)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_PHONE_RE = re.compile(r"^[\+]?[\d\s\-\(\)]{7,20}$")

_REDACTED = "<redacted>"
_REDACTED_EMAIL = "user@example.com"
_REDACTED_PHONE = "+1-555-0100"


def redact(value: object) -> object:
    """Return a deep copy of *value* with PII-like content replaced."""
    return _redact_value(copy.deepcopy(value), parent_key=None)


def _redact_value(value: object, *, parent_key: str | None) -> object:
    if isinstance(value, dict):
        return {k: _redact_value(v, parent_key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, parent_key=parent_key) for item in value]
    if isinstance(value, str):
        return _redact_string(value, parent_key)
    return value


def _redact_string(value: str, parent_key: str | None) -> str:
    if parent_key is not None and parent_key.lower() in _SENSITIVE_FIELD_NAMES:
        return _REDACTED
    if _EMAIL_RE.match(value):
        return _REDACTED_EMAIL
    if _PHONE_RE.match(value) and any(c.isdigit() for c in value):
        return _REDACTED_PHONE
    return value
