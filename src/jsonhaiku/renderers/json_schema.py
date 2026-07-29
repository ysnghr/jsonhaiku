"""JSON Schema renderer — re-exports from the existing schema module.

The implementation lives in :mod:`jsonhaiku.schema` for backward compatibility;
this module exists so that ``from jsonhaiku.renderers import render_json_schema``
follows the same pattern as the other renderers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jsonhaiku.schema import SCHEMA_DIALECT, to_json_schema

if TYPE_CHECKING:
    from jsonhaiku.nodes import Node

__all__ = ["SCHEMA_DIALECT", "render_json_schema"]


def render_json_schema(node: Node, *, max_depth: int | None = None) -> dict[str, Any]:
    """Render a type tree as a JSON Schema document.

    Args:
        node: The root of the type tree.
        max_depth: When set, subtrees deeper than this level are replaced with
            an empty schema (accepting anything).
    """
    if max_depth is None:
        return to_json_schema(node)
    return {"$schema": SCHEMA_DIALECT, **_schema_with_depth(node, depth=0, max_depth=max_depth)}


def _schema_with_depth(node: Node, *, depth: int, max_depth: int) -> dict[str, Any]:
    """Render with depth tracking."""
    from jsonhaiku.nodes import ArrayNode, ObjectNode, Primitive, UnionNode  # noqa: PLC0415

    if isinstance(node, Primitive):
        from jsonhaiku.schema import _JSON_SCHEMA_TYPES  # noqa: PLC0415

        json_type = _JSON_SCHEMA_TYPES.get(node.name)
        return {} if json_type is None else {"type": json_type}
    if isinstance(node, ArrayNode):
        if node.items is None:
            return {"type": "array"}
        items = _schema_with_depth(node.items, depth=depth, max_depth=max_depth)
        return {"type": "array", "items": items}
    if isinstance(node, ObjectNode):
        return _object_with_depth(node, depth=depth, max_depth=max_depth)
    return _union_with_depth(node, depth=depth, max_depth=max_depth)


def _object_with_depth(node: Node, *, depth: int, max_depth: int) -> dict[str, Any]:
    """Render an object schema with depth limiting."""
    from jsonhaiku.nodes import ObjectNode  # noqa: PLC0415

    if not isinstance(node, ObjectNode):
        return {}  # pragma: no cover
    if not node.fields:
        return {"type": "object"}
    if depth >= max_depth:
        return {"type": "object"}

    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            key: _schema_with_depth(field.type, depth=depth + 1, max_depth=max_depth)
            for key, field in node.fields.items()
        },
    }
    required = [key for key, field in node.fields.items() if not field.optional]
    if required:
        schema["required"] = required
    return schema


def _union_with_depth(node: Node, *, depth: int, max_depth: int) -> dict[str, Any]:
    """Render a union schema with depth limiting."""
    from jsonhaiku.nodes import Primitive, UnionNode  # noqa: PLC0415
    from jsonhaiku.schema import _JSON_SCHEMA_TYPES  # noqa: PLC0415

    if not isinstance(node, UnionNode):
        return {}  # pragma: no cover

    names = [
        _JSON_SCHEMA_TYPES[member.name]
        for member in node.members
        if isinstance(member, Primitive) and member.name in _JSON_SCHEMA_TYPES
    ]
    if len(names) == len(node.members):
        return {"type": names}
    return {
        "anyOf": [
            _schema_with_depth(member, depth=depth, max_depth=max_depth) for member in node.members
        ],
    }
