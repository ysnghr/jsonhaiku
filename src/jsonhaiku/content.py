"""Content-type detection for string values.

Applied as an opt-in pass when ``Config.detect_content_types`` is enabled.
Each heuristic is a cheap regex check, and the first match wins.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from jsonhaiku.nodes import (
    EMAIL_STRING,
    HTML_STRING,
    ISO_DATE,
    ISO_DATETIME,
    JWT_STRING,
    STRING,
    URL_STRING,
    UUID_STRING,
    Primitive,
)

if TYPE_CHECKING:
    from jsonhaiku.nodes import PrimitiveName

__all__ = ["detect_content_type", "make_long_string_meta"]

_HTML_RE = re.compile(r"<[a-z][^>]*>", re.IGNORECASE)
_URL_RE = re.compile(r"^https?://")
_ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"^.+@.+\..+$")
_JWT_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")

_DETECTORS: list[tuple[re.Pattern[str], Primitive]] = [
    (_HTML_RE, HTML_STRING),
    (_URL_RE, URL_STRING),
    (_ISO_DATETIME_RE, ISO_DATETIME),
    (_ISO_DATE_RE, ISO_DATE),
    (_UUID_RE, UUID_STRING),
    (_EMAIL_RE, EMAIL_STRING),
    (_JWT_RE, JWT_STRING),
]


def detect_content_type(value: str) -> PrimitiveName:
    """Return the content-type name for ``value``, or ``"string"`` if none match."""
    for pattern, primitive in _DETECTORS:
        if pattern.search(value):
            return primitive.name
    return "string"


def make_long_string_meta(value: str, *, sample_len: int = 40) -> str:
    """Build the display annotation for a long plain string.

    Returns:
        A string like ``"len≈523, sample: 'The quick brown fox…'"``.
    """
    length = len(value)
    sample = value[:sample_len]
    if len(value) > sample_len:
        sample += "…"
    return f"len≈{length}, sample: '{sample}'"


def classify_string(
    value: str,
    *,
    threshold: int = 200,
    sample_len: int = 40,
) -> Primitive:
    """Classify a string value, returning an annotated Primitive.

    Short strings always become plain ``string``. Long strings are checked
    against content-type patterns; if none match, they get a length-and-sample
    annotation.
    """
    if len(value) <= threshold:
        ct = detect_content_type(value)
        if ct != "string":
            return Primitive(ct)
        return STRING

    ct = detect_content_type(value)
    if ct != "string":
        return Primitive(ct)

    meta = make_long_string_meta(value, sample_len=sample_len)
    return Primitive("string", string_meta=meta)
