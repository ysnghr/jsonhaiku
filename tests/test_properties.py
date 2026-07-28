"""Property-based tests over arbitrary JSON values.

Hand-written tests check the cases we thought of. These check the laws the
implementation has to obey for *every* input, which is where inference code
tends to break: a float that is also an integer, an empty container three levels
down, the same object under two key orders.
"""

from __future__ import annotations

import json
from typing import Any

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator

from jsonhaiku import describe
from jsonhaiku.core import infer, merge

# JSON as a strategy: scalars, then arrays and objects of those, a few deep.
# NaN and infinity are excluded because they are not JSON, whatever json.dumps
# is willing to write.
scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=12),
)
keys = st.text(min_size=1, max_size=6)
json_values = st.recursive(
    scalars,
    lambda children: st.lists(children, max_size=4) | st.dictionaries(keys, children, max_size=4),
    max_leaves=12,
)

SETTINGS = settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])


@given(json_values)
@SETTINGS
def test_describe_never_raises(value: Any) -> None:
    describe(value)


@given(json_values)
@SETTINGS
def test_describe_is_deterministic(value: Any) -> None:
    assert describe(value).compact == describe(value).compact


@given(json_values)
@SETTINGS
def test_the_generated_schema_accepts_the_value_it_came_from(value: Any) -> None:
    """The strongest single property: a schema that rejects its own source is wrong."""
    Draft202012Validator(describe(value).schema).validate(value)


@given(json_values)
@SETTINGS
def test_merge_is_idempotent(value: Any) -> None:
    node = infer(value)
    assert merge(node, node) == node


@given(json_values, json_values)
@SETTINGS
def test_merge_is_commutative(left: Any, right: Any) -> None:
    assert merge(infer(left), infer(right)) == merge(infer(right), infer(left))


@given(json_values, json_values, json_values)
@SETTINGS
def test_merge_is_associative(left: Any, middle: Any, right: Any) -> None:
    nodes = [infer(left), infer(middle), infer(right)]
    assert merge(merge(nodes[0], nodes[1]), nodes[2]) == merge(nodes[0], merge(nodes[1], nodes[2]))


@given(json_values)
@SETTINGS
def test_repeating_an_element_does_not_change_the_description(value: Any) -> None:
    assert describe([value]).compact == describe([value, value]).compact


@given(st.lists(json_values, min_size=2, max_size=5))
@SETTINGS
def test_element_order_does_not_change_the_description(values: list[Any]) -> None:
    assert describe(values).compact == describe(list(reversed(values))).compact


@given(st.dictionaries(keys, json_values, min_size=2, max_size=5))
@SETTINGS
def test_key_order_does_not_change_the_description(mapping: dict[str, Any]) -> None:
    reordered = dict(reversed(list(mapping.items())))
    assert describe(mapping).compact == describe(reordered).compact


@given(json_values)
@SETTINGS
def test_the_tree_is_json_serialisable(value: Any) -> None:
    assert json.loads(json.dumps(describe(value).tree)) == describe(value).tree


@given(st.lists(st.integers() | st.floats(allow_nan=False, allow_infinity=False), min_size=1))
@SETTINGS
def test_numbers_never_render_as_a_union(values: list[float]) -> None:
    """int and float in one column is a `number`, never `integer | float`."""
    assume(any(isinstance(value, float) for value in values))
    assume(any(isinstance(value, int) for value in values))
    assert describe(values).compact in {'["number"]', '["float"]', '["integer"]'}
