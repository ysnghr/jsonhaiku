"""JSON Schema rendering, for everything that speaks schema rather than prose.

The compact format is for models; this is for the rest of the toolchain —
Pydantic, OpenAI structured outputs, Anthropic tool definitions, enterprise
validation. It targets Draft 2020-12.

Two things it deliberately does not do:

* It never emits ``additionalProperties: false``. jsonhaiku describes the values
  it was shown; it has no basis for claiming no other key can ever appear.
* It never invents a ``format``. Content-type detection arrives in a later phase
  and will be opt-in, because guessing is worse than staying quiet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jsonhaiku.nodes import ArrayNode, ObjectNode, Primitive, UnionNode

if TYPE_CHECKING:
    from jsonhaiku.nodes import Node

__all__ = ["SCHEMA_DIALECT", "to_json_schema"]

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
"""The dialect advertised in the generated ``$schema`` key."""

_JSON_SCHEMA_TYPES: dict[str, str] = {
    "null": "null",
    "boolean": "boolean",
    "integer": "integer",
    "float": "number",
    "number": "number",
    "string": "string",
    # "unknown" has no JSON Schema equivalent and is handled as "any" instead.
}


def to_json_schema(node: Node) -> dict[str, Any]:
    """Render a type tree as a JSON Schema document.

    The result is a fresh, mutable dictionary: callers routinely bolt on a
    ``title`` or ``$id`` of their own.
    """
    return {"$schema": SCHEMA_DIALECT, **_schema(node)}


def _schema(node: Node) -> dict[str, Any]:
    """Render ``node`` as a schema fragment, without the ``$schema`` key."""
    if isinstance(node, Primitive):
        json_type = _JSON_SCHEMA_TYPES.get(node.name)
        # An empty schema accepts anything, which is exactly what "unknown" means.
        return {} if json_type is None else {"type": json_type}
    if isinstance(node, ArrayNode):
        if node.items is None:
            return {"type": "array"}
        return {"type": "array", "items": _schema(node.items)}
    if isinstance(node, ObjectNode):
        return _object_schema(node)
    return _union_schema(node)


def _object_schema(node: ObjectNode) -> dict[str, Any]:
    """Render an object type, listing every key that was always present as required."""
    if not node.fields:
        return {"type": "object"}

    schema: dict[str, Any] = {
        "type": "object",
        "properties": {key: _schema(field.type) for key, field in node.fields.items()},
    }
    required = [key for key, field in node.fields.items() if not field.optional]
    if required:
        schema["required"] = required
    return schema


def _union_schema(node: UnionNode) -> dict[str, Any]:
    """Render a union, preferring the compact ``type`` list over ``anyOf``.

    ``{"type": ["string", "null"]}`` says the same thing as a two-branch
    ``anyOf`` in a fraction of the space, and every validator understands it. It
    only works for scalars, so structural unions still fall back to ``anyOf``.
    """
    names = [
        _JSON_SCHEMA_TYPES[member.name]
        for member in node.members
        if isinstance(member, Primitive) and member.name in _JSON_SCHEMA_TYPES
    ]
    if len(names) == len(node.members):
        return {"type": names}
    return {"anyOf": [_schema(member) for member in node.members]}
