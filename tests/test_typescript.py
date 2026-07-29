"""Tests for the TypeScript renderer."""

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
from jsonhaiku.renderers.typescript import render_typescript


def render(value: object, **kwargs: object) -> str:
    return render_typescript(infer(value), **kwargs)  # type: ignore[arg-type]


class TestScalars:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, "type Root = null;"),
            (True, "type Root = boolean;"),
            (1, "type Root = number;"),
            (1.5, "type Root = number;"),
            ("text", "type Root = string;"),
        ],
    )
    def test_scalar_root(self, value, expected) -> None:
        assert render(value) == expected

    def test_custom_root_name(self) -> None:
        assert render(1, root_name="MyType") == "type MyType = number;"


class TestObjects:
    def test_flat_object(self) -> None:
        expected = dedent("""\
            interface Root {
              active: boolean;
              id: number;
              name: string;
            }""")
        assert render({"id": 1, "name": "a", "active": True}) == expected

    def test_nested_object(self) -> None:
        result = render({"title": "a", "room": {"id": 1, "name": "x"}})
        assert "interface Root {" in result
        assert "room:" in result
        assert "id: number;" in result

    def test_empty_object(self) -> None:
        assert render({}) == "interface Root {}"

    def test_custom_interface_name(self) -> None:
        result = render({"id": 1}, root_name="Session")
        assert result.startswith("interface Session {")

    def test_reserved_keyword_key_is_quoted(self) -> None:
        result = render({"class": "a"})
        assert '"class"' in result

    def test_special_chars_key_is_quoted(self) -> None:
        result = render({"my-key": 1})
        assert '"my-key"' in result


class TestArrays:
    def test_array_of_scalars(self) -> None:
        assert render(["a", "b"]) == "type Root = string[];"

    def test_empty_array(self) -> None:
        assert render([]) == "type Root = unknown[];"

    def test_array_of_objects(self) -> None:
        result = render([{"id": 1, "name": "a"}])
        assert "id: number;" in result

    def test_nullable_array_elements_get_parens(self) -> None:
        result = render_typescript(ArrayNode(UnionNode((STRING, NULL))))
        assert "(string | null)[]" in result


class TestOptionalFields:
    def test_optional_field(self) -> None:
        result = render([{"id": 1, "name": "a"}, {"id": 2}])
        assert "name?: string;" in result
        assert "id: number;" in result


class TestUnions:
    def test_nullable_scalar(self) -> None:
        result = render([1, None])
        assert "number | null" in result

    def test_object_and_scalar(self) -> None:
        result = render_typescript(
            UnionNode((STRING, ObjectNode({"a": Field(INTEGER)})))
        )
        assert "string |" in result


class TestMaxDepth:
    def test_depth_truncation(self) -> None:
        data = {"a": {"b": {"c": 1}}}
        result = render(data, max_depth=1)
        assert "Record<string, unknown>" in result


class TestContentTypeComments:
    def test_html_string_comment(self) -> None:
        node = ObjectNode({"bio": Field(Primitive("html_string"))})
        result = render_typescript(node)
        assert "// html" in result

    def test_url_string_comment(self) -> None:
        node = ObjectNode({"link": Field(Primitive("url_string"))})
        result = render_typescript(node)
        assert "// url" in result


class TestInlineObjects:
    def test_empty_inline_object(self) -> None:
        node = ArrayNode(ObjectNode({}))
        result = render_typescript(node)
        assert "{}[]" in result

    def test_nested_inline_objects(self) -> None:
        node = ObjectNode({
            "a": Field(ObjectNode({"b": Field(ObjectNode({"c": Field(INTEGER)}))})),
        })
        result = render_typescript(node)
        assert "c: number;" in result


class TestScalarRoot:
    def test_scalar_type_alias(self) -> None:
        result = render_typescript(STRING)
        assert result == "type Root = string;"


class TestInlineContentTypeComments:
    def test_content_type_in_nested_inline(self) -> None:
        node = ArrayNode(ObjectNode({
            "bio": Field(Primitive("html_string")),
        }))
        result = render_typescript(node)
        assert "// html" in result

    def test_union_content_type_comment(self) -> None:
        node = ObjectNode({
            "value": Field(UnionNode((Primitive("html_string"), NULL))),
        })
        result = render_typescript(node)
        assert "// html" in result


class TestDeterminism:
    def test_repeated_rendering_is_byte_identical(self) -> None:
        value = {"b": [1, None], "a": {"z": True, "y": "x"}}
        first = render(value)
        assert all(render(value) == first for _ in range(100))
