"""Tests for the reservoir sampling module."""

from __future__ import annotations

from collections import Counter

from jsonhaiku.reservoir import Reservoir


class TestBasicBehaviour:
    def test_fewer_than_k_keeps_all(self) -> None:
        r = Reservoir(10)
        for i in range(5):
            r.add(i)
        assert r.buffer == [0, 1, 2, 3, 4]
        assert r.seen == 5

    def test_exactly_k_keeps_all(self) -> None:
        r = Reservoir(5)
        for i in range(5):
            r.add(i)
        assert len(r.buffer) == 5
        assert r.seen == 5

    def test_more_than_k_keeps_k(self) -> None:
        r = Reservoir(5)
        for i in range(100):
            r.add(i)
        assert len(r.buffer) == 5
        assert r.seen == 100

    def test_buffer_is_copy(self) -> None:
        r = Reservoir(3)
        r.add("a")
        buf = r.buffer
        buf.append("extra")
        assert len(r.buffer) == 1

    def test_k_property(self) -> None:
        r = Reservoir(42)
        assert r.k == 42


class TestDeterminism:
    def test_same_seed_same_result(self) -> None:
        def run(seed: int) -> list[object]:
            r = Reservoir(5, seed=seed)
            for i in range(1000):
                r.add(i)
            return r.buffer

        assert run(42) == run(42)

    def test_different_seeds_different_results(self) -> None:
        def run(seed: int) -> list[object]:
            r = Reservoir(5, seed=seed)
            for i in range(1000):
                r.add(i)
            return r.buffer

        assert run(42) != run(99)


class TestUniformity:
    def test_all_elements_appear(self) -> None:
        counts: Counter[int] = Counter()
        n = 20
        k = 5
        trials = 10_000
        for trial in range(trials):
            r = Reservoir(k, seed=trial)
            for i in range(n):
                r.add(i)
            for item in r.buffer:
                if isinstance(item, int):
                    counts[item] += 1

        expected_per = (k / n) * trials
        for i in range(n):
            ratio = counts[i] / expected_per
            assert 0.85 < ratio < 1.15, f"element {i}: ratio {ratio:.2f} outside [0.85, 1.15]"
