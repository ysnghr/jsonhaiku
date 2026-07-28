"""Tests for type inference and observation merging."""

from __future__ import annotations

from decimal import Decimal

import pytest

from jsonhaiku.core import (
    UnsupportedValueWarning,
    infer,
    merge,
    merge_all,
    union_of,
)
from jsonhaiku.nodes import (
    BOOLEAN,
    FLOAT,
    INTEGER,
    NULL,
    NUMBER,
    STRING,
    UNKNOWN,
    ArrayNode,
    Field,
    Node,
    ObjectNode,
    UnionNode,
)


class TestPrimitives:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, NULL),
            (True, BOOLEAN),
            (False, BOOLEAN),
            (0, INTEGER),
            (42, INTEGER),
            (-7, INTEGER),
            (3.14, FLOAT),
            (0.0, FLOAT),
            ("", STRING),
            ("hello", STRING),
        ],
    )
    def test_scalar_inference(self, value: object, expected: Node) -> None:
        assert infer(value) == expected

    def test_bool_is_not_reported_as_integer(self) -> None:
        # isinstance(True, int) is True in Python; the check order must reflect that.
        assert infer(True) is not INTEGER
        assert infer(True) == BOOLEAN


class TestUnsupportedValues:
    def test_warns_and_emits_unknown(self) -> None:
        with pytest.warns(UnsupportedValueWarning, match="Decimal"):
            assert infer(Decimal("1.5")) == UNKNOWN

    def test_warns_for_nested_unsupported_values(self) -> None:
        with pytest.warns(UnsupportedValueWarning):
            tree = infer({"amount": {1, 2}})
        assert tree == ObjectNode({"amount": Field(UNKNOWN)})


class TestArrays:
    def test_empty_array_has_unknown_element_type(self) -> None:
        assert infer([]) == ArrayNode(None)

    def test_homogeneous_array(self) -> None:
        assert infer([1, 2, 3]) == ArrayNode(INTEGER)

    def test_heterogeneous_array_becomes_a_union(self) -> None:
        assert infer([1, "two"]) == ArrayNode(UnionNode((INTEGER, STRING)))

    def test_nullable_element_type(self) -> None:
        assert infer([1, None]) == ArrayNode(UnionNode((INTEGER, NULL)))

    def test_nested_arrays(self) -> None:
        assert infer([[1], [2]]) == ArrayNode(ArrayNode(INTEGER))

    def test_tuples_are_arrays(self) -> None:
        # json.dumps serialises tuples as arrays, so jsonhaiku describes them as such.
        assert infer((1, 2)) == infer([1, 2])

    @pytest.mark.parametrize("value", [[[], [1]], [[1], []]])
    def test_empty_array_observation_adds_no_information(self, value: object) -> None:
        assert infer(value) == ArrayNode(ArrayNode(INTEGER))

    def test_array_of_objects_merges_shapes(self) -> None:
        tree = infer([{"id": 1}, {"id": 2, "name": "a"}])
        assert tree == ArrayNode(
            ObjectNode({"id": Field(INTEGER), "name": Field(STRING, optional=True)})
        )


class TestObjects:
    def test_empty_object(self) -> None:
        assert infer({}) == ObjectNode({})

    def test_flat_object(self) -> None:
        assert infer({"id": 1, "active": True}) == ObjectNode(
            {"id": Field(INTEGER), "active": Field(BOOLEAN)}
        )

    def test_nested_object(self) -> None:
        assert infer({"room": {"id": 1}}) == ObjectNode(
            {"room": Field(ObjectNode({"id": Field(INTEGER)}))}
        )

    def test_non_string_keys_are_stringified(self) -> None:
        assert infer({1: "a"}) == ObjectNode({"1": Field(STRING)})


class TestNumericMerging:
    def test_integer_and_float_collapse_to_number(self) -> None:
        assert merge(INTEGER, FLOAT) == NUMBER

    def test_number_absorbs_integer(self) -> None:
        assert merge(NUMBER, INTEGER) == NUMBER

    def test_numeric_collapse_inside_a_larger_union(self) -> None:
        assert union_of((INTEGER, FLOAT, STRING)) == UnionNode((NUMBER, STRING))

    def test_boolean_does_not_merge_with_integer(self) -> None:
        assert merge(BOOLEAN, INTEGER) == UnionNode((BOOLEAN, INTEGER))

    def test_inferred_from_data(self) -> None:
        assert infer([1, 1.5]) == ArrayNode(NUMBER)


class TestUnions:
    def test_single_member_union_collapses(self) -> None:
        assert union_of((STRING,)) == STRING

    def test_duplicates_are_removed(self) -> None:
        assert union_of((STRING, STRING)) == STRING

    def test_nested_unions_are_flattened(self) -> None:
        nested = UnionNode((INTEGER, STRING))
        assert union_of((nested, NULL)) == UnionNode((INTEGER, STRING, NULL))

    def test_structurally_equal_objects_are_deduplicated(self) -> None:
        left = ObjectNode({"a": Field(INTEGER)})
        right = ObjectNode({"a": Field(INTEGER)})
        assert union_of((left, right)) == left


class TestMerge:
    def test_is_idempotent(self) -> None:
        node = ObjectNode({"a": Field(INTEGER)})
        assert merge(node, node) == node

    def test_is_commutative(self) -> None:
        left = ObjectNode({"a": Field(INTEGER)})
        right = ObjectNode({"b": Field(STRING)})
        assert merge(left, right) == merge(right, left)

    def test_object_and_scalar_become_a_union(self) -> None:
        obj = ObjectNode({"a": Field(INTEGER)})
        assert merge(obj, STRING) == UnionNode((STRING, obj))

    def test_arrays_merge_element_types(self) -> None:
        assert merge(ArrayNode(INTEGER), ArrayNode(STRING)) == ArrayNode(
            UnionNode((INTEGER, STRING))
        )

    def test_shared_optional_field_stays_optional(self) -> None:
        left = ObjectNode({"a": Field(INTEGER, optional=True)})
        right = ObjectNode({"a": Field(INTEGER)})
        assert merge(left, right) == ObjectNode({"a": Field(INTEGER, optional=True)})

    def test_deeply_merged_shapes(self) -> None:
        tree = infer([{"a": {"b": 1}}, {"a": {"b": None, "c": 2}}])
        assert tree == ArrayNode(
            ObjectNode(
                {
                    "a": Field(
                        ObjectNode(
                            {
                                "b": Field(UnionNode((INTEGER, NULL))),
                                "c": Field(INTEGER, optional=True),
                            }
                        )
                    )
                }
            )
        )


class TestMergeAll:
    def test_folds_many_observations(self) -> None:
        assert merge_all([INTEGER, FLOAT, NULL]) == UnionNode((NUMBER, NULL))

    def test_single_observation(self) -> None:
        assert merge_all([INTEGER]) == INTEGER

    def test_rejects_an_empty_iterable(self) -> None:
        with pytest.raises(ValueError, match="at least one node"):
            merge_all([])
