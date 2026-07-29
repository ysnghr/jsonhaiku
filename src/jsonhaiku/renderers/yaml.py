"""YAML renderer: a type tree as indented YAML.

Some LLMs — particularly smaller open models — reason about hierarchical
structure better in YAML.  It is also strictly cheaper in tokens for deeply
nested schemas, because it spends no characters on braces, brackets, or quotes.

.. code-block:: yaml

    id: integer
    tags:
      - string
    content:
      outline: html_string | null
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jsonhaiku.nodes import ArrayNode, EnumNode, ObjectNode, Primitive, UnionNode

if TYPE_CHECKING:
    from jsonhaiku.nodes import Node

__all__ = ["render_yaml"]

_INDENT = "  "


def render_yaml(node: Node, *, max_depth: int | None = None) -> str:
    """Render a type tree as YAML-style type description.

    Args:
        node: The root of the type tree.
        max_depth: When set, subtrees deeper than this level are replaced with a
            compact summary.
    """
    return _value(node, depth=0, max_depth=max_depth).rstrip("\n")


def _display_name(node: Primitive) -> str:
    """Return the display string for a primitive, including any string metadata."""
    if node.string_meta is not None:
        return f"{node.name} ({node.string_meta})"
    return node.name


def _value(
    node: Node,
    *,
    depth: int,
    max_depth: int | None,
    inline: bool = False,
) -> str:
    """Render ``node`` as a YAML fragment."""
    if isinstance(node, Primitive):
        return _display_name(node)
    if isinstance(node, EnumNode):
        return _enum_yaml(node)
    if isinstance(node, ArrayNode):
        return _array(node, depth=depth, max_depth=max_depth, inline=inline)
    if isinstance(node, ObjectNode):
        return _object(node, depth=depth, max_depth=max_depth, inline=inline)
    return _union(node, depth=depth, max_depth=max_depth, inline=inline)


def _object(
    node: ObjectNode,
    *,
    depth: int,
    max_depth: int | None,
    inline: bool = False,
) -> str:
    """Render an object type as YAML mapping entries."""
    if not node.fields:
        return "{}"

    if max_depth is not None and depth >= max_depth:
        return _depth_summary(node)

    indent = _INDENT * depth
    lines: list[str] = []

    for key, field in node.fields.items():
        label = _field_label(key, field.optional)
        child = field.type
        child_val = _value(child, depth=depth + 1, max_depth=max_depth)

        if _is_block(child):
            lines.append(f"{indent}{label}:")
            lines.append(child_val)
        else:
            lines.append(f"{indent}{label}: {child_val}")

    result = "\n".join(lines)
    if inline and depth > 0:
        return "\n" + result
    return result


def _array(
    node: ArrayNode,
    *,
    depth: int,
    max_depth: int | None,
    inline: bool = False,
) -> str:
    """Render an array type as YAML sequence entries."""
    if node.items is None:
        return "[]"

    indent = _INDENT * depth
    item_val = _value(node.items, depth=depth + 1, max_depth=max_depth)

    if _is_block(node.items):
        prefix = f"{indent}- "
        body = item_val.lstrip("\n")
        inner_indent = _INDENT * (depth + 1)
        first, *rest = body.split("\n")
        first = first.lstrip()
        rest_lines = [
            f"{indent}  {line.removeprefix(inner_indent)}"
            if line.startswith(inner_indent)
            else line
            for line in rest
        ]
        result = prefix + first
        if rest_lines:
            result += "\n" + "\n".join(rest_lines)
    else:
        result = f"{indent}- {item_val}"

    if inline and depth > 0:
        return "\n" + result
    return result


def _union(
    node: UnionNode,
    *,
    depth: int,
    max_depth: int | None,
    inline: bool = False,
) -> str:
    """Render a union type."""
    if _is_scalar_union(node):
        names = [_display_name(m) for m in node.members if isinstance(m, Primitive)]
        return " | ".join(names)

    parts = [
        _value(member, depth=depth, max_depth=max_depth, inline=True) for member in node.members
    ]

    result = " | ".join(p.strip() for p in parts)
    if inline and depth > 0:
        return result
    return result


def _enum_yaml(node: EnumNode) -> str:
    """Render an enum node as ``enum(a | b | null)``."""
    parts: list[str] = []
    for v in node.values:
        if v is None:
            parts.append("null")
        elif isinstance(v, bool):
            parts.append(str(v).lower())
        elif isinstance(v, str):
            parts.append(v)
        else:
            parts.append(str(v))
    return "enum(" + " | ".join(parts) + ")"


def _field_label(key: str, optional: bool) -> str:
    """Build a YAML key label, with ``?`` suffix for optional fields."""
    safe = _safe_yaml_key(key)
    if optional:
        return f"{safe}?"
    return safe


def _safe_yaml_key(key: str) -> str:
    """Quote a key if it contains characters that would confuse a YAML parser."""
    if not key or ":" in key or "#" in key or key != key.strip() or key.startswith(("-", "{")):
        return f'"{key}"'
    return key


def _is_block(node: Node) -> bool:
    """Return whether ``node`` should be rendered as an indented block."""
    if isinstance(node, ObjectNode) and node.fields:
        return True
    return isinstance(node, ArrayNode) and node.items is not None and _is_block(node.items)


def _is_scalar_union(node: UnionNode) -> bool:
    """Return whether all union members are primitives."""
    return all(isinstance(m, Primitive) for m in node.members)


def _depth_summary(node: ObjectNode) -> str:
    """Produce a truncated summary for objects that exceed max_depth."""
    count = len(node.fields)
    from jsonhaiku.renderers.compact import _max_depth_below  # noqa: PLC0415

    max_child = _max_depth_below(node)
    return f"{{ ... {count} fields, depth {max_child} }}"
