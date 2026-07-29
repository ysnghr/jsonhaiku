"""HyperLogLog wrapper for approximate cardinality counting.

Provides a unified interface that starts with an exact ``set`` and
switches to a probabilistic HyperLogLog sketch when the set crosses
a configurable threshold. The switch is transparent to callers.
"""

from __future__ import annotations

import json

__all__ = ["ApproximateCardinality"]

_DEFAULT_SWITCH_THRESHOLD = 1024
_DEFAULT_HLL_PRECISION = 14


class ApproximateCardinality:
    """Cardinality counter that upgrades from exact to approximate.

    Args:
        switch_threshold: Number of unique values before switching to HLL.
        hll_precision: HLL precision parameter (4-16). Higher = more accurate
            but more memory. Default 14 gives ~0.8% error.
    """

    __slots__ = ("_exact", "_hll", "_is_approximate", "_precision", "_threshold")

    def __init__(
        self,
        *,
        switch_threshold: int = _DEFAULT_SWITCH_THRESHOLD,
        hll_precision: int = _DEFAULT_HLL_PRECISION,
    ) -> None:
        """Initialize with exact counting, upgrading to HLL when needed."""
        self._threshold = switch_threshold
        self._precision = hll_precision
        self._exact: set[str] | None = set()
        self._hll: object | None = None
        self._is_approximate = False

    def add(self, value: object) -> None:
        """Record one observed value."""
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if self._exact is not None:
            self._exact.add(key)
            if len(self._exact) > self._threshold:
                self._switch_to_hll()
        else:
            self._add_to_hll(key)

    def cardinality(self) -> int:
        """Return the number of unique values (exact or approximate)."""
        if self._exact is not None:
            return len(self._exact)
        return self._hll_count()

    def values(self) -> list[object] | None:
        """Return exact values if still tracking, else None."""
        if self._exact is not None:
            return [json.loads(v) for v in self._exact]
        return None

    @property
    def is_approximate(self) -> bool:
        """Whether the counter has switched to HLL."""
        return self._is_approximate

    @property
    def error_rate(self) -> float:
        """Approximate error rate (0.0 if exact)."""
        if not self._is_approximate:
            return 0.0
        return 1.04 / (2 ** (self._precision / 2))

    def _switch_to_hll(self) -> None:
        from datasketch import HyperLogLog  # noqa: PLC0415

        hll = HyperLogLog(p=self._precision)
        if self._exact is not None:
            for key in self._exact:
                hll.update(key.encode("utf-8"))
        self._hll = hll
        self._exact = None
        self._is_approximate = True

    def _add_to_hll(self, key: str) -> None:
        from datasketch import HyperLogLog  # noqa: PLC0415

        if isinstance(self._hll, HyperLogLog):
            self._hll.update(key.encode("utf-8"))

    def _hll_count(self) -> int:
        from datasketch import HyperLogLog  # noqa: PLC0415

        if isinstance(self._hll, HyperLogLog):
            return int(self._hll.count())
        return 0
