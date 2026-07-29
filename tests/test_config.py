"""Tests for Config and its integration with describe()."""

from __future__ import annotations

import pytest

from jsonhaiku import Config, describe


class TestConfig:
    def test_defaults(self) -> None:
        cfg = Config()
        assert cfg.detect_content_types is False
        assert cfg.long_string_threshold == 200
        assert cfg.long_string_sample_len == 40
        assert cfg.max_depth is None

    def test_frozen(self) -> None:
        cfg = Config()
        with pytest.raises(AttributeError):
            cfg.detect_content_types = True  # type: ignore[misc]


class TestDescribeWithConfig:
    def test_describe_without_config(self) -> None:
        result = describe({"id": 1})
        assert "integer" in result.compact

    def test_describe_with_empty_config(self) -> None:
        result = describe({"id": 1}, config=Config())
        assert "integer" in result.compact

    def test_detect_content_types(self) -> None:
        data = {"url": "https://example.com", "name": "test"}
        result = describe(data, config=Config(detect_content_types=True))
        assert "url_string" in result.compact

    def test_content_types_off_by_default(self) -> None:
        data = {"url": "https://example.com"}
        result = describe(data)
        assert "url_string" not in result.compact
        assert '"string"' in result.compact

    def test_max_depth(self) -> None:
        data = {"a": {"b": {"c": 1}}}
        result = describe(data, config=Config(max_depth=1))
        assert "..." in result.compact

    def test_long_string_detection(self) -> None:
        data = {"desc": "a" * 300}
        result = describe(data, config=Config(detect_content_types=True))
        assert "len≈300" in result.compact

    def test_html_detection_in_array(self) -> None:
        data = [
            {"bio": "<p>Hello world</p>"},
            {"bio": "<p>Another bio</p>"},
        ]
        result = describe(data, config=Config(detect_content_types=True))
        assert "html_string" in result.compact

    def test_mixed_content_types_collapse_to_string(self) -> None:
        data = [
            {"value": "https://example.com"},
            {"value": "<p>hello</p>"},
        ]
        result = describe(data, config=Config(detect_content_types=True))
        assert '"string"' in result.compact
        assert "url_string" not in result.compact
        assert "html_string" not in result.compact
