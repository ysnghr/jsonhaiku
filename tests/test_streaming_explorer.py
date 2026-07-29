"""Tests for JsonHaiku.from_stream() and streamed overview/describe."""

from __future__ import annotations

import io
import json

from jsonhaiku.explorer import JsonHaiku


def _stream(data: object) -> io.BytesIO:
    return io.BytesIO(json.dumps(data).encode())


class TestFromStream:
    def test_creates_instance(self) -> None:
        data = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        h = JsonHaiku.from_stream(_stream(data))
        assert isinstance(h, JsonHaiku)

    def test_overview_root_kind(self) -> None:
        data = [{"x": 1}, {"x": 2}]
        h = JsonHaiku.from_stream(_stream(data))
        ov = h.overview()
        assert ov["root_kind"] == "array"

    def test_overview_records_seen(self) -> None:
        data = [{"x": i} for i in range(10)]
        h = JsonHaiku.from_stream(_stream(data))
        ov = h.overview()
        assert ov["records_seen"] == 10

    def test_overview_has_approximate(self) -> None:
        data = [{"x": 1}]
        h = JsonHaiku.from_stream(_stream(data))
        ov = h.overview()
        assert "approximate" in ov

    def test_overview_top_keys(self) -> None:
        data = [{"name": "a", "age": 1}]
        h = JsonHaiku.from_stream(_stream(data))
        ov = h.overview()
        assert "name" in ov.get("top_keys", [])
        assert "age" in ov.get("top_keys", [])

    def test_describe_root(self) -> None:
        data = [{"id": 1, "val": "x"}]
        h = JsonHaiku.from_stream(_stream(data))
        desc = h.describe("$")
        assert "schema" in desc
        assert desc["path"] == "$"

    def test_describe_tree_format(self) -> None:
        data = [{"id": 1}]
        h = JsonHaiku.from_stream(_stream(data))
        desc = h.describe("$", fmt="tree")
        assert "tree" in desc

    def test_describe_non_root_falls_through(self) -> None:
        data = [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]
        h = JsonHaiku.from_stream(_stream(data))
        desc = h.describe("$[0].name")
        assert desc.get("path") == "$[0].name"

    def test_sample_from_reservoir(self) -> None:
        data = [{"i": i} for i in range(50)]
        h = JsonHaiku.from_stream(_stream(data), reservoir_k=10)
        s = h.sample("$[*]")
        assert s["total"] > 0

    def test_size_bytes_from_stream(self) -> None:
        data = [{"a": 1}]
        payload = json.dumps(data).encode()
        h = JsonHaiku.from_stream(io.BytesIO(payload))
        ov = h.overview()
        assert ov["total_size_bytes"] == len(payload)

    def test_single_object_stream(self) -> None:
        data = {"key": "value", "num": 42}
        h = JsonHaiku.from_stream(_stream(data))
        ov = h.overview()
        assert ov["root_kind"] == "object"

    def test_seed_determinism(self) -> None:
        data = [{"v": i} for i in range(100)]

        def run(seed: int) -> list[object]:
            h = JsonHaiku.from_stream(_stream(data), reservoir_k=5, seed=seed)
            return h.sample("$[*]")["values"]

        assert run(42) == run(42)

    def test_progress_callback(self) -> None:
        data = [{"i": i} for i in range(2000)]
        calls: list[tuple[int, int]] = []

        def on_progress(bytes_read: int, records_seen: int) -> None:
            calls.append((bytes_read, records_seen))

        JsonHaiku.from_stream(_stream(data), on_progress=on_progress)
        assert len(calls) >= 1
