"""Tests for Config and its integration with describe()."""

from __future__ import annotations

import pytest

from jsonhaiku import Config, describe
from jsonhaiku.core import _merge_string_meta, merge, union_of
from jsonhaiku.nodes import INTEGER, STRING, Primitive, UnionNode


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

    def test_long_string_meta_merge(self) -> None:
        data = [
            {"desc": "a" * 300},
            {"desc": "b" * 400},
        ]
        result = describe(data, config=Config(detect_content_types=True))
        assert "len≈300" in result.compact

    def test_long_string_meta_first_has_none(self) -> None:
        assert _merge_string_meta(None, "len≈300") == "len≈300"
        assert _merge_string_meta("len≈200", None) == "len≈200"
        assert _merge_string_meta(None, None) is None

    def test_merge_plain_string_with_long_string(self) -> None:
        plain = Primitive("string")
        long = Primitive("string", string_meta="len≈300, sample: 'aaa…'")
        result = merge(plain, long)
        assert isinstance(result, Primitive)
        assert result.string_meta == "len≈300, sample: 'aaa…'"

    def test_content_type_in_union_collapses(self) -> None:
        data = [
            "https://example.com",
            "<p>html</p>",
            "plain text",
        ]
        result = describe(data, config=Config(detect_content_types=True))
        assert "url_string" not in result.compact
        assert "html_string" not in result.compact

    def test_collapse_string_subtypes_in_union_of(self) -> None:
        html = Primitive("html_string")
        url = Primitive("url_string")
        result = union_of((html, url, INTEGER))
        assert result == UnionNode((INTEGER, STRING))

    def test_collapse_string_subtypes_single_type(self) -> None:
        html = Primitive("html_string")
        result = union_of((html, INTEGER))
        assert isinstance(result, UnionNode)
        assert any(
            isinstance(m, Primitive) and m.name == "html_string"
            for m in result.members
        )
