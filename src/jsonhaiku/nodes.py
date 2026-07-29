"""The internal type tree — an immutable, canonically ordered description of shape.

Every public rendering (compact, JSON Schema, and later TypeScript and YAML) is a
pure function over this tree, so the tree is the one thing that has to be right.

Two invariants make renderings deterministic without any renderer having to think
about it:

* **Object fields are stored in sorted key order.** Two payloads that differ only
  in key order therefore produce equal trees, and byte-identical output.
* **Union members are stored in canonical order:** scalars, then arrays, then
  objects, alphabetically within each group, with ``null`` always last. That
  ordering is what makes ``"string | null"`` read the way a TypeScript
  programmer expects rather than ``"null | string"``.

The nodes are frozen dataclasses and object fields are wrapped in a read-only
mapping, so a tree can be shared and cached without defensive copying.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Mapping

PrimitiveName: TypeAlias = Literal[
    "null",
    "boolean",
    "integer",
    "float",
    "number",
    "string",
    "unknown",
    "html_string",
    "url_string",
    "iso_date",
    "iso_datetime",
    "uuid_string",
    "email_string",
    "jwt_string",
    "always_null",
    "always_empty_array",
    "always_empty_object",
]
"""The scalar type names jsonhaiku can emit.

``number`` is the merge of ``integer`` and ``float`` (JSON draws no such
distinction), and ``unknown`` marks a value jsonhaiku could not describe.

