"""Tests for max_depth truncation across all renderers."""

from __future__ import annotations

from jsonhaiku.core import infer
from jsonhaiku.renderers.compact import render_compact
from jsonhaiku.renderers.json_schema import render_json_schema
from jsonhaiku.renderers.typescript import render_typescript
from jsonhaiku.renderers.yaml import render_yaml

NESTED = {"level1": {"level2": {"level3": {"leaf": 1}}}}


class TestCompactDepth:
    def test_no_limit(self) -> None:
        result = render_compact(infer(NESTED))
        assert "leaf" in result

    def test_depth_0_truncates_root(self) -> None:
        result = render_compact(infer(NESTED), max_depth=0)
        assert "..." in result
        assert "leaf" not in result

    def test_depth_1_shows_level1(self) -> None:
        result = render_compact(infer(NESTED), max_depth=1)
        assert '"level1"' in result
        assert "..." in result

    def test_depth_2(self) -> None:
        result = render_compact(infer(NESTED), max_depth=2)
        assert '"level2"' in result
        assert "..." in result

    def test_summary_includes_field_count(self) -> None:
        data = {"a": {"x": 1, "y": 2, "z": 3}}
        result = render_compact(infer(data), max_depth=1)
        assert "3 fields" in result


class TestTypescriptDepth:
    def test_depth_truncation(self) -> None:
        result = render_typescript(infer(NESTED), max_depth=1)
        assert "Record<string, unknown>" in result
        assert "leaf" not in result


class TestJsonSchemaDepth:
    def test_depth_truncation_produces_empty_object(self) -> None:
        result = render_json_schema(infer(NESTED), max_depth=1)
        level1_schema = result["properties"]["level1"]
        assert level1_schema == {"type": "object"}

    def test_no_limit_includes_all(self) -> None:
        result = render_json_schema(infer(NESTED))
        deep = result["properties"]["level1"]["properties"]["level2"]
        assert "properties" in deep


class TestYamlDepth:
    def test_depth_truncation(self) -> None:
        result = render_yaml(infer(NESTED), max_depth=1)
        assert "..." in result
        assert "leaf" not in result
