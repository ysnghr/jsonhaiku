"""Tests for JSON Schema rendering.

Beyond checking the shape of the output, these tests validate the *source data*
against the *generated schema* with a real validator. That is the only assertion
that proves the schema is not merely plausible.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from jsonhaiku.core import UnsupportedValueWarning, infer
from jsonhaiku.nodes import (
    INTEGER,
    NULL,
    STRING,
    UNKNOWN,
    ArrayNode,
    Field,
    ObjectNode,
    UnionNode,
)
from jsonhaiku.schema import SCHEMA_DIALECT, to_json_schema

PAYLOADS: list[object] = [
    None,
    True,
    42,
    3.5,
    "text",
    [],
    {},
    [1, 2, 3],
    [1, 1.5],
    [1, "two", None],
    {"id": 1, "tags": ["a"], "meta": {}},
    [{"id": 1, "name": "a"}, {"id": 2, "name": None}],
    [{"id": 1}, {"id": 2, "extra": True}],
    [{"id": 1}, None],
    [{"id": 1}, "scalar"],
    [[{"deep": [1]}]],
]


def schema_of(value: object) -> dict[str, Any]:
    """Infer and render a JSON value as a schema in one step."""
    return to_json_schema(infer(value))


class TestDocument:
    def test_declares_the_dialect(self) -> None:
        assert schema_of(1)["$schema"] == SCHEMA_DIALECT

    def test_result_is_a_fresh_mutable_dict(self) -> None:
        schema = schema_of(1)
        schema["title"] = "Mine"
        assert "title" not in schema_of(1)

    def test_is_itself_a_valid_schema(self) -> None:
        Draft202012Validator.check_schema(schema_of(PAYLOADS[-1]))


class TestScalars:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, "null"),
            (True, "boolean"),
            (1, "integer"),
            (1.5, "number"),
            ("a", "string"),
        ],
    )
    def test_scalar_types(self, value: object, expected: str) -> None:
        assert schema_of(value)["type"] == expected

    def test_unknown_becomes_an_empty_schema(self) -> None:
        with pytest.warns(UnsupportedValueWarning, match="Decimal"):
            schema = schema_of(Decimal(1))
        assert schema == {"$schema": SCHEMA_DIALECT}


class TestArrays:
    def test_array_of_unknown_elements_omits_items(self) -> None:
        assert schema_of([]) == {"$schema": SCHEMA_DIALECT, "type": "array"}

    def test_array_items(self) -> None:
        assert schema_of([1])["items"] == {"type": "integer"}


class TestObjects:
    def test_empty_object_has_no_properties(self) -> None:
        assert schema_of({}) == {"$schema": SCHEMA_DIALECT, "type": "object"}

    def test_properties_and_required(self) -> None:
        schema = schema_of({"id": 1, "name": "a"})
        assert schema["properties"] == {"id": {"type": "integer"}, "name": {"type": "string"}}
        assert schema["required"] == ["id", "name"]

    def test_optional_fields_are_not_required(self) -> None:
        schema = schema_of([{"id": 1, "name": "a"}, {"id": 2}])["items"]
        assert schema["required"] == ["id"]
        assert "name" in schema["properties"]

    def test_object_with_only_optional_fields_omits_required(self) -> None:
        node = ObjectNode({"a": Field(INTEGER, optional=True)})
        assert "required" not in to_json_schema(node)


class TestUnions:
    def test_scalar_union_uses_a_type_list(self) -> None:
        assert to_json_schema(UnionNode((STRING, NULL)))["type"] == ["string", "null"]

    def test_structural_union_uses_any_of(self) -> None:
        node = UnionNode((STRING, ObjectNode({"a": Field(INTEGER)})))
        assert to_json_schema(node)["anyOf"] == [
            {"type": "string"},
            {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]},
        ]

    def test_union_containing_unknown_falls_back_to_any_of(self) -> None:
        node = UnionNode((STRING, UNKNOWN))
        assert to_json_schema(node)["anyOf"] == [{"type": "string"}, {}]

    def test_array_element_union(self) -> None:
        assert to_json_schema(ArrayNode(UnionNode((INTEGER, NULL))))["items"] == {
            "type": ["integer", "null"]
        }


class TestGeneratedSchemasValidateTheirSource:
    @pytest.mark.parametrize("payload", PAYLOADS, ids=repr)
    def test_source_data_validates(self, payload: object) -> None:
        Draft202012Validator(schema_of(payload)).validate(payload)

    def test_a_missing_required_key_is_rejected(self) -> None:
        # Proves "required" is doing real work, not decorating the output.
        validator = Draft202012Validator(schema_of({"id": 1}))
        assert not validator.is_valid({})
