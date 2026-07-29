"""Smart sample selection — pick records that best convey the *variance* in the data.

A schema tells an LLM what the shape is.  Samples tell it what the values look
like.  Together they close the gap between "abstract description" and "real
understanding" — but only if the samples are chosen well.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DefaultStrategy",
    "FirstNStrategy",
    "RandomStrategy",
    "Sample",
    "SampleStrategy",
    "select_samples",
]

_USUAL_FIELD_THRESHOLD = 0.5
_DIVERSITY_THRESHOLD = 0.9
_MIN_K_FOR_EXTREME = 2
_MIN_K_FOR_NULLABLE = 3


@dataclass(frozen=True)
class Sample:
    """One representative record chosen from the input data.

    Attributes:
        value: The actual JSON value.
        path: JSONPath to the source location (e.g. ``$[42]``).
        reason: Short human-readable rationale for selection.
        score_components: Breakdown of scoring factors.
    """

    value: Any
    path: str
    reason: str
    score_components: dict[str, Any] = field(default_factory=dict)


class SampleStrategy(ABC):
    """Base class for sample selection strategies.

    Override :meth:`select` for full control, or just implement :meth:`score`
    for simple ranking-based selection.
    """

    def select(self, records: list[object], k: int) -> list[Sample]:
        """Select *k* representative samples from *records*."""
        scored = [(i, self.score(r, records)) for i, r in enumerate(records)]
        scored.sort(key=lambda x: (-x[1], x[0]))
        return [
            Sample(
                value=records[i],
                path=f"$[{i}]",
                reason=f"score: {score:.2f}",
                score_components={"score": score},
            )
            for i, score in scored[:k]
        ]

    @abstractmethod
    def score(self, record: object, corpus: list[object]) -> float:
        """Score a single record for selection priority."""


class FirstNStrategy(SampleStrategy):
    """Select the first *k* records, for baselines and backward compatibility."""

    def select(self, records: list[object], k: int) -> list[Sample]:
        """Return the first *k* records in order."""
        return [
            Sample(
                value=records[i],
                path=f"$[{i}]",
                reason="first-N selection",
                score_components={"index": i},
            )
            for i in range(min(k, len(records)))
        ]

    def score(self, record: object, corpus: list[object]) -> float:  # noqa: ARG002
        """Not used by FirstNStrategy."""
        return 0.0


class RandomStrategy(SampleStrategy):
    """Seeded random selection, for baselines and A/B testing.

    Args:
        seed: RNG seed for reproducibility.
    """

    def __init__(self, seed: int = 42) -> None:
        """Create a random strategy with the given *seed*."""
        self._seed = seed

    def select(self, records: list[object], k: int) -> list[Sample]:
        """Return *k* randomly chosen records (deterministic for a given seed)."""
        import random  # noqa: PLC0415

        rng = random.Random(self._seed)  # noqa: S311
        n = min(k, len(records))
        indices = rng.sample(range(len(records)), n)
        indices.sort()
        return [
            Sample(
                value=records[i],
                path=f"$[{i}]",
                reason="random selection",
                score_components={"index": i},
            )
            for i in indices
        ]

    def score(self, record: object, corpus: list[object]) -> float:  # noqa: ARG002
        """Not used by RandomStrategy."""
        return 0.0


class DefaultStrategy(SampleStrategy):
    """Typical + nullable coverage + extreme + diversity dedup."""

    def select(self, records: list[object], k: int) -> list[Sample]:
        """Select diverse, informative samples covering key axes."""
        if not records or k <= 0:
            return []
        if k >= len(records):
            return [
                Sample(
                    value=records[i],
                    path=f"$[{i}]",
                    reason="all records included",
                    score_components={},
                )
                for i in range(len(records))
            ]

        chosen: list[Sample] = []
        used: set[int] = set()

        typical = _pick_typical(records)
        chosen.append(typical)
        used.add(_index_from_path(typical.path))

        if k >= _MIN_K_FOR_EXTREME:
            extreme = _pick_extreme(records, used)
            if extreme is not None:
                chosen.append(extreme)
                used.add(_index_from_path(extreme.path))

        if k >= _MIN_K_FOR_NULLABLE:
            nullable = _pick_nullable(records, used, k - len(chosen))
            for s in nullable:
                if len(chosen) >= k:
                    break
                chosen.append(s)
                used.add(_index_from_path(s.path))

        while len(chosen) < k:
            filler = _pick_filler(records, used)
            if filler is None:
                break
            chosen.append(filler)
            used.add(_index_from_path(filler.path))

        return _diversity_check(chosen, records)

    def score(self, record: object, corpus: list[object]) -> float:  # noqa: ARG002
        """Not used by DefaultStrategy."""
        return 0.0


def select_samples(
    data: object,
    k: int,
    *,
    strategy: SampleStrategy | None = None,
) -> list[Sample]:
    """Select *k* representative samples from *data*.

    Only works when *data* is a list of records. Returns an empty list for
    scalars, single objects, or empty lists.
    """
    if not isinstance(data, list | tuple) or not data:
        return []
    records = list(data)
    if k <= 0:
        return []
    strat = strategy or DefaultStrategy()
    return strat.select(records, k)


def _index_from_path(path: str) -> int:
    return int(path.split("[")[1].rstrip("]"))


def _pick_typical(records: list[object]) -> Sample:
    """Pick the record closest to the median field completeness."""
    field_counts = _field_presence(records)
    if not field_counts:
        return Sample(
            value=records[0],
            path="$[0]",
            reason="typical: median field completeness",
            score_components={"typicality": 1.0},
        )

    total = len(records)
    usual_fields = {
        f for f, count in field_counts.items() if count / total >= _USUAL_FIELD_THRESHOLD
    }

    scores: list[tuple[int, float]] = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            scores.append((i, 0.0))
            continue
        rec_fields = set(rec.keys())
        hits = len(rec_fields & usual_fields)
        norm = hits / max(len(usual_fields), 1)
        scores.append((i, norm))

    scores.sort(key=lambda x: x[1])
    median_idx = len(scores) // 2
    idx, score = scores[median_idx]

    return Sample(
        value=records[idx],
        path=f"$[{idx}]",
        reason="typical: median field completeness",
        score_components={"typicality": score},
    )


def _pick_extreme(records: list[object], used: set[int]) -> Sample | None:
    """Pick the record with the largest serialized size."""
    best_idx = -1
    best_size = -1
    median_size = _median_size(records)

    for i, rec in enumerate(records):
        if i in used:
            continue
        size = len(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
        if size > best_size:
            best_size = size
            best_idx = i

    if best_idx < 0:
        return None

    size_kb = best_size / 1024
    median_kb = median_size / 1024
    reason = f"extreme: longest record ({size_kb:.1f} KB vs median {median_kb:.1f} KB)"

    return Sample(
        value=records[best_idx],
        path=f"$[{best_idx}]",
        reason=reason,
        score_components={"size": best_size, "median_size": median_size},
    )


def _pick_nullable(
    records: list[object],
    used: set[int],
    budget: int,
) -> list[Sample]:
    """Pick records that demonstrate null values in nullable fields."""
    if budget <= 0:
        return []

    nullable_fields = _find_nullable_fields(records)
    if not nullable_fields:
        return []

    nullable_fields.sort(key=lambda x: x[1])

    result: list[Sample] = []
    used_local = set(used)

    for field_name, _null_rate in nullable_fields:
        if len(result) >= budget:
            break
        for i, rec in enumerate(records):
            if i in used_local:
                continue
            if isinstance(rec, dict) and field_name in rec and rec[field_name] is None:
                result.append(
                    Sample(
                        value=rec,
                        path=f"$[{i}]",
                        reason=f"nullable: '{field_name}' is null here",
                        score_components={"nullable_hits": [field_name]},
                    )
                )
                used_local.add(i)
                break

    return result


def _pick_filler(records: list[object], used: set[int]) -> Sample | None:
    """Pick a record not yet used, preferring diversity from the middle."""
    available = [i for i in range(len(records)) if i not in used]
    if not available:
        return None
    mid = available[len(available) // 2]
    return Sample(
        value=records[mid],
        path=f"$[{mid}]",
        reason="diversity: fills remaining budget",
        score_components={},
    )


def _diversity_check(chosen: list[Sample], records: list[object]) -> list[Sample]:
    """Replace overly similar samples with more diverse alternatives."""
    result = list(chosen)

    for i in range(len(result)):
        for j in range(i + 1, len(result)):
            sim = _jaccard_similarity(result[i].value, result[j].value)
            if sim > _DIVERSITY_THRESHOLD:
                used = {_index_from_path(s.path) for s in result}
                replacement = _pick_filler(records, used)
                if replacement is None:
                    continue
                new_sim = _jaccard_similarity(result[i].value, replacement.value)
                if new_sim < sim:
                    result[j] = replacement

    return result


def _jaccard_similarity(a: object, b: object) -> float:
    """Compute key-set Jaccard similarity between two records."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return 1.0 if a == b else 0.0
    keys_a = set(a.keys())
    keys_b = set(b.keys())
    if not keys_a and not keys_b:
        return 1.0
    union = keys_a | keys_b
    intersection = keys_a & keys_b
    return len(intersection) / len(union) if union else 1.0


def _field_presence(records: list[object]) -> dict[str, int]:
    """Count how many records contain each field."""
    counts: dict[str, int] = {}
    for rec in records:
        if isinstance(rec, dict):
            for key in rec:
                counts[key] = counts.get(key, 0) + 1
    return counts


def _find_nullable_fields(records: list[object]) -> list[tuple[str, float]]:
    """Find fields that are sometimes null, with their null frequency."""
    total_by_field: dict[str, int] = {}
    null_by_field: dict[str, int] = {}

    for rec in records:
        if not isinstance(rec, dict):
            continue
        for key, val in rec.items():
            total_by_field[key] = total_by_field.get(key, 0) + 1
            if val is None:
                null_by_field[key] = null_by_field.get(key, 0) + 1

    result: list[tuple[str, float]] = []
    for field_name, null_count in null_by_field.items():
        total = total_by_field[field_name]
        null_rate = null_count / total
        if 0 < null_rate < 1:
            result.append((field_name, null_rate))
    return result


def _median_size(records: list[object]) -> int:
    """Return the median serialized size of the records."""
    sizes = sorted(len(json.dumps(r, ensure_ascii=False, separators=(",", ":"))) for r in records)
    if not sizes:
        return 0
    return sizes[len(sizes) // 2]
