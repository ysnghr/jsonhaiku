"""Tests for content-type detection."""

from __future__ import annotations

import pytest

from jsonhaiku.content import classify_string, detect_content_type, make_long_string_meta
from jsonhaiku.nodes import STRING, Primitive

_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0"
    ".Gfx6VO9tcxwk6xqx9yYzSfebfeakZp5JYIgP_edcw_A"
)


def _jwt_sample() -> str:
    return _JWT


class TestDetectContentType:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("<p>Hello</p>", "html_string"),
            ("<div class='x'>content</div>", "html_string"),
            ("https://example.com", "url_string"),
            ("http://localhost:3000/api", "url_string"),
            ("2024-03-15", "iso_date"),
            ("2024-03-15T10:30:00Z", "iso_datetime"),
            ("550e8400-e29b-41d4-a716-446655440000", "uuid_string"),
            ("user@example.com", "email_string"),
            (_jwt_sample(), "jwt_string"),
        ],
    )
    def test_positive_detection(self, value: str, expected: str) -> None:
        assert detect_content_type(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "just a regular string",
            "12345",
            "not-a-date",
            "almost@but",
            "two.segments.only",
        ],
    )
    def test_negative_detection(self, value: str) -> None:
        assert detect_content_type(value) == "string"


class TestMakeLongStringMeta:
    def test_basic_meta(self) -> None:
        value = "x" * 523
        meta = make_long_string_meta(value)
        assert "len≈523" in meta
        assert "sample:" in meta

    def test_truncation_at_sample_len(self) -> None:
        value = "abcdefghij" * 10
        meta = make_long_string_meta(value, sample_len=10)
        assert "sample: 'abcdefghij…'" in meta

    def test_short_string_no_ellipsis(self) -> None:
        meta = make_long_string_meta("short", sample_len=40)
        assert "…" not in meta


class TestClassifyString:
    def test_short_plain_string(self) -> None:
        assert classify_string("hello", threshold=200) == STRING

    def test_short_html_string(self) -> None:
        result = classify_string("<p>hello</p>", threshold=200)
        assert result == Primitive("html_string")

    def test_long_plain_string(self) -> None:
        value = "a" * 300
        result = classify_string(value, threshold=200)
        assert result.name == "string"
        assert result.string_meta is not None
        assert "len≈300" in result.string_meta

    def test_long_html_string(self) -> None:
        value = "<div>" + "x" * 300 + "</div>"
        result = classify_string(value, threshold=200)
        assert result == Primitive("html_string")

    def test_custom_sample_len(self) -> None:
        value = "a" * 300
        result = classify_string(value, threshold=200, sample_len=5)
        assert result.string_meta is not None
        assert "aaaaa…" in result.string_meta
