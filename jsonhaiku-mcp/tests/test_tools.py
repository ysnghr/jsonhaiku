"""Tests for the MCP tool implementations."""

from __future__ import annotations

import json

import pytest
from jsonhaiku.explorer import JsonHaiku
from mcp.server.fastmcp import FastMCP

from jsonhaiku_mcp.sessions import SessionStore
from jsonhaiku_mcp.tools import (
    _parse_json,
    _read_file,
    _read_source,
    register_tools,
)

SAMPLE_DATA = [
    {"id": 1, "name": "alice", "status": "active"},
    {"id": 2, "name": "bob", "status": "active"},
    {"id": 3, "name": "charlie", "status": "inactive"},
]


@pytest.fixture
def store():
    return SessionStore()


@pytest.fixture
def session_id(store):
    return store.create(JsonHaiku(SAMPLE_DATA))


class TestReadSource:
    def test_inline_object(self):
        assert _read_source('{"a": 1}') == '{"a": 1}'

    def test_inline_array(self):
        assert _read_source("[1, 2, 3]") == "[1, 2, 3]"

    def test_inline_string(self):
        assert _read_source('"hello"') == '"hello"'

    def test_inline_number(self):
        assert _read_source("42") == "42"

    def test_file_path(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('{"x": 1}', encoding="utf-8")
        assert _read_source(str(p)) == '{"x": 1}'

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="File not found"):
            _read_source("/nonexistent/file.json")