The ``*_string`` variants are emitted when content-type detection is enabled
and a string value matches a known pattern.
"""


@dataclass(frozen=True, slots=True)
class Primitive:
    """A scalar type, such as ``integer`` or ``string``.

    Attributes:
        name: The type name.
        string_meta: Optional rendering annotation for long plain strings,
            e.g. ``"len≈523, sample: 'The quick brown fox…'"``.
    """

    name: PrimitiveName
    string_meta: str | None = None


@dataclass(frozen=True, slots=True)
class ArrayNode:
    """An array type.

    Attributes:
        items: The merged element type, or ``None`` when only empty arrays were
            observed and the element type is therefore unknown.
    """

    items: Node | None


@dataclass(frozen=True, slots=True)
class Field:
    """One member of an object type.

    Attributes:
        type: The merged type of the values observed for this key.
        optional: ``True`` when at least one observed object omitted the key.
    """

    type: Node
    optional: bool = False


@dataclass(frozen=True, slots=True)
class ObjectNode:
    """An object type, keyed by field name.

    Fields are normalised into sorted order on construction, which is what makes
    equality independent of the key order in the source document.
    """

    fields: Mapping[str, Field]

    def __post_init__(self) -> None:
        """Freeze the field mapping in canonical (sorted) key order."""
        object.__setattr__(self, "fields", _frozen_fields(self.fields))

    def __reduce__(self) -> tuple[type[ObjectNode], tuple[dict[str, Field]]]:
        """Support pickling and deep-copying by rebuilding through the constructor.

        A mappingproxy is neither picklable nor deep-copyable, and results are
        meant to be cached and shipped between processes. ``__reduce__`` rather
        than ``__getstate__`` because on Python 3.10 the ``slots=True`` dataclass
        transform installs its own ``__getstate__`` over anything defined here.
        """
        return (type(self), (dict(self.fields),))


@dataclass(frozen=True, slots=True)
class UnionNode:
    """A union of two or more distinct types.

    Members are normalised into canonical order on construction. Build unions
    with :func:`jsonhaiku.core.union_of` rather than directly: it also flattens
    nested unions, removes duplicates and applies the numeric merge rule.
    """

    members: tuple[Node, ...]

    def __post_init__(self) -> None:
        """Sort members into canonical order."""
        object.__setattr__(self, "members", tuple(sorted(self.members, key=sort_key)))


@dataclass(frozen=True, slots=True)
class EnumNode:
    """A set of observed literal values rendered as an enum.

    Attributes:
        values: The distinct values, sorted (strings alphabetically, numbers
            numerically, ``None`` last).
        frequencies: Parallel to *values* — how many times each was observed.
            ``None`` when ``include_frequency`` is off.
    """

    values: tuple[str | int | bool | None, ...]
    frequencies: tuple[int, ...] | None = None


Node: TypeAlias = Primitive | ArrayNode | ObjectNode | UnionNode | EnumNode
"""Any node in the type tree."""


def _frozen_fields(fields: Mapping[str, Field]) -> Mapping[str, Field]:
    """Return a read-only copy of ``fields`` in sorted key order."""
    return MappingProxyType(dict(sorted(fields.items())))


NULL = Primitive("null")
BOOLEAN = Primitive("boolean")
INTEGER = Primitive("integer")
FLOAT = Primitive("float")
NUMBER = Primitive("number")
STRING = Primitive("string")
UNKNOWN = Primitive("unknown")

HTML_STRING = Primitive("html_string")
URL_STRING = Primitive("url_string")
ISO_DATE = Primitive("iso_date")
ISO_DATETIME = Primitive("iso_datetime")
UUID_STRING = Primitive("uuid_string")
EMAIL_STRING = Primitive("email_string")
JWT_STRING = Primitive("jwt_string")

ALWAYS_NULL = Primitive("always_null")
ALWAYS_EMPTY_ARRAY = Primitive("always_empty_array")
ALWAYS_EMPTY_OBJECT = Primitive("always_empty_object")

STRING_CONTENT_TYPES: frozenset[PrimitiveName] = frozenset(
    {
        "html_string",
        "url_string",
        "iso_date",
        "iso_datetime",
        "uuid_string",
        "email_string",
        "jwt_string",
    }
)
"""Content-type string variant names, for merge and rendering logic."""

ALL_STRING_NAMES: frozenset[PrimitiveName] = STRING_CONTENT_TYPES | {"string"}
"""Every primitive name that represents a string."""


def canonical(node: Node) -> str:
    """Return a compact, stable signature of ``node``.

    The signature is an implementation detail used for ordering and de-duplication;
    it is not part of the public output format. Two nodes have the same signature
    if and only if they describe the same type.
    """
    if isinstance(node, Primitive):
        return node.name
    if isinstance(node, EnumNode):
        return "enum(" + "|".join(repr(v) for v in node.values) + ")"
    if isinstance(node, ArrayNode):
        return f"[{'' if node.items is None else canonical(node.items)}]"
    if isinstance(node, ObjectNode):
        members = (
            f"{key}{'?' if field.optional else ''}:{canonical(field.type)}"
            for key, field in node.fields.items()
        )
        return "{" + ",".join(members) + "}"
    return "(" + "|".join(canonical(member) for member in node.members) + ")"


def sort_key(node: Node) -> tuple[int, str]:
    """Return the canonical sort key for a union member.

    Scalars come first, then arrays, then objects and unions, alphabetically
    within each group. ``null`` sorts last so that nullable types render as
    ``"string | null"`` — the form TypeScript-trained models expect.
    """
    if node == NULL:
        return (3, "")
    if isinstance(node, Primitive):
        return (0, node.name)
    if isinstance(node, EnumNode):
        return (0, canonical(node))
    if isinstance(node, ArrayNode):
        return (1, canonical(node))
    return (2, canonical(node))


def to_dict(node: Node) -> dict[str, Any]:
    """Convert ``node`` into a plain JSON-serialisable dictionary.

    This is the machine-readable form exposed as :attr:`jsonhaiku.Result.tree`.
    Every node becomes a dict with a ``kind`` discriminator, so consumers can
    walk the structure without importing jsonhaiku's classes.
    """
    if isinstance(node, Primitive):
        return {"kind": "primitive", "type": node.name}
    if isinstance(node, EnumNode):
        result: dict[str, Any] = {"kind": "enum", "values": list(node.values)}
        if node.frequencies is not None:
            result["frequencies"] = list(node.frequencies)
        return result
    if isinstance(node, ArrayNode):
        return {
            "kind": "array",
            "items": None if node.items is None else to_dict(node.items),
        }
    if isinstance(node, ObjectNode):
        return {
            "kind": "object",
            "fields": {
                key: {"type": to_dict(field.type), "optional": field.optional}
                for key, field in node.fields.items()
            },
        }
    return {"kind": "union", "members": [to_dict(member) for member in node.members]}
