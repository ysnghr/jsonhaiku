"""Tests for the HyperLogLog approximate cardinality module."""

from __future__ import annotations

import pytest

from jsonhaiku.hll import ApproximateCardinality


class TestExactMode:
    def test_empty(self) -> None:
        ac = ApproximateCardinality()
        assert ac.cardinality() == 0
        assert ac.values() == []
        assert not ac.is_approximate
        assert ac.error_rate == 0.0

    def test_single_value(self) -> None:
        ac = ApproximateCardinality()
        ac.add("hello")
        assert ac.cardinality() == 1
        vals = ac.values()
        assert vals is not None
        assert len(vals) == 1

    def test_duplicates_dont_increase_cardinality(self) -> None:
        ac = ApproximateCardinality()
        for _ in range(100):
            ac.add("same")
        assert ac.cardinality() == 1

    def test_multiple_types(self) -> None:
        ac = ApproximateCardinality()
        ac.add(1)
        ac.add("one")
        ac.add(True)
        ac.add(None)
        assert ac.cardinality() == 4


class TestSwitchToHLL:
    def test_switches_above_threshold(self) -> None:
        ac = ApproximateCardinality(switch_threshold=10)
        for i in range(11):
            ac.add(i)
        assert ac.is_approximate
        assert ac.values() is None
        assert ac.error_rate > 0.0

    def test_cardinality_is_accurate_after_switch(self) -> None:
        ac = ApproximateCardinality(switch_threshold=50)
        n = 200
        for i in range(n):
            ac.add(i)
        assert ac.is_approximate
        estimated = ac.cardinality()
        assert abs(estimated - n) / n < 0.15, f"estimated {estimated}, expected ~{n}"

    def test_stays_exact_below_threshold(self) -> None:
        ac = ApproximateCardinality(switch_threshold=1000)
        for i in range(500):
            ac.add(i)
        assert not ac.is_approximate
        assert ac.cardinality() == 500


class TestLargeCardinality:
    @pytest.mark.slow
    def test_hll_accuracy_large(self) -> None:
        ac = ApproximateCardinality(switch_threshold=100)
        n = 10_000
        for i in range(n):
            ac.add(f"value-{i}")
        assert ac.is_approximate
        estimated = ac.cardinality()
        error = abs(estimated - n) / n
        assert error < 0.05, f"HLL error {error:.2%} exceeds 5% for {n} values"
