"""Streaming ingestion — process JSON files that don't fit in RAM.

Uses ``ijson`` for event-driven parsing. The ingestor incrementally
builds the type tree and collects statistics without holding the full
document in memory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import IO, TYPE_CHECKING

from jsonhaiku.config import Config
from jsonhaiku.core import infer, merge
from jsonhaiku.hll import ApproximateCardinality
from jsonhaiku.nodes import NULL, ArrayNode, Node
from jsonhaiku.reservoir import Reservoir
from jsonhaiku.stats import PathStats

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

__all__ = ["StreamResult", "stream_ingest"]

Path = tuple[str, ...]

_DEFAULT_RESERVOIR_K = 100
_PROGRESS_INTERVAL = 1000


@dataclass
class StreamResult:
    """Result of streaming ingestion.

    Attributes:
        root: The inferred type tree.
        config: The config used during ingestion.
        stats: Per-path statistics.
        samples: Reservoir-sampled records.
        records_seen: Total number of top-level records processed.
        bytes_read: Total bytes parsed from the stream.
        approximate: Whether any output uses approximate counting.
        warnings: List of degradation warnings.
    """

    root: Node
    config: Config
    stats: dict[Path, PathStats]
    samples: list[object]
    records_seen: int
    bytes_read: int
    approximate: bool
    warnings: list[str] = field(default_factory=list)


def stream_ingest(
    stream: IO[bytes],
    *,
    config: Config | None = None,
    memory_budget_mb: int = 500,  # noqa: ARG001
    reservoir_k: int = _DEFAULT_RESERVOIR_K,
    seed: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> StreamResult:
    """Ingest a JSON stream and return a StreamResult.

    Args:
        stream: Binary stream containing JSON data.
        config: Optional configuration for inference.
        memory_budget_mb: Soft memory budget in megabytes (reserved for future use).
        reservoir_k: Number of records to keep in the reservoir sample.
        seed: Random seed for reproducible sampling.
        on_progress: Callback ``(bytes_read, records_seen)`` for progress.

    Returns:
        A StreamResult with the inferred schema, stats, and samples.
    """
    import ijson  # noqa: PLC0415

    cfg = config or Config(track_cardinality=True)
    ctx = _IngestContext(cfg=cfg, reservoir_k=reservoir_k, seed=seed)

    parser = ijson.parse(stream, use_float=True)
    ctx.run(parser, stream, on_progress)

    bytes_read = _stream_position(stream)
    approximate = False

    if cfg.track_cardinality:
        _merge_hll_into_stats(ctx.stats, ctx.trackers)
        approximate = any(t.is_approximate for t in ctx.trackers.values())

    root = ctx.root
    if cfg.track_cardinality and root is not None:
        from jsonhaiku.enrich import enrich  # noqa: PLC0415

        root = enrich(root, ctx.stats, cfg)

    if root is None:
        root = NULL

    return StreamResult(
        root=root,
        config=cfg,
        stats=ctx.stats,
        samples=ctx.reservoir.buffer,
        records_seen=ctx.records_seen,
        bytes_read=bytes_read,
        approximate=approximate,
    )


class _IngestContext:
    """Mutable state for a streaming ingestion run."""

    __slots__ = ("cfg", "records_seen", "reservoir", "root", "stats", "trackers")

    def __init__(self, *, cfg: Config, reservoir_k: int, seed: int | None) -> None:
        """Initialize ingestion context."""
        self.cfg = cfg
        self.reservoir = Reservoir(reservoir_k, seed=seed)
        self.stats: dict[Path, PathStats] = {}
        self.trackers: dict[Path, ApproximateCardinality] = {}
        self.root: Node | None = None
        self.records_seen = 0

    def run(
        self,
        parser: Iterator[tuple[str, str, object]],
        stream: IO[bytes],
        on_progress: Callable[[int, int], None] | None,
    ) -> None:
        """Run the ingestion loop."""
        builder = _RecordBuilder()

        for prefix, event, _value in parser:
            if prefix == "" and event == "start_array":
                self._ingest_array_body(parser, builder, stream, on_progress)
                return
            if prefix == "" and event == "start_map":
                record = _consume_map(parser, builder)
                self._process_record(record, ("$",))
                return

    def _ingest_array_body(
        self,
        parser: Iterator[tuple[str, str, object]],
        builder: _RecordBuilder,
        stream: IO[bytes],
        on_progress: Callable[[int, int], None] | None,
    ) -> None:
        """Process elements of a top-level array."""
        for prefix, event, value in parser:
            if prefix == "" and event == "end_array":
                break
            record = builder.handle(event, value)
            if record is not _SENTINEL:
                self._process_record(record, ("$", "[*]"))
                if on_progress is not None and self.records_seen % _PROGRESS_INTERVAL == 0:
                    on_progress(_stream_position(stream), self.records_seen)

        if self.root is not None:
            self.root = ArrayNode(self.root)

    def _process_record(self, record: object, base_path: Path) -> None:
        """Infer type, add to reservoir, and collect stats for one record."""
        self.records_seen += 1
        node = infer(record, config=self.cfg)
        self.root = merge(self.root, node) if self.root is not None else node
        self.reservoir.add(record)
        if self.cfg.track_cardinality:
            _walk_stats(record, base_path, self.stats, self.trackers, self.cfg.unique_value_cap)


_SENTINEL = object()


class _RecordBuilder:
    """Reconstruct complete JSON records from ijson events."""

    __slots__ = ("_stack",)

    def __init__(self) -> None:
        """Initialize the builder."""
        self._stack: list[object] = []

    def handle(self, event: str, value: object) -> object:
        """Process one ijson event. Returns the record when complete, else _SENTINEL."""
        if event in ("start_map", "start_array"):
            self._stack.append({} if event == "start_map" else [])
            return _SENTINEL

        if event == "map_key":
            self._stack.append(value)
            return _SENTINEL

        if event in ("end_map", "end_array"):
            return self._complete()

        if not self._stack:
            return value
        self._add_to_parent(value)
        return _SENTINEL

    def _complete(self) -> object:
        """Handle end_map/end_array: pop and either return or attach to parent."""
        completed = self._stack.pop()
        if not self._stack:
            return completed
        self._add_to_parent(completed)
        return _SENTINEL

    def _add_to_parent(self, value: object) -> None:
        if not self._stack:
            return
        parent = self._stack[-1]
        if isinstance(parent, list):
            parent.append(value)
        elif isinstance(parent, str):
            key = self._stack.pop()
            if self._stack and isinstance(self._stack[-1], dict):
                self._stack[-1][key] = value


def _consume_map(
    parser: Iterator[tuple[str, str, object]],
    builder: _RecordBuilder,
) -> object:
    """Consume a single top-level map from the parser."""
    builder.handle("start_map", None)
    for _prefix, ev, val in parser:
        result = builder.handle(ev, val)
        if result is not _SENTINEL:
            return result
    return {}


def _walk_stats(
    value: object,
    path: Path,
    stats: dict[Path, PathStats],
    trackers: dict[Path, ApproximateCardinality],
    cap: int,
) -> None:
    """Walk a record and update stats accumulators."""
    if isinstance(value, dict):
        _walk_dict_stats(value, path, stats, trackers, cap)
        return

    if isinstance(value, list | tuple):
        _walk_list_stats(value, path, stats, trackers, cap)
        return

    _record_leaf(value, path, stats, trackers, cap)


def _record_leaf(
    value: object,
    path: Path,
    stats: dict[Path, PathStats],
    trackers: dict[Path, ApproximateCardinality],
    cap: int,
) -> None:
    """Record a leaf value in both stats and cardinality trackers."""
    ps = stats.get(path)
    if ps is None:
        ps = PathStats()
        stats[path] = ps
    ps.record(value, cap=cap)

    if path not in trackers:
        trackers[path] = ApproximateCardinality()
    trackers[path].add(value)


def _walk_dict_stats(
    value: dict[str, object],
    path: Path,
    stats: dict[Path, PathStats],
    trackers: dict[Path, ApproximateCardinality],
    cap: int,
) -> None:
    """Walk a dict and update stats."""
    for key, item in value.items():
        _walk_stats(item, (*path, str(key)), stats, trackers, cap)
    if len(value) == 0:
        ps = stats.get(path)
        if ps is None:
            ps = PathStats()
            stats[path] = ps
        ps.record(value, cap=cap)


def _walk_list_stats(
    value: list[object] | tuple[object, ...],
    path: Path,
    stats: dict[Path, PathStats],
    trackers: dict[Path, ApproximateCardinality],
    cap: int,
) -> None:
    """Walk a list and update stats."""
    if len(value) == 0:
        ps = stats.get(path)
        if ps is None:
            ps = PathStats()
            stats[path] = ps
        ps.record(value, cap=cap)
    for element in value:
        _walk_stats(element, (*path, "[*]"), stats, trackers, cap)


def _merge_hll_into_stats(
    stats: dict[Path, PathStats],
    trackers: dict[Path, ApproximateCardinality],
) -> None:
    """Merge HLL cardinality counts into PathStats unique_values."""
    for path, tracker in trackers.items():
        ps = stats.get(path)
        if ps is None:
            continue
        if tracker.is_approximate:
            ps.unique_values = None
            ps.values_over_limit = True
        elif tracker.values() is not None:
            exact = tracker.values()
            if exact is not None and ps.unique_values is not None:
                ps.unique_values = {json.dumps(v, ensure_ascii=False) for v in exact}


def _stream_position(stream: IO[bytes]) -> int:
    """Get the current position of the stream."""
    try:
        return stream.tell()
    except (OSError, AttributeError):
        return 0
