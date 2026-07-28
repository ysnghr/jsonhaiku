"""Tests for the compact renderer.

The expected strings are written out in full rather than computed: this file is
the readable specification of the output format, and a diff here should be
obvious to a human reviewer.
"""

from __future__ import annotations

from textwrap import dedent

import pytest

from jsonhaiku.core import infer
from jsonhaiku.nodes import INTEGER, NULL, STRING, ArrayNode, Field, ObjectNode, UnionNode
from jsonhaiku.render import render_compact


def render(value: object) -> str:
    """Infer and render a JSON value in one step."""
    return render_compact(infer(value))


class TestScalars:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, '"null"'),
            (True, '"boolean"'),
            (1, '"integer"'),
            (1.5, '"float"'),
            ("text", '"string"'),
        ],
    )
    def test_scalar_root(self, value: object, expected: str) -> None:
        assert render(value) == expected

    def test_nullable_scalar_puts_null_last(self) -> None:
        assert render_compact(UnionNode((NULL, STRING))) == '"string | null"'

    def test_union_of_scalars(self) -> None:
        assert render([1, "a", None]) == '["integer | string | null"]'

    def test_mixed_numbers_render_as_number(self) -> None:
        assert render([1, 1.5]) == '["number"]'


class TestEmptyContainers:
    def test_empty_object(self) -> None:
        assert render({}) == "{}"

    def test_empty_array(self) -> None:
        assert render([]) == "[]"

    def test_empty_containers_inside_an_object(self) -> None:
        expected = dedent("""\
            {
              "children": [],
              "meta": {}
            }""")
        assert render({"children": [], "meta": {}}) == expected


class TestObjects:
    def test_flat_object(self) -> None:
        expected = dedent("""\
            {
              "active": "boolean",
              "id": "integer",
              "name": "string"
            }""")
        assert render({"id": 1, "name": "a", "active": True}) == expected

    def test_keys_are_sorted_so_source_order_cannot_change_the_output(self) -> None:
        assert render({"b": 1, "a": 1}) == render({"a": 1, "b": 1})

    def test_nested_object(self) -> None:
        expected = dedent("""\
            {
              "room": {
                "id": "integer",
                "name": "string"
              },
              "title": "string"
            }""")
        assert render({"title": "a", "room": {"id": 1, "name": "HALL A"}}) == expected

    def test_keys_are_escaped(self) -> None:
        assert render({'say "hi"': 1}) == '{\n  "say \\"hi\\"": "integer"\n}'

    def test_non_ascii_keys_stay_readable(self) -> None:
        assert render({"türkçe": 1}) == '{\n  "türkçe": "integer"\n}'


class TestArrays:
    def test_array_of_scalars(self) -> None:
        assert render(["a", "b"]) == '["string"]'

    def test_nested_arrays(self) -> None:
        assert render([[1]]) == '[["integer"]]'

    def test_array_of_objects(self) -> None:
        expected = dedent("""\
            [{
              "id": "integer",
              "name": "string | null"
            }]""")
        assert render([{"id": 1, "name": "a"}, {"id": 2, "name": None}]) == expected

    def test_array_of_arrays_of_objects(self) -> None:
        expected = dedent("""\
            [[{
              "id": "integer"
            }]]""")
        assert render([[{"id": 1}]]) == expected


class TestOptionalFields:
    def test_scalar_field_missing_from_some_observations(self) -> None:
        expected = dedent("""\
            [{
              "id": "integer",
              "name": "string | undefined"
            }]""")
        assert render([{"id": 1, "name": "a"}, {"id": 2}]) == expected

    def test_nullable_and_optional_are_distinct(self) -> None:
        nullable = render([{"name": "a"}, {"name": None}])
        optional = render([{"name": "a"}, {}])
        assert '"string | null"' in nullable
        assert '"string | undefined"' in optional

    def test_object_field_missing_from_some_observations(self) -> None:
        expected = dedent("""\
            [{
              "room": {
                "id": "integer"
              } | undefined
            }]""")
        assert render([{"room": {"id": 1}}, {}]) == expected


class TestUnionsWithStructure:
    """Objects at the same path merge; genuinely different kinds become unions.

    Two objects with different keys are one shape with optional fields, not two
    shapes — that is what real record arrays look like. A union only appears when
    the *kind* differs: object versus scalar, object versus array, and so on.
    """

    def test_objects_with_different_keys_merge_into_one_shape(self) -> None:
        expected = dedent("""\
            [{
              "code": "integer | undefined",
              "kind": "string | undefined",
              "value": "integer | undefined"
            }]""")
        assert render([{"kind": "a", "value": 1}, {"code": 2}]) == expected

    def test_nullable_object(self) -> None:
        assert render([{"id": 1}, None]) == '[{"id": "integer"} | null]'

    def test_object_and_scalar(self) -> None:
        assert render([{"id": 1}, "a"]) == '[string | {"id": "integer"}]'

    def test_object_and_array(self) -> None:
        assert render([{"id": 1}, [1]]) == '[["integer"] | {"id": "integer"}]'

    def test_optional_field_inside_an_inline_object(self) -> None:
        node = UnionNode(
            (
                ObjectNode({"a": Field(INTEGER, optional=True)}),
                ObjectNode({"b": Field(STRING)}),
            )
        )
        assert render_compact(node) == '{"a": "integer | undefined"} | {"b": "string"}'

    def test_array_of_unknown_elements_inside_a_union(self) -> None:
        node = UnionNode((ArrayNode(None), ObjectNode({"a": Field(INTEGER)})))
        assert render_compact(node) == '[] | {"a": "integer"}'

    def test_empty_object_inside_a_union(self) -> None:
        node = UnionNode((STRING, ObjectNode({})))
        assert render_compact(node) == "string | {}"


class TestDeterminism:
    def test_repeated_rendering_is_byte_identical(self) -> None:
        value = {"b": [1, None], "a": {"z": True, "y": "x"}}
        first = render(value)
        assert all(render(value) == first for _ in range(100))
