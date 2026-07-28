"""Type inference: turn JSON values into a type tree, and merge observations.

The two operations here are :func:`infer` (one value, one tree) and :func:`merge`
(two trees, one tree). Everything else in jsonhaiku is a rendering of what these
two produce.

``merge`` is commutative and idempotent, which matters more than it sounds: it is
what lets a 10,000-element array be folded into one type in any order, and what
guarantees that describing the same data twice gives the same answer.
"""

from __future__ import annotations

import warnings
from functools import reduce
from typing import TYPE_CHECKING

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
    Primitive,
    UnionNode,
    canonical,
)
from jsonhaiku.result import Result

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

__all__ = [
    "UnsupportedValueWarning",
    "describe",
    "infer",
    "merge",
    "merge_all",
    "union_of",
]

_NUMERIC_NAMES = frozenset({"integer", "float", "number"})

# Order matters: bool must precede int, because isinstance(True, int) is True in
# Python. Get this wrong and every boolean is silently described as an integer.
_SCALAR_TYPES: tuple[tuple[type, Primitive], ...] = (
    (bool, BOOLEAN),
    (int, INTEGER),
    (float, FLOAT),
    (str, STRING),
)


class UnsupportedValueWarning(UserWarning):
    """Warned when a value is not JSON-representable and is described as ``unknown``.

    jsonhaiku accepts what :func:`json.dumps` accepts. Anything else — a
    ``Decimal``, a ``set``, a numpy scalar — cannot be described faithfully, so it
    becomes ``unknown`` and says so out loud rather than being guessed at.
    """


def describe(data: object) -> Result:
    """Describe a JSON value.

    This is the front door of the library.

    Args:
        data: Any JSON value — a dict, a list of thousands of records, or a bare
            scalar. Values that :func:`json.dumps` could not serialise are
            described as ``unknown`` and warned about.

    Returns:
        A :class:`~jsonhaiku.result.Result` exposing the description in every
        supported format.

    Example:
        >>> from jsonhaiku import describe
        >>> print(describe([{"id": 1, "name": "a"}, {"id": 2, "name": None}]).compact)
        [{
          "id": "integer",
          "name": "string | null"
        }]
    """
    return Result(root=infer(data))


def infer(value: object) -> Node:
    """Infer the type tree of a single JSON value.

    Args:
        value: A JSON value: ``None``, ``bool``, ``int``, ``float``, ``str``,
            a sequence (``list`` or ``tuple``), or a ``dict``.

    Returns:
        The type tree describing ``value``.

    Warns:
        UnsupportedValueWarning: If ``value`` is not JSON-representable. The
            result is ``unknown`` rather than an exception, so one odd value in a
            large payload never costs you the whole description.
    """
    if value is None:
        return NULL
    for python_type, scalar in _SCALAR_TYPES:
        if isinstance(value, python_type):
            return scalar
    if isinstance(value, list | tuple):
        elements = [infer(element) for element in value]
        return ArrayNode(merge_all(elements) if elements else None)
    if isinstance(value, dict):
        # Non-string keys are stringified, exactly as json.dumps would.
        return ObjectNode({str(key): Field(infer(item)) for key, item in value.items()})

    warnings.warn(
        f"cannot describe {type(value).__name__!r}; emitting 'unknown'",
        UnsupportedValueWarning,
        stacklevel=2,
    )
    return UNKNOWN


def merge(left: Node, right: Node) -> Node:
    """Merge two observations of the same path into one type.

    Objects merge field by field, arrays merge their element types, and anything
    else becomes a union.
    """
    if left == right:
        return left
    if isinstance(left, ObjectNode) and isinstance(right, ObjectNode):
        return _merge_objects(left, right)
    if isinstance(left, ArrayNode) and isinstance(right, ArrayNode):
        return ArrayNode(_merge_items(left.items, right.items))
    return union_of((left, right))


def merge_all(nodes: Iterable[Node]) -> Node:
    """Merge a non-empty iterable of nodes into a single type.

    Raises:
        ValueError: If ``nodes`` is empty; an empty container has no element type
            to merge, and callers must decide what that means for them.
    """
    observations = list(nodes)
    if not observations:
        message = "merge_all() requires at least one node"
        raise ValueError(message)
    return reduce(merge, observations)


def union_of(nodes: Iterable[Node]) -> Node:
    """Build the union of ``nodes``, normalising it into canonical form.

    Nested unions are flattened, duplicates removed, mixed numeric types
    collapsed to ``number``, and — importantly — members of the same kind merged
    with each other. A union therefore holds at most one array member and at
    most one object member, which is what makes ``merge`` commutative and
    associative: ``[null, [], [null]]`` must describe the same way whatever
    order those three elements arrive in.

    A union of one member collapses to that member, so this never produces a
    pointless single-member union.
    """
    scalars: list[Node] = []
    arrays: list[Node] = []
    objects: list[Node] = []
    for node in _flatten(nodes):
        if isinstance(node, ArrayNode):
            arrays.append(node)
        elif isinstance(node, ObjectNode):
            objects.append(node)
        else:
            scalars.append(node)

    members = _unique(_collapse_numerics(scalars))
    if arrays:
        members.append(reduce(merge, arrays))
    if objects:
        members.append(reduce(merge, objects))

    if len(members) == 1:
        return members[0]
    return UnionNode(tuple(members))


def _flatten(nodes: Iterable[Node]) -> Iterator[Node]:
    """Yield ``nodes``, replacing any union with its members."""
    for node in nodes:
        if isinstance(node, UnionNode):
            yield from node.members
        else:
            yield node


def _merge_objects(left: ObjectNode, right: ObjectNode) -> ObjectNode:
    """Merge two object types: union of keys, recursive merge of shared ones.

    A key seen on only one side becomes optional, which is what later renders as
    ``| undefined`` and drops the key from JSON Schema's ``required`` list.
    """
    shared = left.fields.keys() & right.fields.keys()
    fields = {
        key: Field(
            merge(left.fields[key].type, right.fields[key].type),
            optional=left.fields[key].optional or right.fields[key].optional,
        )
        for key in shared
    }
    for side in (left, right):
        for key, field in side.fields.items():
            if key not in shared:
                fields[key] = Field(field.type, optional=True)
    return ObjectNode(fields)


def _merge_items(left: Node | None, right: Node | None) -> Node | None:
    """Merge two array element types, treating ``None`` (empty array) as no news."""
    if left is None:
        return right
    if right is None:
        return left
    return merge(left, right)


def _collapse_numerics(nodes: list[Node]) -> list[Node]:
    """Replace mixed ``integer``/``float`` observations with ``number``.

    JSON has a single number type; ``1`` and ``1.5`` in the same field is not a
    union worth showing to a model.
    """
    observed = {
        node.name for node in nodes if isinstance(node, Primitive) and node.name in _NUMERIC_NAMES
    }
    if len(observed) <= 1:
        return nodes
    return [
        NUMBER if isinstance(node, Primitive) and node.name in _NUMERIC_NAMES else node
        for node in nodes
    ]


def _unique(nodes: list[Node]) -> list[Node]:
    """Drop duplicate nodes, keeping first-seen order."""
    by_signature: dict[str, Node] = {}
    for node in nodes:
        by_signature.setdefault(canonical(node), node)
    return list(by_signature.values())
