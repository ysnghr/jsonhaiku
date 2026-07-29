"""The compact renderer: a type tree as TypeScript-flavoured, JSON-shaped text.

The format keeps JSON's punctuation — which every model has seen a billion times
— and replaces the *values* with type expressions.

.. code-block:: json

    {
      "id": "integer",
      "tags": ["string"],
      "room": {
        "name": "string"
      },
      "outline": "string | null"
    }
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from jsonhaiku.nodes import ArrayNode, Field, ObjectNode, Primitive, UnionNode

if TYPE_CHECKING:
    from jsonhaiku.nodes import Node

__all__ = ["render_compact"]

INDENT = "  "
"""One level of indentation. Two spaces: JSON convention, and cheap in tokens."""

_OPTIONAL_SUFFIX = " | undefined"


def render_compact(node: Node, *, max_depth: int | None = None) -> str:
    """Render a type tree as compact type-map text.

    Args:
        node: The root of the type tree.
        max_depth: When set, subtrees deeper than this level are replaced with a
            compact summary.
    """
    return _value(node, "", depth=0, max_depth=max_depth)


def _display_name(node: Primitive) -> str:
    """Return the display string for a primitive, including any string metadata."""
    if node.string_meta is not None:
        return f"{node.name} ({node.string_meta})"
    return node.name


def _value(
    node: Node,
    indent: str | None,
    *,
    optional: bool = False,
    depth: int = 0,
    max_depth: int | None = None,
) -> str:
    """Render ``node`` where a JSON value would go."""
    suffix = _OPTIONAL_SUFFIX if optional else ""

    if isinstance(node, Primitive):
        return _quote(_display_name(node) + suffix)
    if isinstance(node, ArrayNode):
        element = (
            ""
            if node.items is None
            else _value(
                node.items,
                indent,
                depth=depth,
                max_depth=max_depth,
            )
        )
        return f"[{element}]{suffix}"
    if isinstance(node, ObjectNode):
        return _object(node, indent, depth=depth, max_depth=max_depth) + suffix

    scalars = _scalar_union(node)
    if scalars is not None:
        return _quote(scalars + suffix)
    return (
        " | ".join(
            _union_member(member, depth=depth, max_depth=max_depth) for member in node.members
        )
        + suffix
    )


def _field_value(
    field: Field,
    indent: str | None,
    depth: int,
    max_depth: int | None,
) -> str:
    """Render a field's value with optional and depth parameters."""
    return _value(
        field.type,
        indent,
        optional=field.optional,
        depth=depth,
        max_depth=max_depth,
    )


def _object(
    node: ObjectNode,
    indent: str | None,
    *,
    depth: int = 0,
    max_depth: int | None = None,
) -> str:
    """Render an object type: as an indented block when possible, inline when not."""
    if not node.fields:
        return "{}"

    if max_depth is not None and depth >= max_depth:
        return _depth_summary(node)

    if indent is None:
        entries = (
            f"{_quote(key)}: {_field_value(field, None, depth + 1, max_depth)}"
            for key, field in node.fields.items()
        )
        return "{" + ", ".join(entries) + "}"

    inner = indent + INDENT
    lines = (
        f"{inner}{_quote(key)}: {_field_value(field, inner, depth + 1, max_depth)}"
        for key, field in node.fields.items()
    )
    return "{\n" + ",\n".join(lines) + f"\n{indent}}}"


def _depth_summary(node: ObjectNode) -> str:
    """Produce a truncated summary for objects that exceed max_depth."""
    count = len(node.fields)
    max_child = _max_depth_below(node)
    return f"{{ ... {count} fields, depth {max_child} }}"


def _max_depth_below(node: Node) -> int:
    """Return the maximum nesting depth below ``node``."""
    if isinstance(node, Primitive):
        return 0
    if isinstance(node, ArrayNode):
        return 0 if node.items is None else 1 + _max_depth_below(node.items)
    if isinstance(node, ObjectNode):
        if not node.fields:
            return 0
        return 1 + max(_max_depth_below(f.type) for f in node.fields.values())
    return max(_max_depth_below(m) for m in node.members)


def _union_member(
    node: Node,
    *,
    depth: int = 0,
    max_depth: int | None = None,
) -> str:
    """Render one member of a union that also contains structure."""
    if isinstance(node, Primitive):
        return _display_name(node)
    return _value(node, None, depth=depth, max_depth=max_depth)


def _scalar_union(node: UnionNode) -> str | None:
    """Return the single quoted expression for a scalar-only union, else ``None``."""
    names = [_display_name(member) for member in node.members if isinstance(member, Primitive)]
    if len(names) != len(node.members):
        return None
    return " | ".join(names)


def _quote(text: str) -> str:
    """Quote ``text`` as a JSON string, escaping whatever needs escaping."""
    return json.dumps(text, ensure_ascii=False)
