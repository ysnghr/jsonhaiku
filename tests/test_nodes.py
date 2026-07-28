"""Tests for the type tree data model and its canonical-ordering invariants."""

from __future__ import annotations

import json

import pytest

from jsonhaiku.nodes import (
    BOOLEAN,
    INTEGER,
    NULL,
    STRING,
    ArrayNode,
    Field,
    Node,
    ObjectNode,
    Primitive,
    UnionNode,
    canonical,
    sort_key,
    to_dict,
)


class TestOrderingInvariants:
    def test_object_fields_are_sorted_on_construction(self) -> None:
        node = ObjectNode({"z": Field(INTEGER), "a": Field(STRING)})
        assert list(node.fields) == ["a", "z"]

    def test_objects_are_equal_regardless_of_source_key_order(self) -> None:
        first = ObjectNode({"a": Field(INTEGER), "b": Field(STRING)})
        second = ObjectNode({"b": Field(STRING), "a": Field(INTEGER)})
        assert first == second

    def test_union_members_are_sorted_on_construction(self) -> None:
        node = UnionNode((STRING, BOOLEAN))
        assert node.members == (BOOLEAN, STRING)

    def test_null_sorts_last(self) -> None:
        node = UnionNode((NULL, STRING))
        assert node.members == (STRING, NULL)

    def test_scalars_sort_before_arrays_and_objects(self) -> None:
        members = (ObjectNode({"a": Field(INTEGER)}), ArrayNode(INTEGER), STRING, NULL)
        assert UnionNode(members).members == (
            STRING,
            ArrayNode(INTEGER),
            ObjectNode({"a": Field(INTEGER)}),
            NULL,
        )

    def test_sort_key_orders_unions_with_objects(self) -> None:
        assert sort_key(UnionNode((INTEGER, STRING)))[0] == 2


class TestImmutability:
    def test_nodes_are_frozen(self) -> None:
        node = ArrayNode(INTEGER)
        with pytest.raises(AttributeError):
            node.items = STRING  # type: ignore[misc]

    def test_object_fields_cannot_be_mutated(self) -> None:
        node = ObjectNode({"a": Field(INTEGER)})
        with pytest.raises(TypeError):
            node.fields["b"] = Field(STRING)  # type: ignore[index]

    def test_mutating_the_source_mapping_does_not_affect_the_node(self) -> None:
        source = {"a": Field(INTEGER)}
        node = ObjectNode(source)
        source["b"] = Field(STRING)
        assert list(node.fields) == ["a"]


class TestCanonical:
    @pytest.mark.parametrize(
        ("node", "expected"),
        [
            (INTEGER, "integer"),
            (ArrayNode(None), "[]"),
            (ArrayNode(STRING), "[string]"),
            (ObjectNode({}), "{}"),
            (ObjectNode({"a": Field(INTEGER)}), "{a:integer}"),
            (ObjectNode({"a": Field(INTEGER, optional=True)}), "{a?:integer}"),
            (UnionNode((STRING, NULL)), "(string|null)"),
        ],
    )
    def test_signature(self, node: Node, expected: str) -> None:
        assert canonical(node) == expected

    def test_distinguishes_optional_from_required_fields(self) -> None:
        required = ObjectNode({"a": Field(INTEGER)})
        optional = ObjectNode({"a": Field(INTEGER, optional=True)})
        assert canonical(required) != canonical(optional)


class TestToDict:
    def test_primitive(self) -> None:
        assert to_dict(Primitive("integer")) == {"kind": "primitive", "type": "integer"}

    def test_empty_array(self) -> None:
        assert to_dict(ArrayNode(None)) == {"kind": "array", "items": None}

    def test_array_of_scalars(self) -> None:
        assert to_dict(ArrayNode(STRING)) == {
            "kind": "array",
            "items": {"kind": "primitive", "type": "string"},
        }

    def test_object_records_optionality(self) -> None:
        node = ObjectNode({"a": Field(INTEGER), "b": Field(STRING, optional=True)})
        assert to_dict(node) == {
            "kind": "object",
            "fields": {
                "a": {"type": {"kind": "primitive", "type": "integer"}, "optional": False},
                "b": {"type": {"kind": "primitive", "type": "string"}, "optional": True},
            },
        }

    def test_union(self) -> None:
        assert to_dict(UnionNode((STRING, NULL))) == {
            "kind": "union",
            "members": [
                {"kind": "primitive", "type": "string"},
                {"kind": "primitive", "type": "null"},
            ],
        }

    def test_output_is_json_serialisable(self) -> None:
        node = ObjectNode({"a": Field(ArrayNode(UnionNode((INTEGER, NULL))))})
        assert json.loads(json.dumps(to_dict(node))) == to_dict(node)
