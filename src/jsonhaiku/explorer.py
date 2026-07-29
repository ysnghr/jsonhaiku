"""Progressive disclosure API — explore a JSON payload one path at a time.

A :class:`JsonHaiku` wraps a parsed JSON value and its inferred description,
exposing seven path-scoped accessors that return compact, LLM-friendly dicts.
Each response echoes the queried path and reports any truncation.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from typing import IO, TYPE_CHECKING, Any

from jsonhaiku.config import Config
from jsonhaiku.core import describe
from jsonhaiku.filter_dsl import evaluate as filter_evaluate
from jsonhaiku.path import parse_path, resolve, resolve_paths

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["JsonHaiku"]

_DEFAULT_DEPTH = 2
_DEFAULT_ENUM_LIMIT = 100
_DEFAULT_SEARCH_LIMIT = 50
_DEFAULT_FILTER_LIMIT = 100
_DEFAULT_SAMPLE_COUNT = 3


@dataclass
class JsonHaiku:
    """Stateful explorer for interactive, path-scoped JSON inspection.

    Build one with ``JsonHaiku(data)`` and call its accessors to explore
    the payload incrementally — ideal for agentic loops where each step
    asks a targeted question rather than consuming the full schema.

    Args:
        data: Any JSON value — a dict, list, or scalar.
        config: Optional configuration forwarded to :func:`describe`.
    """

    _data: object
    _config: Config
    _path_index: dict[str, list[object]] = field(repr=False)
    _size_bytes: int
    _stream_result: Any = field(default=None, repr=False)

    def __init__(self, data: object, config: Config | None = None) -> None:
        """Index *data* for interactive exploration."""
        self._data = data
        self._config = config or Config(track_cardinality=True)
        self._path_index = resolve_paths(data)
        self._size_bytes = len(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        self._stream_result = None

    @classmethod
    def from_stream(
        cls,
        stream: IO[bytes],
        *,
        config: Config | None = None,
        memory_budget_mb: int = 500,
        reservoir_k: int = 100,
        seed: int | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> JsonHaiku:
        """Create a JsonHaiku from a streaming JSON source.

        Args:
            stream: Binary stream containing JSON data.
            config: Optional configuration for inference.
            memory_budget_mb: Soft memory budget in megabytes.
            reservoir_k: Number of sample records to keep.
            seed: Random seed for reproducible sampling.
            on_progress: Callback ``(bytes_read, records_seen)``.

        Returns:
            A JsonHaiku explorer backed by streaming results.
        """
        from jsonhaiku.streaming import stream_ingest  # noqa: PLC0415

        result = stream_ingest(
            stream,
            config=config,
            memory_budget_mb=memory_budget_mb,
            reservoir_k=reservoir_k,
            seed=seed,
            on_progress=on_progress,
        )

        samples = result.samples
        instance = cls(samples, config=result.config)
        instance._stream_result = result
        instance._size_bytes = result.bytes_read
        return instance

    def overview(self) -> dict[str, Any]:
        """Return a top-level orientation summary.

        The response tells the agent what kind of value the root is,
        how large it is, and what the top-level keys are — enough to
        decide which path to drill into next.
        """
        if self._stream_result is not None:
            return self._streamed_overview()

        root_kind = _kind_of(self._data)
        result: dict[str, Any] = {
            "root_kind": root_kind,
            "total_size_bytes": self._size_bytes,
            "unique_paths": len(self._path_index),
        }

        if isinstance(self._data, list | tuple):
            result["length"] = len(self._data)
            if self._data and isinstance(self._data[0], dict):
                result["top_keys"] = list(self._data[0].keys())
        elif isinstance(self._data, dict):
            result["top_keys"] = list(self._data.keys())

        return result

    def _streamed_overview(self) -> dict[str, Any]:
        """Overview for stream-ingested data."""
        from jsonhaiku.nodes import ArrayNode, ObjectNode  # noqa: PLC0415

        sr = self._stream_result
        root = sr.root
        root_kind = (
            "array"
            if isinstance(root, ArrayNode)
            else ("object" if isinstance(root, ObjectNode) else "scalar")
        )
        result: dict[str, Any] = {
            "root_kind": root_kind,
            "total_size_bytes": sr.bytes_read,
            "records_seen": sr.records_seen,
            "unique_paths": len(sr.stats) if sr.stats else len(self._path_index),
            "approximate": sr.approximate,
        }
        if isinstance(root, ArrayNode) and isinstance(root.items, ObjectNode):
            result["top_keys"] = list(root.items.fields.keys())
        elif sr.samples and isinstance(sr.samples[0], dict):
            result["top_keys"] = list(sr.samples[0].keys())
        if sr.warnings:
            result["warnings"] = sr.warnings
        return result

    def _streamed_describe(
        self,
        *,
        depth: int | None,
        fmt: str,
    ) -> dict[str, Any]:
        """Describe using the pre-computed stream root."""
        from jsonhaiku.nodes import to_dict  # noqa: PLC0415
        from jsonhaiku.renderers.compact import render_compact  # noqa: PLC0415

        root = self._stream_result.root
        if fmt == "tree":
            return {"path": "$", "depth": depth, "tree": to_dict(root)}
        schema = render_compact(root, max_depth=depth)
        result: dict[str, Any] = {"path": "$", "depth": depth, "schema": schema}
        if self._stream_result.approximate:
            result["approximate"] = True
        return result

    def describe(
        self,
        path: str = "$",
        *,
        depth: int | None = _DEFAULT_DEPTH,
        fmt: str = "compact",
    ) -> dict[str, Any]:
        """Return the inferred schema at *path*.

        Args:
            path: JSONPath to describe (e.g. ``$[*].room``).
            depth: Max nesting depth in the output. ``None`` for unlimited.
            fmt: Output format — ``"compact"`` (default) or ``"tree"``.
        """
        if self._stream_result is not None and path == "$":
            return self._streamed_describe(depth=depth, fmt=fmt)

        matches = resolve(self._data, path)
        if not matches:
            return {"path": path, "error": "no matches"}

        values = [m.value for m in matches]
        cfg = Config(
            max_depth=depth,
            detect_content_types=self._config.detect_content_types,
            track_cardinality=self._config.track_cardinality,
        )
        result_obj = describe(values if len(values) > 1 else values[0], config=cfg)

        if fmt == "tree":
            return {"path": path, "depth": depth, "tree": result_obj.tree}

        return {"path": path, "depth": depth, "schema": result_obj.compact}

    def sample(
        self,
        path: str = "$",
        *,
        n: int = _DEFAULT_SAMPLE_COUNT,
    ) -> dict[str, Any]:
        """Return *n* representative values at *path*.

        Args:
            path: JSONPath to sample from.
            n: Number of samples to return.
        """
        matches = resolve(self._data, path)
        if not matches:
            return {"path": path, "error": "no matches"}

        total = len(matches)
        selected = matches[:n] if n < total else matches
        truncated = n < total

        return {
            "path": path,
            "total": total,
            "returned": len(selected),
            "truncated": truncated,
            "values": [{"path": m.path, "value": m.value} for m in selected],
        }

    def enum(
        self,
        path: str,
        *,
        limit: int = _DEFAULT_ENUM_LIMIT,
    ) -> dict[str, Any]:
        """Return unique values at *path*, sorted by frequency.

        Args:
            path: JSONPath whose values to enumerate.
            limit: Maximum number of unique values to return.
        """
        matches = resolve(self._data, path)
        if not matches:
            return {"path": path, "error": "no matches"}

        freq: dict[str, int] = {}
        for m in matches:
            key = json.dumps(m.value, ensure_ascii=False, sort_keys=True)
            freq[key] = freq.get(key, 0) + 1

        sorted_items = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
        total_unique = len(sorted_items)
        truncated = total_unique > limit
        returned_items = sorted_items[:limit]

        values = [json.loads(k) for k, _ in returned_items]

        return {
            "path": path,
            "values": values,
            "total_unique": total_unique,
            "returned": len(values),
            "truncated": truncated,
        }

    def stats(self, path: str) -> dict[str, Any]:
        """Return numeric or string statistics for values at *path*.

        Args:
            path: JSONPath to compute statistics for.
        """
        matches = resolve(self._data, path)
        if not matches:
            return {"path": path, "error": "no matches"}

        values = [m.value for m in matches]
        numerics = [v for v in values if isinstance(v, int | float) and not isinstance(v, bool)]
        strings = [v for v in values if isinstance(v, str)]

        result: dict[str, Any] = {
            "path": path,
            "total": len(values),
            "null_count": sum(1 for v in values if v is None),
        }

        if numerics:
            result["numeric"] = {
                "min": min(numerics),
                "max": max(numerics),
                "mean": round(statistics.mean(numerics), 2),
                "median": statistics.median(numerics),
                "unique_count": len(set(numerics)),
            }

        if strings:
            lengths = [len(s) for s in strings]
            result["string"] = {
                "min_length": min(lengths),
                "max_length": max(lengths),
                "avg_length": round(statistics.mean(lengths), 1),
                "unique_count": len(set(strings)),
            }

        return result

    def search(
        self,
        value_contains: str,
        *,
        path: str = "$",
        limit: int = _DEFAULT_SEARCH_LIMIT,
    ) -> dict[str, Any]:
        """Find values containing a substring at *path*.

        Args:
            value_contains: Substring to search for (case-insensitive).
            path: JSONPath scope to search within.
            limit: Maximum number of results.
        """
        matches = resolve(self._data, path)
        needle = value_contains.lower()
        hits: list[dict[str, Any]] = []

        for m in matches:
            if isinstance(m.value, str) and needle in m.value.lower():
                hits.append({"path": m.path, "value": m.value})
            elif isinstance(m.value, dict | list):
                _search_recursive(m.value, m.path, needle, hits, limit)
            if len(hits) >= limit:
                break

        truncated = len(hits) >= limit
        returned = hits[:limit]

        return {
            "path": path,
            "query": value_contains,
            "returned": len(returned),
            "truncated": truncated,
            "results": returned,
        }

    def filter(
        self,
        path: str,
        *,
        where: str,
        limit: int = _DEFAULT_FILTER_LIMIT,
    ) -> dict[str, Any]:
        """Return records at *path* that match the *where* expression.

        Args:
            path: JSONPath to filter (typically ``$[*]``).
            where: Filter expression using the safe DSL.
            limit: Maximum number of matching records.
        """
        matches = resolve(self._data, path)
        if not matches:
            return {"path": path, "where": where, "error": "no matches"}

        results: list[dict[str, Any]] = []
        for m in matches:
            if filter_evaluate(m.value, where):
                results.append({"path": m.path, "value": m.value})
            if len(results) >= limit:
                break

        total_matched = len(results)
        truncated = total_matched >= limit

        return {
            "path": path,
            "where": where,
            "total_matched": total_matched,
            "returned": len(results),
            "truncated": truncated,
            "results": results,
        }

    def list_paths(
        self,
        *,
        min_depth: int = 0,
        max_depth: int | None = None,
    ) -> list[str]:
        """Return all observed paths, filtered by depth.

        Args:
            min_depth: Minimum path depth (number of segments after ``$``).
            max_depth: Maximum path depth. ``None`` for unlimited.
        """
        paths: list[str] = []
        for p in sorted(self._path_index.keys()):
            depth = _path_depth(p)
            if depth < min_depth:
                continue
            if max_depth is not None and depth > max_depth:
                continue
            paths.append(p)
        return paths


_KIND_CHECKS: tuple[tuple[type | tuple[type, ...], str], ...] = (
    (bool, "boolean"),
    (int, "number"),
    (float, "number"),
    (str, "string"),
    (dict, "object"),
    ((list, tuple), "array"),
)


def _kind_of(value: object) -> str:
    if value is None:
        return "null"
    for types, kind in _KIND_CHECKS:
        if isinstance(value, types):
            return kind
    return "unknown"


def _path_depth(path: str) -> int:
    if path == "$":
        return 0
    segments = parse_path(path)
    return len(segments) - 1


def _search_recursive(
    value: object,
    path: str,
    needle: str,
    hits: list[dict[str, Any]],
    limit: int,
) -> None:
    if len(hits) >= limit:
        return
    if isinstance(value, str) and needle in value.lower():
        hits.append({"path": path, "value": value})
    elif isinstance(value, dict):
        for key, val in value.items():
            _search_recursive(val, f"{path}.{key}", needle, hits, limit)
    elif isinstance(value, list | tuple):
        for i, item in enumerate(value):
            _search_recursive(item, f"{path}[{i}]", needle, hits, limit)
