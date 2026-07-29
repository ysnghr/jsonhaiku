"""The object :func:`jsonhaiku.describe` hands back.

A :class:`Result` is a frozen wrapper around one type tree that knows how to
render itself. Inference happens once, up front; renderings are produced on
access, so asking for a format you never use costs nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any

from jsonhaiku.config import Config
from jsonhaiku.nodes import canonical, to_dict
from jsonhaiku.renderers.compact import render_compact
from jsonhaiku.renderers.json_schema import render_json_schema
from jsonhaiku.renderers.typescript import render_typescript
from jsonhaiku.renderers.yaml import render_yaml
from jsonhaiku.schema import to_json_schema

if TYPE_CHECKING:
    from jsonhaiku.nodes import Node

__all__ = ["Result"]

_REPR_SIGNATURE_LIMIT = 60

_FORMAT_ALIASES: dict[str, str] = {
    "ts": "typescript",
    "json-schema": "json_schema",
    "jsonschema": "json_schema",
    "yml": "yaml",
}


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
        config: The configuration used during inference.
        samples: Representative records selected from the input data, or an
            empty tuple when no samples were requested.
    """

    root: Node
    config: Config = field(default_factory=Config)
    samples: tuple[Any, ...] = ()

    # ------------------------------------------------------------------
    # Rendering — each format is a thin wrapper over its renderer module
    # ------------------------------------------------------------------

    @cached_property
    def compact(self) -> str:
        """The compact type map: the default, LLM-facing rendering."""
        return render_compact(self.root, max_depth=self.config.max_depth)

    def typescript(self, root_name: str = "Root") -> str:
        """TypeScript interface declaration."""
        return render_typescript(
            self.root,
            root_name=root_name,
            max_depth=self.config.max_depth,
        )

    @cached_property
    def json_schema(self) -> dict[str, Any]:
        """A JSON Schema (Draft 2020-12) document describing the value."""
        return render_json_schema(self.root, max_depth=self.config.max_depth)

    @cached_property
    def yaml(self) -> str:
        """YAML-style type description."""
        return render_yaml(self.root, max_depth=self.config.max_depth)

    def render(
        self,
        fmt: str = "compact",
        *,
        root_name: str = "Root",
        max_depth: int | None = None,
    ) -> str:
        """Render the type tree in the requested format.

        Args:
            fmt: One of ``"compact"``, ``"typescript"``, ``"json_schema"``,
                ``"yaml"``. Common aliases are accepted (``"ts"``, ``"yml"``).
            root_name: Interface name for the TypeScript format.
            max_depth: Override the config's ``max_depth`` for this render.

        Returns:
            The rendered string. For ``json_schema`` the dict is serialised as
            indented JSON.
        """
        effective_depth = max_depth if max_depth is not None else self.config.max_depth
        fmt = _FORMAT_ALIASES.get(fmt, fmt)

        if fmt == "compact":
            return render_compact(self.root, max_depth=effective_depth)
        if fmt == "typescript":
            return render_typescript(
                self.root,
                root_name=root_name,
                max_depth=effective_depth,
            )
        if fmt == "json_schema":
            schema = render_json_schema(self.root, max_depth=effective_depth)
            return json.dumps(schema, indent=2, ensure_ascii=False)
        if fmt == "yaml":
            return render_yaml(self.root, max_depth=effective_depth)

        msg = f"unknown format {fmt!r}; choose from compact, typescript, json_schema, yaml"
        raise ValueError(msg)

    # ------------------------------------------------------------------
    # Samples
    # ------------------------------------------------------------------

    def render_with_samples(
        self,
        fmt: str = "compact",
        *,
        indent: int = 2,
        root_name: str = "Root",
    ) -> str:
        """Render the type description with selected samples appended.

        Args:
            fmt: Output format for the type description.
            indent: JSON indentation for sample values.
            root_name: Interface name for TypeScript format.

        Returns:
            The type description followed by commented sample records.
        """
        schema_text = self.render(fmt, root_name=root_name)
        if not self.samples:
            return schema_text

        parts = [schema_text, "", "// Samples:"]
        for i, sample in enumerate(self.samples):
            reason = getattr(sample, "reason", "")
            value = getattr(sample, "value", sample)
            parts.append(f"// [{i}] {reason}")
            parts.append(json.dumps(value, indent=indent, ensure_ascii=False))
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def token_count(
        self,
        *,
        model: str = "gpt-4",
        fmt: str = "compact",
        root_name: str = "Root",
    ) -> int:
        """Count tokens for a rendered format.

        Args:
            model: Model name or tiktoken encoding name. Anthropic model names
                use ``cl100k_base`` as a close proxy (documented ±10%% error).
            fmt: Format to count tokens for.
            root_name: Interface name when ``fmt`` is ``"typescript"``.

        Returns:
            Token count.

        Raises:
            ImportError: If ``tiktoken`` is not installed. Install the
                ``tokens`` extra: ``pip install jsonhaiku[tokens]``.
        """
        from jsonhaiku.tokens import count_tokens  # noqa: PLC0415

        text = self.render(fmt, root_name=root_name)
        return count_tokens(text, model=model)

    def token_breakdown(
        self,
        *,
        model: str = "gpt-4",
        root_name: str = "Root",
    ) -> dict[str, int]:
        """Return token counts for all four formats side by side.

        Args:
            model: Model name or tiktoken encoding name.
            root_name: Interface name for the TypeScript format.

        Returns:
            A dict mapping format names to token counts.
        """
        from jsonhaiku.tokens import count_tokens  # noqa: PLC0415

        return {
            "compact": count_tokens(
                self.render("compact"),
                model=model,
            ),
            "typescript": count_tokens(
                self.render("typescript", root_name=root_name),
                model=model,
            ),
            "json_schema": count_tokens(
                self.render("json_schema"),
                model=model,
            ),
            "yaml": count_tokens(
                self.render("yaml"),
                model=model,
            ),
        }

    # ------------------------------------------------------------------
    # Backward-compatible accessors
    # ------------------------------------------------------------------

    @property
    def tree(self) -> dict[str, Any]:
        """The type tree as plain, JSON-serialisable dictionaries.

        A fresh dictionary on every access, so callers may mutate it freely.
        """
        return to_dict(self.root)

    @property
    def schema(self) -> dict[str, Any]:
        """A JSON Schema (Draft 2020-12) document describing the value.

        Alias for :attr:`json_schema`, kept for backward compatibility.
        A fresh dictionary on every access, so callers may add a ``title``,
        ``$id`` or anything else without affecting later reads.
        """
        return to_json_schema(self.root)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the compact rendering, so ``print(result)`` does what you want."""
        return self.compact

    def __repr__(self) -> str:
        """Return a short summary; the full tree would flood a terminal."""
        signature = canonical(self.root)
        if len(signature) > _REPR_SIGNATURE_LIMIT:
            signature = signature[:_REPR_SIGNATURE_LIMIT] + "…"
        return f"Result({signature})"
