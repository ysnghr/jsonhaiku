"""The compact renderer: a type tree as TypeScript-flavoured, JSON-shaped text.

The format keeps JSON's punctuation — which every model has seen a billion times —
and replaces the *values* with type expressions.

.. code-block:: json

    {
      "id": "integer",
      "tags": ["string"],
      "room": {
        "name": "string"
      },
      "outline": "string | null"
    }

The rules, in full:

* A scalar is its type name in quotes: ``"integer"``.
* A union of scalars is one quoted expression: ``"string | null"``. ``null``
  always comes last.
* An array is its element type in brackets: ``["string"]``. An array that was
  only ever empty is ``[]`` — "array of something, we never saw what".
* An object is a JSON object whose values are type expressions. Keys are sorted,
  so the same data always renders byte-identically.
* An empty object is ``{}``.
* A field that was missing from some observations gains ``| undefined``.
  ``| null`` and ``| undefined`` mean different things and are never conflated:
  the first is a value that was present and null, the second a key that was
  absent.
* A union that involves structure renders its members inline, separated by
  ``|``: ``[{"id": "integer"} | null]``. Scalars appear bare there, because the
  expression around them is already unquoted. This is the one place the output
  stops being valid JSON, and it is worth it: the alternative is hiding the fact
  that an array holds more than one shape.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from jsonhaiku.nodes import ArrayNode, ObjectNode, Primitive, UnionNode

if TYPE_CHECKING:
    from jsonhaiku.nodes import Node

__all__ = ["render_compact"]

INDENT = "  "
"""One level of indentation. Two spaces: JSON convention, and cheap in tokens."""

_OPTIONAL_SUFFIX = " | undefined"


def render_compact(node: Node) -> str:
    """Render a type tree as compact type-map text."""
    return _value(node, "")


def _value(node: Node, indent: str | None, *, optional: bool = False) -> str:
    """Render ``node`` where a JSON value would go.

    Args:
        node: The node to render.
        indent: The indentation of the line this value starts on, or ``None`` to
            force the result onto a single line.
        optional: Whether the field holding this value was sometimes absent.
    """
    suffix = _OPTIONAL_SUFFIX if optional else ""

    if isinstance(node, Primitive):
        return _quote(node.name + suffix)
    if isinstance(node, ArrayNode):
        element = "" if node.items is None else _value(node.items, indent)
        return f"[{element}]{suffix}"
    if isinstance(node, ObjectNode):
        return _object(node, indent) + suffix

    scalars = _scalar_union(node)
    if scalars is not None:
        return _quote(scalars + suffix)
    return " | ".join(_union_member(member) for member in node.members) + suffix


def _object(node: ObjectNode, indent: str | None) -> str:
    """Render an object type: as an indented block when possible, inline when not."""
    if not node.fields:
        return "{}"
    if indent is None:
        entries = (
            f"{_quote(key)}: {_value(field.type, None, optional=field.optional)}"
            for key, field in node.fields.items()
        )
        return "{" + ", ".join(entries) + "}"

    inner = indent + INDENT
    lines = (
        f"{inner}{_quote(key)}: {_value(field.type, inner, optional=field.optional)}"
        for key, field in node.fields.items()
    )
    return "{\n" + ",\n".join(lines) + f"\n{indent}}}"


def _union_member(node: Node) -> str:
    """Render one member of a union that also contains structure.

    Scalars appear bare here (``null``, not ``"null"``) because the surrounding
    expression is already unquoted, and ``"null"`` would read like the string
    ``null`` rather than the type.
    """
    if isinstance(node, Primitive):
        return node.name
    return _value(node, None)


def _scalar_union(node: UnionNode) -> str | None:
    """Return the single quoted expression for a scalar-only union, else ``None``."""
    names = [member.name for member in node.members if isinstance(member, Primitive)]
    if len(names) != len(node.members):
        return None
    return " | ".join(names)


def _quote(text: str) -> str:
    """Quote ``text`` as a JSON string, escaping whatever needs escaping."""
    return json.dumps(text, ensure_ascii=False)
