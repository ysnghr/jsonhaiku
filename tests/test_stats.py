"""Tests for per-path statistics collection."""

from __future__ import annotations

import pytest

from jsonhaiku.config import Config
from jsonhaiku.stats import PathStats, collect_stats


@pytest.fixture
def cfg() -> Config:
    return Config(track_cardinality=True)


class TestPathStats:
    def test_null_recording(self) -> None:
        ps = PathStats()
        ps.record(None, cap=100)
        assert ps.total_count == 1
        assert ps.null_count == 1

    def test_string_stats(self) -> None:
        ps = PathStats()
        for s in ("abc", "de", "fghij"):
            ps.record(s, cap=100)
        assert ps.string_count == 3
        assert ps.string_min_len == 2
        assert ps.string_max_len == 5
        assert ps.string_sum_len == 10

    def test_numeric_stats(self) -> None:
        ps = PathStats()
        for n in (10, 20, 30):
            ps.record(n, cap=100)
        assert ps.numeric_count == 3
        assert ps.numeric_min == 10.0
        assert ps.numeric_max == 30.0
        assert ps.numeric_sum == 60.0

    def test_boolean_stats(self) -> None:
        ps = PathStats()
        ps.record(True, cap=100)
        ps.record(True, cap=100)
        ps.record(False, cap=100)
        assert ps.true_count == 2
        assert ps.false_count == 1

    def test_unique_value_cap(self) -> None:
        ps = PathStats()
        for i in range(10):
            ps.record(f"val_{i}", cap=5)
        assert ps.values_over_limit is True
        assert ps.unique_values is None
        assert ps.string_count == 10

    def test_empty_array_tracking(self) -> None:
        ps = PathStats()
        ps.record([], cap=100)
        ps.record([], cap=100)
        assert ps.empty_array_count == 2

    def test_empty_object_tracking(self) -> None:
        ps = PathStats()
        ps.record({}, cap=100)
        assert ps.empty_object_count == 1

    def test_bool_not_counted_as_int(self) -> None:
        ps = PathStats()
        ps.record(True, cap=100)
        ps.record(False, cap=100)
        assert ps.numeric_count == 0
        assert ps.true_count == 1
        assert ps.false_count == 1


class TestCollectStats:
    def test_flat_object(self, cfg: Config) -> None:
        data = {"name": "Alice", "age": 30}
        stats = collect_stats(data, config=cfg)
        assert ("$", "name") in stats
        assert ("$", "age") in stats
        assert stats[("$", "name")].string_count == 1
        assert stats[("$", "age")].numeric_count == 1

    def test_array_of_objects(self, cfg: Config) -> None:
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        stats = collect_stats(data, config=cfg)
        ps = stats[("$", "[*]", "id")]
        assert ps.numeric_count == 3
        assert ps.numeric_min == 1.0
        assert ps.numeric_max == 3.0

    def test_nested_objects(self, cfg: Config) -> None:
        data = {"room": {"name": "A"}}
        stats = collect_stats(data, config=cfg)
        assert ("$", "room", "name") in stats

    def test_null_field_tracking(self, cfg: Config) -> None:
        data = [{"x": None}, {"x": None}, {"x": None}]
        stats = collect_stats(data, config=cfg)
        ps = stats[("$", "[*]", "x")]
        assert ps.null_count == 3
        assert ps.total_count == 3

    def test_empty_array_in_records(self, cfg: Config) -> None:
        data = [{"items": []}, {"items": []}]
        stats = collect_stats(data, config=cfg)
        ps = stats[("$", "[*]", "items")]
        assert ps.empty_array_count == 2

    def test_mixed_types(self, cfg: Config) -> None:
        data = [{"val": "a"}, {"val": 1}, {"val": None}]
        stats = collect_stats(data, config=cfg)
        ps = stats[("$", "[*]", "val")]
        assert ps.total_count == 3
        assert ps.string_count == 1
        assert ps.numeric_count == 1
        assert ps.null_count == 1
