"""Tests for the JSONPath subset parser and resolver."""

from __future__ import annotations

import pytest

from jsonhaiku.path import parse_path, resolve, resolve_paths


class TestParsePath:
    def test_root_only(self) -> None:
        segs = parse_path("$")
        assert len(segs) == 1

    def test_root_field(self) -> None:
        segs = parse_path("$.name")
        assert len(segs) == 2

    def test_root_index(self) -> None:
        segs = parse_path("$[0]")
        assert len(segs) == 2

    def test_root_wildcard(self) -> None:
        segs = parse_path("$[*]")
        assert len(segs) == 2

    def test_deep_path(self) -> None:
        segs = parse_path("$[*].room.name")
        assert len(segs) == 4

    def test_empty_path_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            parse_path("")

    def test_invalid_syntax_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid path syntax"):
            parse_path("$[*]!!!")


class TestResolve:
    def test_root(self) -> None:
        data = {"a": 1}
        matches = resolve(data, "$")
        assert len(matches) == 1
        assert matches[0].value == {"a": 1}
        assert matches[0].path == "$"

    def test_field(self) -> None:
        data = {"name": "Alice"}
        matches = resolve(data, "$.name")
        assert len(matches) == 1
        assert matches[0].value == "Alice"
        assert matches[0].path == "$.name"

    def test_nested_field(self) -> None:
        data = {"user": {"name": "Bob"}}
        matches = resolve(data, "$.user.name")
        assert matches[0].value == "Bob"

    def test_index(self) -> None:
        data = [10, 20, 30]
        matches = resolve(data, "$[1]")
        assert len(matches) == 1
        assert matches[0].value == 20
        assert matches[0].path == "$[1]"

    def test_wildcard_on_array(self) -> None:
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        matches = resolve(data, "$[*]")
        assert len(matches) == 3
        assert matches[0].value == {"id": 1}
        assert matches[2].path == "$[2]"

    def test_wildcard_field(self) -> None:
        data = [{"name": "a"}, {"name": "b"}]
        matches = resolve(data, "$[*].name")
        assert len(matches) == 2
        assert [m.value for m in matches] == ["a", "b"]

    def test_index_out_of_range(self) -> None:
        data = [1, 2]
        matches = resolve(data, "$[99]")
        assert matches == []

    def test_field_not_found(self) -> None:
        data = {"a": 1}
        matches = resolve(data, "$.missing")
        assert matches == []

    def test_wildcard_on_object(self) -> None:
        data = {"a": 1, "b": 2}
        matches = resolve(data, "$[*]")
        assert len(matches) == 2

    def test_specific_record_field(self) -> None:
        data = [{"room": {"name": "HALL A"}}, {"room": {"name": "HALL B"}}]
        matches = resolve(data, "$[0].room.name")
        assert len(matches) == 1
        assert matches[0].value == "HALL A"


class TestResolvePaths:
    def test_simple_object(self) -> None:
        data = {"a": 1, "b": "hello"}
        index = resolve_paths(data)
        assert "$" in index
        assert "$.a" in index
        assert "$.b" in index
        assert index["$.a"] == [1]

    def test_array_collapses_to_wildcard(self) -> None:
        data = [{"id": 1}, {"id": 2}]
        index = resolve_paths(data)
        assert "$[*]" in index
        assert "$[*].id" in index
        assert len(index["$[*].id"]) == 2

    def test_nested_structure(self) -> None:
        data = [{"room": {"name": "A"}}, {"room": {"name": "B"}}]
        index = resolve_paths(data)
        assert "$[*].room.name" in index
        assert index["$[*].room.name"] == ["A", "B"]
