"""TypeScript interface renderer.

GPT-4 and Claude were both heavily trained on TypeScript, so this format often
produces better model comprehension than any other.

.. code-block:: typescript

    interface Root {
      id: number;
      tags: string[];
      content: {
        outline: string | null;   // html
      };
    }
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jsonhaiku.nodes import (
    ArrayNode,
    ObjectNode,
    Primitive,
    UnionNode,
)

if TYPE_CHECKING:
    from jsonhaiku.nodes import Node

__all__ = ["render_typescript"]

_INDENT = "  "

_TS_TYPE_MAP: dict[str, str] = {
    "null": "null",
    "boolean": "boolean",
    "integer": "number",
    "float": "number",
    "number": "number",
    "string": "string",
    "unknown": "unknown",
}

_CONTENT_TYPE_COMMENTS: dict[str, str] = {
    "html_string": "html",
    "url_string": "url",
    "iso_date": "ISO date",
    "iso_datetime": "ISO datetime",
    "uuid_string": "UUID",
    "email_string": "email",
    "jwt_string": "JWT",
}


def render_typescript(
    node: Node,
    *,
    root_name: str = "Root",
    max_depth: int | None = None,
) -> str:
    """Render a type tree as a TypeScript interface declaration.

    Args:
        node: The root of the type tree.
        root_name: Name for the top-level interface.
        max_depth: When set, subtrees deeper than this level are replaced with
            ``Record<string, unknown>``.
    """
    if isinstance(node, ObjectNode):
        return _interface(node, root_name, depth=0, max_depth=max_depth)
    if isinstance(node, ArrayNode):
        items = node.items
        element_ts = _type_expr(items, depth=0, max_depth=max_depth) if items else "unknown"
        return f"type {root_name} = {element_ts}[];"
    return f"type {root_name} = {_type_expr(node, depth=0, max_depth=max_depth)};"


def _interface(
    node: ObjectNode,
    name: str,
    *,
    depth: int,
    max_depth: int | None,
) -> str:
    """Render an object node as a named TypeScript interface."""
    if not node.fields:
        return f"interface {name} {{}}"

    lines = [f"interface {name} {{"]
    for key, field in node.fields.items():
        safe_key = _safe_key(key)
        opt = "?" if field.optional else ""
        ts_type = _type_expr(field.type, depth=depth + 1, max_depth=max_depth)
        comment = _trailing_comment(field.type)
        line = f"{_INDENT}{safe_key}{opt}: {ts_type};"
        if comment:
            line += f"   // {comment}"
        lines.append(line)
    lines.append("}")
    return "\n".join(lines)


def _type_expr(
    node: Node | None,
    *,
    depth: int,
    max_depth: int | None,
) -> str:
    """Produce a TypeScript type expression for ``node``."""
    if node is None:
        return "unknown"

    if isinstance(node, Primitive):
        return _TS_TYPE_MAP.get(node.name, "string")

    if isinstance(node, ArrayNode):
        items = node.items
        inner = _type_expr(items, depth=depth, max_depth=max_depth) if items else "unknown"
        if " | " in inner:
            return f"({inner})[]"
        return f"{inner}[]"

    if isinstance(node, ObjectNode):
        return _inline_object(node, depth=depth, max_depth=max_depth)

    parts = [_type_expr(member, depth=depth, max_depth=max_depth) for member in node.members]
    return " | ".join(parts)


def _inline_object(
    node: ObjectNode,
    *,
    depth: int,
    max_depth: int | None,
) -> str:
    """Render an object as an inline type literal ``{ key: type; ... }``."""
    if not node.fields:
        return "{}"

    if max_depth is not None and depth >= max_depth:
        return "Record<string, unknown>"

    inner = depth + 1
    indent = _INDENT * inner
    outer_indent = _INDENT * depth

    lines: list[str] = ["{"]
    for key, field in node.fields.items():
        safe_key = _safe_key(key)
        opt = "?" if field.optional else ""
        ts_type = _type_expr(field.type, depth=inner, max_depth=max_depth)
        comment = _trailing_comment(field.type)
        line = f"{indent}{safe_key}{opt}: {ts_type};"
        if comment:
            line += f"   // {comment}"
        lines.append(line)
    lines.append(f"{outer_indent}}}")
    return "\n".join(lines)


def _trailing_comment(node: Node) -> str:
    """Return a short trailing comment for content-typed strings, or empty."""
    if isinstance(node, Primitive) and node.name in _CONTENT_TYPE_COMMENTS:
        return _CONTENT_TYPE_COMMENTS[node.name]
    if isinstance(node, UnionNode):
        comments = [
            _CONTENT_TYPE_COMMENTS[m.name]
            for m in node.members
            if isinstance(m, Primitive) and m.name in _CONTENT_TYPE_COMMENTS
        ]
        if comments:
            return ", ".join(comments)
    return ""


def _safe_key(key: str) -> str:
    """Quote an object key if it is not a valid TypeScript identifier."""
    if key.isidentifier() and not _is_ts_reserved(key):
        return key
    return f'"{key}"'


_TS_RESERVED = frozenset({
    "break", "case", "catch", "class", "const", "continue", "debugger",
    "default", "delete", "do", "else", "enum", "export", "extends",
    "false", "finally", "for", "function", "if", "import", "in",
    "instanceof", "new", "null", "return", "super", "switch", "this",
    "throw", "true", "try", "typeof", "var", "void", "while", "with",
})


def _is_ts_reserved(word: str) -> bool:
    """Return whether ``word`` is a TypeScript reserved keyword."""
    return word in _TS_RESERVED
