"""Reservoir sampling — keep a fixed-size uniform random sample from a stream.

Implements Vitter's Algorithm R: every record in the stream has an equal
probability of being in the final reservoir, regardless of stream length.
"""

from __future__ import annotations

import random

__all__ = ["Reservoir"]


class Reservoir:
    """Fixed-size reservoir that samples uniformly from a stream.

    Args:
        k: Maximum number of records to keep.
        seed: Optional random seed for reproducibility.
    """

    __slots__ = ("_buffer", "_k", "_rng", "_seen")

    def __init__(self, k: int, *, seed: int | None = None) -> None:
        """Initialize a reservoir with capacity *k*."""
        self._k = k
        self._buffer: list[object] = []
        self._seen = 0
        self._rng = random.Random(seed)  # noqa: S311

    def add(self, record: object) -> None:
        """Add one record to the reservoir."""
        self._seen += 1
        if len(self._buffer) < self._k:
            self._buffer.append(record)
        else:
            j = self._rng.randrange(self._seen)
            if j < self._k:
                self._buffer[j] = record

    @property
    def buffer(self) -> list[object]:
        """Return the current reservoir contents."""
        return list(self._buffer)

    @property
    def seen(self) -> int:
        """Return the total number of records offered."""
        return self._seen

    @property
    def k(self) -> int:
        """Return the reservoir capacity."""
        return self._k