class TestReadFile:
    def test_reads_utf8(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('{"key": "müzik"}', encoding="utf-8")
        assert "müzik" in _read_file(str(p))

    def test_size_limit(self, tmp_path):
        p = tmp_path / "big.json"
        p.write_bytes(b"x" * (200 * 1024 * 1024 + 1))
        with pytest.raises(ValueError, match="too large"):
            _read_file(str(p))


class TestParseJson:
    def test_valid(self):
        assert _parse_json("[1, 2]") == [1, 2]

    def test_invalid(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            _parse_json("{not json")


class TestToolRegistration:
    def test_all_tools_registered(self):
        mcp = FastMCP("test")
        store = SessionStore()
        register_tools(mcp, store)

        tool_names = {t.name for t in mcp._tool_manager.list_tools()}
        expected = {
            "jsonhaiku_load",
            "jsonhaiku_overview",
            "jsonhaiku_describe",
            "jsonhaiku_sample",
            "jsonhaiku_enum",
            "jsonhaiku_stats",
            "jsonhaiku_filter",
            "jsonhaiku_search",
            "jsonhaiku_list_paths",
            "jsonhaiku_unload",
        }
        assert tool_names == expected


class TestToolLoad:
    def test_load_inline(self):
        mcp = FastMCP("test")
        store = SessionStore()
        register_tools(mcp, store)

        tool = mcp._tool_manager._tools["jsonhaiku_load"]
        result_str = tool.fn(source='[{"id": 1}]')
        result = json.loads(result_str)
        assert "session_id" in result
        assert result["session_id"].startswith("js_")
        assert "overview" in result

    def test_load_file(self, tmp_path):
        mcp = FastMCP("test")
        store = SessionStore()
        register_tools(mcp, store)

        p = tmp_path / "data.json"
        p.write_text('[{"id": 1}]', encoding="utf-8")

        tool = mcp._tool_manager._tools["jsonhaiku_load"]
        result_str = tool.fn(source=str(p))
        result = json.loads(result_str)
        assert result["session_id"].startswith("js_")

    def test_load_missing_file(self):
        mcp = FastMCP("test")
        store = SessionStore()
        register_tools(mcp, store)

        tool = mcp._tool_manager._tools["jsonhaiku_load"]
        with pytest.raises(FileNotFoundError, match="File not found"):
            tool.fn(source="/nonexistent/path.json")

    def test_load_invalid_inline_json(self):
        mcp = FastMCP("test")
        store = SessionStore()
        register_tools(mcp, store)

        tool = mcp._tool_manager._tools["jsonhaiku_load"]
        with pytest.raises(ValueError, match="Invalid JSON"):
            tool.fn(source="{not json")


class TestToolAccessors:
    @pytest.fixture
    def mcp_with_session(self, tmp_path):
        mcp = FastMCP("test")
        store = SessionStore()
        register_tools(mcp, store)

        p = tmp_path / "data.json"
        p.write_text(json.dumps(SAMPLE_DATA), encoding="utf-8")

        load_tool = mcp._tool_manager._tools["jsonhaiku_load"]
        result = json.loads(load_tool.fn(source=str(p)))
        return mcp, result["session_id"]

    def test_overview(self, mcp_with_session):
        mcp, sid = mcp_with_session
        tool = mcp._tool_manager._tools["jsonhaiku_overview"]
        result = json.loads(tool.fn(session_id=sid))
        assert result["root_kind"] == "array"

    def test_describe(self, mcp_with_session):
        mcp, sid = mcp_with_session
        tool = mcp._tool_manager._tools["jsonhaiku_describe"]
        result = json.loads(tool.fn(session_id=sid, path="$", depth=2))
        assert "schema" in result

    def test_sample(self, mcp_with_session):
        mcp, sid = mcp_with_session
        tool = mcp._tool_manager._tools["jsonhaiku_sample"]
        result = json.loads(tool.fn(session_id=sid, path="$[*]", n=2))
        assert isinstance(result, dict)

    def test_enum(self, mcp_with_session):
        mcp, sid = mcp_with_session
        tool = mcp._tool_manager._tools["jsonhaiku_enum"]
        result = json.loads(tool.fn(session_id=sid, path="$[*].status"))
        assert "values" in result

    def test_stats(self, mcp_with_session):
        mcp, sid = mcp_with_session
        tool = mcp._tool_manager._tools["jsonhaiku_stats"]
        result = json.loads(tool.fn(session_id=sid, path="$[*].id"))
        assert "path" in result

    def test_filter(self, mcp_with_session):
        mcp, sid = mcp_with_session
        tool = mcp._tool_manager._tools["jsonhaiku_filter"]
        result = json.loads(tool.fn(session_id=sid, path="$[*]", where="status == 'active'"))
        assert "results" in result
        assert result["total_matched"] == 2

    def test_search(self, mcp_with_session):
        mcp, sid = mcp_with_session
        tool = mcp._tool_manager._tools["jsonhaiku_search"]
        result = json.loads(tool.fn(session_id=sid, value="alice", path="$"))
        assert "results" in result

    def test_list_paths(self, mcp_with_session):
        mcp, sid = mcp_with_session
        tool = mcp._tool_manager._tools["jsonhaiku_list_paths"]
        result = json.loads(tool.fn(session_id=sid, max_depth=3))
        assert "paths" in result
        assert len(result["paths"]) > 0

    def test_invalid_session_id(self, mcp_with_session):
        mcp, _ = mcp_with_session
        tool = mcp._tool_manager._tools["jsonhaiku_overview"]
        with pytest.raises(ValueError, match="Unknown or expired"):
            tool.fn(session_id="js_nonexist")


class TestToolUnload:
    def test_unload_existing(self):
        mcp = FastMCP("test")
        store = SessionStore()
        register_tools(mcp, store)

        load_tool = mcp._tool_manager._tools["jsonhaiku_load"]
        result = json.loads(load_tool.fn(source='[{"id": 1}]'))
        sid = result["session_id"]

        unload_tool = mcp._tool_manager._tools["jsonhaiku_unload"]
        result = json.loads(unload_tool.fn(session_id=sid))
        assert result["status"] == "unloaded"

        overview_tool = mcp._tool_manager._tools["jsonhaiku_overview"]
        with pytest.raises(ValueError, match="Unknown or expired"):
            overview_tool.fn(session_id=sid)

    def test_unload_nonexistent(self):
        mcp = FastMCP("test")
        store = SessionStore()
        register_tools(mcp, store)

        unload_tool = mcp._tool_manager._tools["jsonhaiku_unload"]
        with pytest.raises(ValueError, match="Unknown or expired"):
            unload_tool.fn(session_id="js_nonexist")
