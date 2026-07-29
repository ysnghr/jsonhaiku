"""MCP tool implementations wrapping the JsonHaiku explorer API.

Each function here is registered as an MCP tool on the FastMCP server.
All tools accept a ``session_id`` and delegate to the corresponding
:class:`~jsonhaiku.explorer.JsonHaiku` accessor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from jsonhaiku.explorer import JsonHaiku

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from jsonhaiku_mcp.sessions import SessionStore

_MAX_RESPONSE_BYTES = 200 * 1024 * 1024
_URL_TIMEOUT_S = 30


def register_tools(mcp: FastMCP, store: SessionStore) -> None:
    """Register all jsonhaiku tools on the given MCP server."""
    _register_load(mcp, store)
    _register_accessors(mcp, store)
    _register_unload(mcp, store)


def _register_load(mcp: FastMCP, store: SessionStore) -> None:
    """Register the jsonhaiku_load tool."""

    @mcp.tool(
        name="jsonhaiku_load",
        description=(
            "Load a JSON payload into memory and return a session ID. "
            "Pass a local file path, an HTTP/HTTPS URL, or inline JSON text. "
            "Use the returned session ID in all subsequent jsonhaiku tool calls. "
            "Call jsonhaiku_unload when you are done to free memory."
        ),
    )
    def jsonhaiku_load(source: str) -> str:
        """Load a JSON payload and return a session ID."""
        raw = _read_source(source)
        data = _parse_json(raw)
        explorer = JsonHaiku(data)
        session_id = store.create(explorer)
        overview = explorer.overview()
        return json.dumps(
            {"session_id": session_id, "overview": overview},
            ensure_ascii=False,
        )


def _register_accessors(mcp: FastMCP, store: SessionStore) -> None:
    """Register the accessor tools (overview, describe, sample, etc)."""

    @mcp.tool(
        name="jsonhaiku_overview",
        description=(
            "Return a high-level summary of a loaded JSON payload: "
            "root type, size, number of records, top-level keys, "
            "and the number of unique paths. Use this first to orient "
            "yourself before drilling into specific paths."
        ),
    )
    def jsonhaiku_overview(session_id: str) -> str:
        """Return the top-level overview of a session."""
        return json.dumps(_get(store, session_id).overview(), ensure_ascii=False)

    @mcp.tool(
        name="jsonhaiku_describe",
        description=(
            "Return the inferred type schema at a JSONPath. "
            "Use this before writing filtering or extraction code — "
            "it tells you what fields exist, what types they hold, "
            "and which are optional or always null. "
            "Supports $, .field, [N], and [*] path syntax."
        ),
    )
    def jsonhaiku_describe(
        session_id: str,
        path: str = "$",
        depth: int = 2,
    ) -> str:
        """Describe the schema at a path."""
        return json.dumps(
            _get(store, session_id).describe(path=path, depth=depth),
            ensure_ascii=False,
        )

    @mcp.tool(
        name="jsonhaiku_sample",
        description=(
            "Return representative sample values at a JSONPath. "
            "Samples are chosen to cover edge cases: typical records, "
            "nullable fields, and extreme outliers. "
            "Use this to see what real data looks like at a path."
        ),
    )
    def jsonhaiku_sample(
        session_id: str,
        path: str = "$",
        n: int = 3,
    ) -> str:
        """Return sample values at a path."""
        return json.dumps(
            _get(store, session_id).sample(path=path, n=n),
            ensure_ascii=False,
        )

    @mcp.tool(
        name="jsonhaiku_enum",
        description=(
            "List all unique values at a JSONPath, sorted by frequency. "
            "Use this to discover what distinct values a field takes — "
            "for example, all status codes, category names, or country codes. "
            "Returns up to 100 values with counts."
        ),
    )
    def jsonhaiku_enum(session_id: str, path: str) -> str:
        """List unique values at a path."""
        return json.dumps(_get(store, session_id).enum(path=path), ensure_ascii=False)

    @mcp.tool(
        name="jsonhaiku_stats",
        description=(
            "Return numeric and string statistics at a JSONPath: "
            "min, max, mean for numbers; min/max/average length for strings. "
            "Use this to understand value distributions without reading every record."
        ),
    )
    def jsonhaiku_stats(session_id: str, path: str) -> str:
        """Return statistics at a path."""
        return json.dumps(_get(store, session_id).stats(path=path), ensure_ascii=False)

    @mcp.tool(
        name="jsonhaiku_filter",
        description=(
            "Return records at a JSONPath that match a filter expression. "
            "The filter DSL supports: ==, !=, <, <=, >, >=, in, contains, and, or. "
            "Examples: \"status == 'active'\", \"age > 30 and name contains 'Smith'\". "
            "Use this to find specific records without scanning the full dataset."
        ),
    )
    def jsonhaiku_filter(session_id: str, path: str, where: str) -> str:
        """Filter records at a path."""
        return json.dumps(
            _get(store, session_id).filter(path=path, where=where),
            ensure_ascii=False,
        )

    @mcp.tool(
        name="jsonhaiku_search",
        description=(
            "Search for values containing a substring anywhere in the JSON tree. "
            "Optionally scope the search to a specific JSONPath. "
            "Returns matching paths and values. "
            "Use this when you know part of a value but not where it lives."
        ),
    )
    def jsonhaiku_search(session_id: str, value: str, path: str = "$") -> str:
        """Search for values containing a substring."""
        return json.dumps(
            _get(store, session_id).search(value_contains=value, path=path),
            ensure_ascii=False,
        )

    @mcp.tool(
        name="jsonhaiku_list_paths",
        description=(
            "List all observed JSONPaths in the loaded data, "
            "optionally filtered by depth. Use this to discover "
            "what paths are available before calling describe, sample, or stats."
        ),
    )
    def jsonhaiku_list_paths(session_id: str, max_depth: int = 3) -> str:
        """List available paths."""
        paths = _get(store, session_id).list_paths(max_depth=max_depth)
        return json.dumps({"paths": paths}, ensure_ascii=False)


def _register_unload(mcp: FastMCP, store: SessionStore) -> None:
    """Register the jsonhaiku_unload tool."""

    @mcp.tool(
        name="jsonhaiku_unload",
        description=(
            "Release the memory held by a session. "
            "Call this when you are done exploring a JSON payload. "
            "The session ID becomes invalid after this call."
        ),
    )
    def jsonhaiku_unload(session_id: str) -> str:
        """Unload a session."""
        removed = store.remove(session_id)
        if removed:
            return json.dumps({"status": "unloaded", "session_id": session_id})
        msg = f"Unknown or expired session: {session_id}"
        raise ValueError(msg)


def _get(store: SessionStore, session_id: str) -> JsonHaiku:
    """Retrieve an explorer, raising a clear error for invalid sessions."""
    try:
        return store.get(session_id)
    except KeyError:
        msg = f"Unknown or expired session: {session_id}"
        raise ValueError(msg) from None


def _read_source(source: str) -> str:
    """Read JSON text from a file path, URL, or inline string."""
    stripped = source.strip()
    if stripped.startswith(("http://", "https://")):
        return _fetch_url(stripped)
    if stripped.startswith(("{", "[", '"')) or stripped[:1].isdigit():
        return stripped
    return _read_file(stripped)


def _read_file(path_str: str) -> str:
    """Read a local JSON file."""
    path = Path(path_str)
    if not path.exists():
        msg = f"File not found: {path_str}"
        raise FileNotFoundError(msg)
    size = path.stat().st_size
    if size > _MAX_RESPONSE_BYTES:
        msg = f"File too large: {size:,} bytes (limit: {_MAX_RESPONSE_BYTES:,})"
        raise ValueError(msg)
    return path.read_text(encoding="utf-8")


def _fetch_url(url: str) -> str:
    """Fetch JSON from a URL with size and timeout limits."""
    with httpx.Client(timeout=_URL_TIMEOUT_S, follow_redirects=False) as client:
        response = client.get(url)
        response.raise_for_status()
    if len(response.content) > _MAX_RESPONSE_BYTES:
        msg = (
            f"Response too large: {len(response.content):,} bytes (limit: {_MAX_RESPONSE_BYTES:,})"
        )
        raise ValueError(msg)
    return response.text


def _parse_json(raw: str) -> object:
    """Parse JSON text, raising a clear error on failure."""
    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON: {exc}"
        raise ValueError(msg) from None
