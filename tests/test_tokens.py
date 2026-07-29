"""Tests for token counting."""

from __future__ import annotations

import pytest

from jsonhaiku import describe


class TestTokenCount:
    def test_basic_count(self) -> None:
        result = describe({"id": 1, "name": "test"})
        count = result.token_count()
        assert isinstance(count, int)
        assert count > 0

    def test_different_formats_have_different_counts(self) -> None:
        result = describe({"id": 1, "name": "test"})
        compact_count = result.token_count(fmt="compact")
        ts_count = result.token_count(fmt="typescript")
        assert isinstance(compact_count, int)
        assert isinstance(ts_count, int)

    def test_anthropic_model_uses_cl100k(self) -> None:
        result = describe({"id": 1})
        count = result.token_count(model="claude-3-5")
        assert isinstance(count, int)
        assert count > 0

    def test_explicit_encoding(self) -> None:
        result = describe({"id": 1})
        count = result.token_count(model="cl100k_base")
        assert isinstance(count, int)
        assert count > 0


class TestTokenBreakdown:
    def test_returns_all_four_formats(self) -> None:
        result = describe({"id": 1, "name": "test"})
        breakdown = result.token_breakdown()
        assert set(breakdown.keys()) == {"compact", "typescript", "json_schema", "yaml"}
        assert all(isinstance(v, int) for v in breakdown.values())
        assert all(v > 0 for v in breakdown.values())

    def test_yaml_is_cheapest_for_nested_structures(self) -> None:
        data = {"a": {"b": {"c": {"d": 1}}}}
        result = describe(data)
        breakdown = result.token_breakdown()
        assert breakdown["yaml"] <= breakdown["json_schema"]
