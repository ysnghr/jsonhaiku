"""Tests for the YAML renderer."""

from __future__ import annotations

from textwrap import dedent

import pytest

from jsonhaiku.core import infer
from jsonhaiku.nodes import (
    INTEGER,
    NULL,
    STRING,
    ArrayNode,
    Field,
    ObjectNode,
    Primitive,
    UnionNode,
)
from jsonhaiku.renderers.yaml import render_yaml


def render(value: object, **kwargs: object) -> str:
    return render_yaml(infer(value), **kwargs)  # type: ignore[arg-type]


class TestScalars:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, "null"),
            (True, "boolean"),
            (1, "integer"),
            (1.5, "float"),
            ("text", "string"),
        ],
    )
    def test_scalar_root(self, value, expected) -> None:
        assert render(value) == expected


class TestObjects:
    def test_flat_object(self) -> None:
        expected = dedent("""\
            active: boolean
            id: integer
            name: string""")
        assert render({"id": 1, "name": "a", "active": True}) == expected

    def test_nested_object(self) -> None:
        result = render({"title": "a", "room": {"id": 1}})
        assert "room:" in result
        assert "  id: integer" in result

    def test_empty_object(self) -> None:
        assert render({}) == "{}"


class TestArrays:
    def test_array_of_scalars(self) -> None:
        assert render(["a", "b"]) == "- string"

    def test_empty_array(self) -> None:
        assert render([]) == "[]"

    def test_array_of_objects(self) -> None:
        result = render([{"id": 1, "name": "a"}])
        assert "- id: integer" in result
        assert "  name: string" in result


class TestOptionalFields:
    def test_optional_field_has_question_mark(self) -> None:
        result = render([{"id": 1, "name": "a"}, {"id": 2}])
        assert "name?:" in result
        assert "id:" in result


class TestUnions:
    def test_nullable_scalar(self) -> None:
        result = render_yaml(UnionNode((STRING, NULL)))
        assert result == "string | null"

    def test_union_of_scalars(self) -> None:
        result = render([1, "a", None])
        assert "integer | string | null" in result


class TestMaxDepth:
    def test_depth_truncation(self) -> None:
        data = {"a": {"b": {"c": 1}}}
        result = render(data, max_depth=1)
        assert "..." in result


class TestContentTypes:
    def test_content_type_primitive(self) -> None:
        result = render_yaml(Primitive("html_string"))
        assert result == "html_string"

    def test_long_string_meta(self) -> None:
        node = Primitive("string", string_meta="len≈500, sample: 'hello…'")
        result = render_yaml(node)
        assert "len≈500" in result


class TestStructuralUnions:
    def test_nullable_object(self) -> None:
        node = UnionNode((ObjectNode({"id": Field(INTEGER)}), NULL))
        result = render_yaml(node)
        assert "null" in result

    def test_object_and_scalar(self) -> None:
        node = UnionNode((STRING, ObjectNode({"a": Field(INTEGER)})))
        result = render_yaml(node)
        assert "string" in result

    def test_structural_union_in_field(self) -> None:
        node = ObjectNode({
            "x": Field(UnionNode((ObjectNode({"a": Field(INTEGER)}), STRING))),
        })
        result = render_yaml(node)
        assert "string" in result
        assert "integer" in result

    def test_array_in_union(self) -> None:
        node = ObjectNode({
            "x": Field(UnionNode((ArrayNode(INTEGER), NULL))),
        })
        result = render_yaml(node)
        assert "null" in result


class TestSpecialKeys:
    def test_key_with_colon(self) -> None:
        result = render({"a:b": 1})
        assert '"a:b"' in result

    def test_key_with_hash(self) -> None:
        result = render({"a#b": 1})
        assert '"a#b"' in result

    def test_key_starting_with_dash(self) -> None:
        result = render({"-key": 1})
        assert '"-key"' in result


class TestDeterminism:
    def test_repeated_rendering_is_byte_identical(self) -> None:
        value = {"b": [1, None], "a": {"z": True, "y": "x"}}
        first = render(value)
        assert all(render(value) == first for _ in range(100))
