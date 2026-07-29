"""Tests for max_depth truncation across all renderers."""

from __future__ import annotations

from jsonhaiku.core import infer
from jsonhaiku.nodes import (
    INTEGER,
    NULL,
    STRING,
    ArrayNode,
    Field,
    ObjectNode,
    UnionNode,
)
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

    def test_summary_with_array_subtree(self) -> None:
        data = {"items": {"list": [{"deep": 1}]}}
        result = render_compact(infer(data), max_depth=1)
        assert "..." in result

    def test_summary_with_union_subtree(self) -> None:
        node = ObjectNode(
            {
                "x": Field(
                    ObjectNode(
                        {
                            "a": Field(UnionNode((INTEGER, ObjectNode({"deep": Field(STRING)})))),
                        }
                    )
                ),
            }
        )
        result = render_compact(node, max_depth=1)
        assert "..." in result

    def test_summary_with_empty_object(self) -> None:
        data: dict[str, object] = {"wrapper": {"empty": {}}}
        result = render_compact(infer(data), max_depth=1)
        assert "..." in result


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


class TestJsonSchemaDepthFull:
    def test_scalar_at_depth(self) -> None:
        result = render_json_schema(infer({"x": 1}), max_depth=5)
        assert result["properties"]["x"] == {"type": "integer"}

    def test_array_at_depth(self) -> None:
        result = render_json_schema(infer({"items": [1]}), max_depth=5)
        assert result["properties"]["items"]["items"] == {"type": "integer"}

    def test_empty_array_at_depth(self) -> None:
        result = render_json_schema(infer({"items": []}), max_depth=5)
        assert result["properties"]["items"] == {"type": "array"}

    def test_union_scalar_at_depth(self) -> None:
        node = ObjectNode({"x": Field(UnionNode((STRING, NULL)))})
        result = render_json_schema(node, max_depth=5)
        assert result["properties"]["x"]["type"] == ["string", "null"]

    def test_union_structural_at_depth(self) -> None:
        node = ObjectNode(
            {
                "x": Field(UnionNode((STRING, ObjectNode({"a": Field(INTEGER)})))),
            }
        )
        result = render_json_schema(node, max_depth=5)
        assert "anyOf" in result["properties"]["x"]

    def test_empty_object_at_depth(self) -> None:
        node = ObjectNode({"x": Field(ObjectNode({}))})
        result = render_json_schema(node, max_depth=5)
        assert result["properties"]["x"] == {"type": "object"}

    def test_required_fields_at_depth(self) -> None:
        result = render_json_schema(infer({"a": 1, "b": 2}), max_depth=5)
        assert "required" in result
        assert sorted(result["required"]) == ["a", "b"]

    def test_optional_fields_not_required(self) -> None:
        node = ObjectNode({"a": Field(INTEGER, optional=True)})
        result = render_json_schema(node, max_depth=5)
        assert "required" not in result


class TestYamlDepth:
    def test_depth_truncation(self) -> None:
        result = render_yaml(infer(NESTED), max_depth=1)
        assert "..." in result
        assert "leaf" not in result
