"""The object :func:`jsonhaiku.describe` hands back.

A :class:`Result` is a frozen wrapper around one type tree that knows how to
render itself. Inference happens once, up front; renderings are produced on
access, so asking for a format you never use costs nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Any

from jsonhaiku.nodes import canonical, to_dict
from jsonhaiku.render import render_compact
from jsonhaiku.schema import to_json_schema

if TYPE_CHECKING:
    from jsonhaiku.nodes import Node

__all__ = ["Result"]

_REPR_SIGNATURE_LIMIT = 60


@dataclass(frozen=True)
class Result:
    """The description of a JSON value, in every format jsonhaiku can render.

    Frozen on purpose: results are routinely cached and passed around, and a
    description that could change under you would be a poor thing to build a
    prompt from.

    Attributes:
        root: The type tree. Stable across versions in *meaning*, but its Python
            representation is internal — walk :attr:`tree` if you need to
            consume it programmatically.
    """

    root: Node

    @cached_property
    def compact(self) -> str:
        """The compact type map: the default, LLM-facing rendering."""
        return render_compact(self.root)

    @property
    def tree(self) -> dict[str, Any]:
        """The type tree as plain, JSON-serialisable dictionaries.

        A fresh dictionary on every access, so callers may mutate it freely.
        """
        return to_dict(self.root)

    @property
    def schema(self) -> dict[str, Any]:
        """A JSON Schema (Draft 2020-12) document describing the value.

        A fresh dictionary on every access, so callers may add a ``title``,
        ``$id`` or anything else without affecting later reads.
        """
        return to_json_schema(self.root)

    def __str__(self) -> str:
        """Return the compact rendering, so ``print(result)`` does what you want."""
        return self.compact

    def __repr__(self) -> str:
        """Return a short summary; the full tree would flood a terminal."""
        signature = canonical(self.root)
        if len(signature) > _REPR_SIGNATURE_LIMIT:
            signature = signature[:_REPR_SIGNATURE_LIMIT] + "…"
        return f"Result({signature})"
