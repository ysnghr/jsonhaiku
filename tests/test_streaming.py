"""Tests for the streaming ingestion module."""

from __future__ import annotations

import io
import json

import pytest

from jsonhaiku.config import Config
from jsonhaiku.nodes import ArrayNode, ObjectNode, Primitive
from jsonhaiku.streaming import StreamResult, stream_ingest


def _stream(data: object) -> io.BytesIO:
    """Encode *data* as a binary JSON stream."""
    return io.BytesIO(json.dumps(data).encode())


class TestStreamIngestionArray:
    def test_infers_array_of_objects(self) -> None:
        records = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        result = stream_ingest(_stream(records))
        assert isinstance(result.root, ArrayNode)
        assert isinstance(result.root.items, ObjectNode)
        assert result.records_seen == 2

    def test_infers_array_of_scalars(self) -> None:
        result = stream_ingest(_stream([1, 2, 3]))
        assert isinstance(result.root, ArrayNode)
        assert result.records_seen == 3

    def test_empty_array(self) -> None:
        result = stream_ingest(_stream([]))
        assert result.records_seen == 0

    def test_samples_are_collected(self) -> None:
        records = [{"x": i} for i in range(10)]
        result = stream_ingest(_stream(records), reservoir_k=5)
        assert len(result.samples) == 5
        assert all(isinstance(s, dict) for s in result.samples)

    def test_all_samples_when_fewer_than_k(self) -> None:
        records = [{"x": i} for i in range(3)]
        result = stream_ingest(_stream(records), reservoir_k=100)
        assert len(result.samples) == 3


class TestStreamIngestionObject:
    def test_single_object(self) -> None:
        data = {"name": "Alice", "age": 30}
        result = stream_ingest(_stream(data))
        assert isinstance(result.root, ObjectNode)
        assert result.records_seen == 1
        assert "name" in result.root.fields
        assert "age" in result.root.fields

    def test_nested_object(self) -> None:
        data = {"user": {"id": 1, "role": "admin"}}
        cfg = Config(track_cardinality=False)
        result = stream_ingest(_stream(data), config=cfg)
        assert isinstance(result.root, ObjectNode)
        assert "user" in result.root.fields


class TestStreamResult:
    def test_fields(self) -> None:
        records = [{"a": 1}, {"a": 2}]
        result = stream_ingest(_stream(records))
        assert isinstance(result, StreamResult)
        assert isinstance(result.config, Config)
        assert isinstance(result.stats, dict)
        assert isinstance(result.samples, list)
        assert result.records_seen == 2
        assert isinstance(result.bytes_read, int)
        assert isinstance(result.approximate, bool)
        assert isinstance(result.warnings, list)

    def test_config_passthrough(self) -> None:
        cfg = Config(track_cardinality=False)
        result = stream_ingest(_stream([1, 2, 3]), config=cfg)
        assert result.config is cfg


class TestApproximationFlag:
    def test_exact_when_few_values(self) -> None:
        records = [{"status": "ok"}, {"status": "err"}]
        result = stream_ingest(_stream(records))
        assert not result.approximate

    def test_approximate_when_many_unique(self) -> None:
        records = [{"uid": f"user-{i}"} for i in range(2000)]
        cfg = Config(track_cardinality=True, unique_value_cap=50)
        result = stream_ingest(_stream(records), config=cfg)
        assert result.approximate


class TestSeedDeterminism:
    def test_same_seed_same_samples(self) -> None:
        records = [{"v": i} for i in range(200)]

        def run(seed: int) -> list[object]:
            return stream_ingest(_stream(records), reservoir_k=10, seed=seed).samples

        assert run(42) == run(42)

    def test_different_seeds_different_samples(self) -> None:
        records = [{"v": i} for i in range(200)]

        def run(seed: int) -> list[object]:
            return stream_ingest(_stream(records), reservoir_k=10, seed=seed).samples

        assert run(42) != run(99)


class TestProgressCallback:
    def test_callback_is_called(self) -> None:
        records = [{"i": i} for i in range(2500)]
        calls: list[tuple[int, int]] = []

        def on_progress(bytes_read: int, records_seen: int) -> None:
            calls.append((bytes_read, records_seen))

        stream_ingest(_stream(records), on_progress=on_progress)
        assert len(calls) >= 2
        for bytes_read, records_seen in calls:
            assert isinstance(bytes_read, int)
            assert isinstance(records_seen, int)
            assert records_seen > 0

    def test_no_callback_is_fine(self) -> None:
        result = stream_ingest(_stream([1, 2, 3]))
        assert result.records_seen == 3


class TestMergedTypes:
    def test_heterogeneous_arrays(self) -> None:
        records = [{"x": 1}, {"x": "hello"}, {"x": None}]
        result = stream_ingest(_stream(records))
        assert isinstance(result.root, ArrayNode)

    def test_optional_field(self) -> None:
        records = [{"a": 1, "b": "x"}, {"a": 2}]
        result = stream_ingest(_stream(records))
        assert isinstance(result.root, ArrayNode)
        inner = result.root.items
        assert isinstance(inner, ObjectNode)
        assert "a" in inner.fields


class TestStatsCollection:
    def test_stats_populated_for_leaves(self) -> None:
        records = [{"val": 10}, {"val": 20}]
        cfg = Config(track_cardinality=True)
        result = stream_ingest(_stream(records), config=cfg)
        path = ("$", "[*]", "val")
        assert path in result.stats
        ps = result.stats[path]
        assert ps.total_count > 0

    def test_stats_not_collected_without_cardinality(self) -> None:
        records = [{"val": 10}]
        cfg = Config(track_cardinality=False)
        result = stream_ingest(_stream(records), config=cfg)
        assert len(result.stats) == 0


class TestBytesRead:
    def test_bytes_read_nonzero(self) -> None:
        result = stream_ingest(_stream([1, 2, 3]))
        assert result.bytes_read > 0

    def test_bytes_read_matches_payload(self) -> None:
        data = [{"key": "value"}]
        payload = json.dumps(data).encode()
        result = stream_ingest(io.BytesIO(payload))
        assert result.bytes_read == len(payload)
