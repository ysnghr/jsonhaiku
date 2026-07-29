"""Per-path statistics collection for cardinality tracking and enum detection.

The collector walks raw data in parallel with type inference, recording
observations per leaf path.  After inference the statistics drive the
enrichment pass (:mod:`jsonhaiku.enrich`) which replaces generic types with
enums, ``always_null`` markers, and numeric/string annotations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jsonhaiku.config import Config

__all__ = ["PathStats", "collect_stats"]

Path = tuple[str, ...]


@dataclass
class PathStats:
    """Mutable accumulator for one leaf path's observations."""

    total_count: int = 0
    null_count: int = 0
    unique_values: set[object] | None = field(default_factory=set)
    values_over_limit: bool = False

    numeric_min: float | None = None
    numeric_max: float | None = None
    numeric_sum: float = 0.0
    numeric_count: int = 0

    string_min_len: int | None = None
    string_max_len: int | None = None
    string_sum_len: int = 0
    string_count: int = 0

    true_count: int = 0
    false_count: int = 0

    empty_array_count: int = 0
    empty_object_count: int = 0

    def record(self, value: object, *, cap: int) -> None:
        """Record a single observed value."""
        self.total_count += 1

        if value is None:
            self.null_count += 1
        elif isinstance(value, bool):
            self._record_bool(value, cap)
        elif isinstance(value, int | float):
            self._record_numeric(value, cap)
        elif isinstance(value, str):
            self._record_string(value, cap)
        elif isinstance(value, list) and len(value) == 0:
            self.empty_array_count += 1
        elif isinstance(value, dict) and len(value) == 0:
            self.empty_object_count += 1

    def _record_bool(self, value: bool, cap: int) -> None:
        if value:
            self.true_count += 1
        else:
            self.false_count += 1
        self._track_unique(value, cap)

    def _record_numeric(self, value: float, cap: int) -> None:
        num = float(value)
        if self.numeric_min is None or num < self.numeric_min:
            self.numeric_min = num
        if self.numeric_max is None or num > self.numeric_max:
            self.numeric_max = num
        self.numeric_sum += num
        self.numeric_count += 1
        self._track_unique(value, cap)

    def _record_string(self, value: str, cap: int) -> None:
        length = len(value)
        if self.string_min_len is None or length < self.string_min_len:
            self.string_min_len = length
        if self.string_max_len is None or length > self.string_max_len:
            self.string_max_len = length
        self.string_sum_len += length
        self.string_count += 1
        self._track_unique(value, cap)

    def _track_unique(self, value: object, cap: int) -> None:
        if self.unique_values is None:
            return
        self.unique_values.add(value)
        if len(self.unique_values) > cap:
            self.unique_values = None
            self.values_over_limit = True


def collect_stats(
    data: object,
    *,
    config: Config,
) -> dict[Path, PathStats]:
    """Walk *data* and collect per-path statistics.

    Returns a mapping from path tuples to :class:`PathStats`.
    """
    stats: dict[Path, PathStats] = {}
    cap = config.unique_value_cap
    _walk(data, path=("$",), stats=stats, cap=cap)
    return stats


def _walk(
    value: object,
    *,
    path: Path,
    stats: dict[Path, PathStats],
    cap: int,
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _walk(item, path=(*path, str(key)), stats=stats, cap=cap)
        if len(value) == 0:
            ps = stats.get(path)
            if ps is None:
                ps = PathStats()
                stats[path] = ps
            ps.record(value, cap=cap)
        return

    if isinstance(value, list | tuple):
        if len(value) == 0:
            ps = stats.get(path)
            if ps is None:
                ps = PathStats()
                stats[path] = ps
            ps.record(value, cap=cap)
        for element in value:
            _walk(element, path=(*path, "[*]"), stats=stats, cap=cap)
        return

    ps = stats.get(path)
    if ps is None:
        ps = PathStats()
        stats[path] = ps
    ps.record(value, cap=cap)
