"""Tests for the JsonHaiku progressive disclosure API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jsonhaiku import JsonHaiku

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def sessions() -> list[object]:
    payload: list[object] = json.loads(
        (FIXTURES / "conference_sessions.json").read_text(encoding="utf-8")
    )
    return payload


@pytest.fixture
def h(sessions: list[object]) -> JsonHaiku:
    return JsonHaiku(sessions)


class TestOverview:
    def test_root_kind(self, h: JsonHaiku) -> None:
        ov = h.overview()
        assert ov["root_kind"] == "array"

    def test_length(self, h: JsonHaiku) -> None:
        ov = h.overview()
        assert ov["length"] == 5

    def test_top_keys(self, h: JsonHaiku) -> None:
        ov = h.overview()
        assert "id" in ov["top_keys"]
        assert "title" in ov["top_keys"]
        assert "room" in ov["top_keys"]

    def test_total_size_bytes(self, h: JsonHaiku) -> None:
        ov = h.overview()
        assert ov["total_size_bytes"] > 0

    def test_unique_paths(self, h: JsonHaiku) -> None:
        ov = h.overview()
        assert ov["unique_paths"] > 10

    def test_object_root(self) -> None:
        h = JsonHaiku({"a": 1, "b": 2})
        ov = h.overview()
        assert ov["root_kind"] == "object"
        assert ov["top_keys"] == ["a", "b"]

    def test_scalar_root(self) -> None:
        h = JsonHaiku(42)
        ov = h.overview()
        assert ov["root_kind"] == "number"


class TestDescribe:
    def test_root_schema(self, h: JsonHaiku) -> None:
        result = h.describe(path="$")
        assert "schema" in result
        assert result["path"] == "$"

    def test_subpath(self, h: JsonHaiku) -> None:
        result = h.describe(path="$[*].room")
        assert "schema" in result
        assert result["path"] == "$[*].room"

    def test_specific_record(self, h: JsonHaiku) -> None:
        result = h.describe(path="$[0].room")
        assert "schema" in result

    def test_no_matches(self, h: JsonHaiku) -> None:
        result = h.describe(path="$.nonexistent")
        assert "error" in result

    def test_depth_control(self, h: JsonHaiku) -> None:
        result = h.describe(path="$", depth=1)
        assert result["depth"] == 1

    def test_tree_format(self, h: JsonHaiku) -> None:
        result = h.describe(path="$[0]", fmt="tree")
        assert "tree" in result
        assert isinstance(result["tree"], dict)


class TestSample:
    def test_sample_values(self, h: JsonHaiku) -> None:
        result = h.sample(path="$[*].room", n=2)
        assert result["total"] == 5
        assert result["returned"] == 2
        assert len(result["values"]) == 2

    def test_sample_truncation(self, h: JsonHaiku) -> None:
        result = h.sample(path="$[*]", n=2)
        assert result["truncated"] is True
        assert result["total"] == 5
        assert result["returned"] == 2

    def test_sample_all(self, h: JsonHaiku) -> None:
        result = h.sample(path="$[*]", n=100)
        assert result["truncated"] is False
        assert result["returned"] == 5

    def test_no_matches(self, h: JsonHaiku) -> None:
        result = h.sample(path="$.nope")
        assert "error" in result

    def test_value_has_path(self, h: JsonHaiku) -> None:
        result = h.sample(path="$[*].room", n=1)
        val = result["values"][0]
        assert "path" in val
        assert "value" in val


class TestEnum:
    def test_enum_values(self, h: JsonHaiku) -> None:
        result = h.enum(path="$[*].is_published")
        assert "values" in result
        assert result["path"] == "$[*].is_published"

    def test_truncation_fields(self, h: JsonHaiku) -> None:
        result = h.enum(path="$[*].id")
        assert "total_unique" in result
        assert "returned" in result
        assert "truncated" in result

    def test_no_matches(self, h: JsonHaiku) -> None:
        result = h.enum(path="$.missing")
        assert "error" in result

    def test_limit(self) -> None:
        data = [{"letter": chr(65 + i)} for i in range(26)]
        h = JsonHaiku(data)
        result = h.enum(path="$[*].letter", limit=5)
        assert result["returned"] == 5
        assert result["total_unique"] == 26
        assert result["truncated"] is True


class TestStats:
    def test_numeric_stats(self, h: JsonHaiku) -> None:
        result = h.stats(path="$[*].duration")
        assert "numeric" in result
        num = result["numeric"]
        assert "min" in num
        assert "max" in num
        assert "mean" in num
        assert "median" in num
        assert "unique_count" in num

    def test_string_stats(self, h: JsonHaiku) -> None:
        result = h.stats(path="$[*].title")
        assert "string" in result
        s = result["string"]
        assert "min_length" in s
        assert "max_length" in s
        assert "avg_length" in s
        assert "unique_count" in s

    def test_null_count(self, h: JsonHaiku) -> None:
        result = h.stats(path="$[*].parent_id")
        assert result["null_count"] >= 0

    def test_no_matches(self, h: JsonHaiku) -> None:
        result = h.stats(path="$.nope")
        assert "error" in result

    def test_total(self, h: JsonHaiku) -> None:
        result = h.stats(path="$[*].id")
        assert result["total"] == 5


class TestSearch:
    def test_search_string_match(self, h: JsonHaiku) -> None:
        result = h.search(value_contains="Plenary", path="$[*]")
        assert result["returned"] >= 1
        assert any("Plenary" in str(r["value"]) for r in result["results"])

    def test_search_case_insensitive(self, h: JsonHaiku) -> None:
        result = h.search(value_contains="hall", path="$[*]")
        assert result["returned"] >= 1

    def test_search_no_results(self, h: JsonHaiku) -> None:
        result = h.search(value_contains="ZZZZZ_NONEXISTENT", path="$[*]")
        assert result["returned"] == 0

    def test_search_limit(self) -> None:
        data = [{"text": f"match {i}"} for i in range(100)]
        h = JsonHaiku(data)
        result = h.search(value_contains="match", path="$[*]", limit=5)
        assert result["returned"] == 5
        assert result["truncated"] is True

    def test_search_truncation_transparent(self) -> None:
        data = [{"text": f"item {i}"} for i in range(10)]
        h = JsonHaiku(data)
        result = h.search(value_contains="item", path="$[*]", limit=3)
        assert result["truncated"] is True
        assert result["returned"] == 3


class TestFilter:
    def test_equality_filter(self, h: JsonHaiku) -> None:
        result = h.filter(path="$[*]", where="is_published == true")
        assert result["total_matched"] >= 1
        for r in result["results"]:
            assert r["value"]["is_published"] is True

    def test_numeric_filter(self, h: JsonHaiku) -> None:
        result = h.filter(path="$[*]", where="duration > 60")
        for r in result["results"]:
            assert r["value"]["duration"] > 60

    def test_nested_path_filter(self, h: JsonHaiku) -> None:
        result = h.filter(path="$[*]", where="room.name == 'HALL A'")
        for r in result["results"]:
            assert r["value"]["room"]["name"] == "HALL A"

    def test_in_filter(self, h: JsonHaiku) -> None:
        result = h.filter(
            path="$[*]",
            where="session_type.name in ['Plenary', 'Symposium']",
        )
        for r in result["results"]:
            assert r["value"]["session_type"]["name"] in ("Plenary", "Symposium")

    def test_contains_filter(self, h: JsonHaiku) -> None:
        result = h.filter(path="$[*]", where="title contains 'Plenary'")
        for r in result["results"]:
            assert "Plenary" in r["value"]["title"]

    def test_and_filter(self, h: JsonHaiku) -> None:
        result = h.filter(
            path="$[*]",
            where="is_published == true and duration > 30",
        )
        for r in result["results"]:
            assert r["value"]["is_published"] is True
            assert r["value"]["duration"] > 30

    def test_no_matches(self, h: JsonHaiku) -> None:
        result = h.filter(path="$[*]", where="duration > 99999")
        assert result["total_matched"] == 0

    def test_no_path_matches(self, h: JsonHaiku) -> None:
        result = h.filter(path="$.nope", where="x == 1")
        assert "error" in result

    def test_limit(self) -> None:
        data = [{"val": i} for i in range(100)]
        h = JsonHaiku(data)
        result = h.filter(path="$[*]", where="val >= 0", limit=5)
        assert result["returned"] == 5
        assert result["truncated"] is True

    def test_result_paths_are_concrete(self, h: JsonHaiku) -> None:
        result = h.filter(path="$[*]", where="is_published == true")
        for r in result["results"]:
            assert r["path"].startswith("$[")
            assert "[*]" not in r["path"]


class TestListPaths:
    def test_all_paths(self, h: JsonHaiku) -> None:
        paths = h.list_paths()
        assert "$" in paths
        assert "$[*]" in paths
        assert len(paths) > 5

    def test_min_depth(self, h: JsonHaiku) -> None:
        paths = h.list_paths(min_depth=2)
        assert "$" not in paths
        assert "$[*]" not in paths

    def test_max_depth(self, h: JsonHaiku) -> None:
        paths = h.list_paths(max_depth=1)
        for p in paths:
            assert p.count(".") + p.count("[*]") <= 1 or p == "$"

    def test_min_and_max_depth(self, h: JsonHaiku) -> None:
        paths = h.list_paths(min_depth=1, max_depth=2)
        assert "$" not in paths
        assert all(p != "$" for p in paths)

    def test_paths_are_sorted(self, h: JsonHaiku) -> None:
        paths = h.list_paths()
        assert paths == sorted(paths)


class TestDepthControl:
    def test_depth_zero(self) -> None:
        data = {"nested": {"deep": {"deeper": 1}}}
        h = JsonHaiku(data)
        result = h.describe(path="$", depth=0)
        assert result["depth"] == 0

    def test_depth_one(self) -> None:
        data = [{"a": {"b": {"c": 1}}}]
        h = JsonHaiku(data)
        result = h.describe(path="$", depth=1)
        assert result["depth"] == 1

    def test_depth_none(self) -> None:
        data = [{"a": {"b": 1}}]
        h = JsonHaiku(data)
        result = h.describe(path="$", depth=None)
        assert result["depth"] is None


class TestTruncation:
    def test_enum_truncation(self) -> None:
        data = [{"val": i} for i in range(200)]
        h = JsonHaiku(data)
        result = h.enum(path="$[*].val", limit=50)
        assert result["truncated"] is True
        assert result["total_unique"] == 200
        assert result["returned"] == 50

    def test_no_truncation(self) -> None:
        data = [{"val": i} for i in range(5)]
        h = JsonHaiku(data)
        result = h.enum(path="$[*].val")
        assert result["truncated"] is False
        assert result["total_unique"] == 5
        assert result["returned"] == 5

    def test_search_truncation(self) -> None:
        data = [{"text": f"match {i}"} for i in range(100)]
        h = JsonHaiku(data)
        result = h.search(value_contains="match", path="$[*]", limit=10)
        assert result["truncated"] is True
        assert result["returned"] == 10

    def test_filter_truncation(self) -> None:
        data = [{"val": 1} for _ in range(200)]
        h = JsonHaiku(data)
        result = h.filter(path="$[*]", where="val == 1", limit=50)
        assert result["truncated"] is True
        assert result["returned"] == 50


class TestEdgeCases:
    def test_empty_list(self) -> None:
        h = JsonHaiku([])
        ov = h.overview()
        assert ov["root_kind"] == "array"
        assert ov["length"] == 0

    def test_scalar_value(self) -> None:
        h = JsonHaiku(42)
        ov = h.overview()
        assert ov["root_kind"] == "number"

    def test_null_value(self) -> None:
        h = JsonHaiku(None)
        ov = h.overview()
        assert ov["root_kind"] == "null"

    def test_string_value(self) -> None:
        h = JsonHaiku("hello")
        ov = h.overview()
        assert ov["root_kind"] == "string"

    def test_boolean_value(self) -> None:
        h = JsonHaiku(True)
        ov = h.overview()
        assert ov["root_kind"] == "boolean"
