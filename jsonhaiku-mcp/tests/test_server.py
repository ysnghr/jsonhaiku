"""Tests for the MCP server creation."""

from __future__ import annotations

from jsonhaiku_mcp.server import create_server


class TestCreateServer:
    def test_creates_server(self):
        server = create_server()
        assert server is not None

    def test_server_has_tools(self):
        server = create_server()
        tools = server._tool_manager.list_tools()
        names = {t.name for t in tools}
        assert "jsonhaiku_load" in names
        assert "jsonhaiku_unload" in names
        assert len(names) == 10

    def test_custom_ttl(self):
        server = create_server(ttl_s=60)
        assert server is not None

    def test_tool_descriptions_are_non_empty(self):
        server = create_server()
        tools = server._tool_manager.list_tools()
        for tool in tools:
            assert tool.description, f"{tool.name} has no description"
            assert len(tool.description) > 20, f"{tool.name} description too short"
