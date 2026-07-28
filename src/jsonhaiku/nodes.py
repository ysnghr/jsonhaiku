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
]
"""The scalar type names jsonhaiku can emit.

``number`` is the merge of ``integer`` and ``float`` (JSON draws no such
distinction), and ``unknown`` marks a value jsonhaiku could not describe.
"""


@dataclass(frozen=True, slots=True)
class Primitive:
    """A scalar type, such as ``integer`` or ``string``."""

    name: PrimitiveName


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

    # A mappingproxy cannot be pickled or deep-copied, and results are meant to
    # be cached and shipped between processes. Unwrap it on the way out and wrap
    # it again on the way back in.
    def __getstate__(self) -> dict[str, Field]:
        """Return picklable state: the fields as a plain dictionary."""
        return dict(self.fields)

    def __setstate__(self, state: dict[str, Field]) -> None:
        """Restore from :meth:`__getstate__`, re-freezing the field mapping."""
        object.__setattr__(self, "fields", _frozen_fields(state))


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


Node: TypeAlias = Primitive | ArrayNode | ObjectNode | UnionNode
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


def canonical(node: Node) -> str:
    """Return a compact, stable signature of ``node``.

    The signature is an implementation detail used for ordering and de-duplication;
    it is not part of the public output format. Two nodes have the same signature
    if and only if they describe the same type.
    """
    if isinstance(node, Primitive):
        return node.name
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
