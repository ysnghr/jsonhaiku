"""MCP server entry point.

Run with ``jsonhaiku-mcp`` (installed) or ``python -m jsonhaiku_mcp.server``.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from jsonhaiku_mcp.sessions import SessionStore
from jsonhaiku_mcp.tools import register_tools

_SERVER_NAME = "jsonhaiku"


def create_server(*, ttl_s: float = 3600) -> FastMCP:
    """Create and configure the MCP server.

    Args:
        ttl_s: Session time-to-live in seconds.

    Returns:
        A configured FastMCP server ready to run.
    """
    mcp = FastMCP(
        _SERVER_NAME,
        instructions=(
            "jsonhaiku lets you explore large JSON payloads without reading them in full. "
            "Start by calling jsonhaiku_load with a file path, URL, or inline JSON. "
            "Use the returned session_id with the other tools to inspect structure, "
            "sample values, filter records, and more. "
            "Call jsonhaiku_unload when done."
        ),
    )
    store = SessionStore(ttl_s=ttl_s)
    register_tools(mcp, store)
    return mcp


def main() -> None:
    """Run the MCP server over stdio."""
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
