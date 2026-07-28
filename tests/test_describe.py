"""Tests for the public API: ``describe()`` and the ``Result`` it returns."""

from __future__ import annotations

import copy
import pickle

import pytest

import jsonhaiku
from jsonhaiku import Result, describe
from jsonhaiku.nodes import INTEGER, ArrayNode, Field, ObjectNode

PAYLOAD = [{"id": 1, "name": "a"}, {"id": 2, "name": None}]


class TestPublicSurface:
    def test_describe_is_exported(self) -> None:
        assert jsonhaiku.describe is describe

    def test_result_is_exported(self) -> None:
        assert isinstance(describe(1), Result)


class TestResult:
    def test_exposes_the_type_tree(self) -> None:
        assert describe([{"id": 1}]).root == ArrayNode(ObjectNode({"id": Field(INTEGER)}))

    def test_compact_rendering(self) -> None:
        assert describe(PAYLOAD).compact == '[{\n  "id": "integer",\n  "name": "string | null"\n}]'

    def test_tree_is_a_plain_dictionary(self) -> None:
        assert describe(1).tree == {"kind": "primitive", "type": "integer"}

    def test_schema_rendering(self) -> None:
        assert describe(1).schema["type"] == "integer"

    def test_str_is_the_compact_rendering(self) -> None:
        result = describe(PAYLOAD)
        assert str(result) == result.compact

    def test_repr_is_a_short_summary(self) -> None:
        assert repr(describe(1)) == "Result(integer)"

    def test_repr_truncates_large_trees(self) -> None:
        wide = {f"field_{index}": index for index in range(20)}
        assert repr(describe(wide)).endswith("…)")


class TestImmutability:
    def test_result_is_frozen(self) -> None:
        result = describe(1)
        with pytest.raises(AttributeError):
            result.root = INTEGER  # type: ignore[misc]

    def test_compact_is_computed_once(self) -> None:
        result = describe(PAYLOAD)
        assert result.compact is result.compact

    def test_tree_is_fresh_on_every_access(self) -> None:
        result = describe({"id": 1})
        result.tree["kind"] = "tampered"
        assert result.tree["kind"] == "object"

    def test_schema_is_fresh_on_every_access(self) -> None:
        result = describe({"id": 1})
        result.schema["title"] = "tampered"
        assert "title" not in result.schema


class TestDeterminism:
    def test_same_input_gives_identical_output(self) -> None:
        expected = describe(PAYLOAD).compact
        assert all(describe(PAYLOAD).compact == expected for _ in range(100))

    def test_key_order_does_not_affect_the_description(self) -> None:
        left = describe({"a": 1, "b": {"c": 2, "d": 3}})
        right = describe({"b": {"d": 3, "c": 2}, "a": 1})
        assert left.compact == right.compact
        assert left.root == right.root

    def test_results_of_equal_payloads_are_equal(self) -> None:
        assert describe(PAYLOAD) == describe(PAYLOAD)

    def test_results_survive_pickling(self) -> None:
        # Results get cached and shipped between processes; make sure they can be.
        result = describe(PAYLOAD)
        restored = pickle.loads(pickle.dumps(result))  # noqa: S301 -- our own object
        assert restored == result
        assert restored.compact == result.compact

    def test_results_survive_deep_copying(self) -> None:
        result = describe(PAYLOAD)
        assert copy.deepcopy(result) == result


class TestRealisticPayload:
    def test_describes_a_record_array_end_to_end(self) -> None:
        sessions = [
            {"id": 1, "code": "A1", "duration": 30, "room": {"name": "HALL A"}, "notes": None},
            {"id": 2, "code": "B2", "duration": 45.5, "room": {"name": "HALL B"}},
        ]
        assert describe(sessions).compact == (
            "[{\n"
            '  "code": "string",\n'
            '  "duration": "number",\n'
            '  "id": "integer",\n'
            '  "notes": "null | undefined",\n'
            '  "room": {\n'
            '    "name": "string"\n'
            "  }\n"
            "}]"
        )
