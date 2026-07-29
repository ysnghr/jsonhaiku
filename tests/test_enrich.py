"""Tests for type tree enrichment — enum detection, stats, and always-null."""

from __future__ import annotations

from jsonhaiku import Config, describe
from jsonhaiku.nodes import (
    ALWAYS_EMPTY_ARRAY,
    ALWAYS_NULL,
    INTEGER,
    NULL,
    STRING,
    ArrayNode,
    EnumNode,
    Field,
    ObjectNode,
    Primitive,
    UnionNode,
)


def _cfg(**kwargs: object) -> Config:
    return Config(track_cardinality=True, **kwargs)  # type: ignore[arg-type]


class TestEnumDetection:
    def test_string_enum(self) -> None:
        data = [{"status": v} for v in ["a", "b", "c"] * 100]
        r = describe(data, config=_cfg())
        node = r.root
        assert isinstance(node, ArrayNode)
        assert node.items is not None
        obj = node.items
        assert isinstance(obj, ObjectNode)
        field = obj.fields["status"]
        assert isinstance(field.type, EnumNode)
        assert set(field.type.values) == {"a", "b", "c"}

    def test_int_enum(self) -> None:
        data = [{"priority": v} for v in [1, 2, 3] * 100]
        r = describe(data, config=_cfg())
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert isinstance(obj.fields["priority"].type, EnumNode)
        assert set(obj.fields["priority"].type.values) == {1, 2, 3}

    def test_enum_with_null(self) -> None:
        values = ["a", "b", None] * 100
        data = [{"x": v} for v in values]
        r = describe(data, config=_cfg())
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        ft = obj.fields["x"].type
        assert isinstance(ft, EnumNode)
        assert None in ft.values

    def test_exceeds_max_values_no_enum(self) -> None:
        data = [{"x": f"val_{i}"} for i in range(300)]
        r = describe(data, config=_cfg(enum_max_values=5))
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert not isinstance(obj.fields["x"].type, EnumNode)

    def test_exceeds_ratio_no_enum(self) -> None:
        data = [{"x": f"val_{i}"} for i in range(30)]
        r = describe(data, config=_cfg(enum_cardinality_ratio=0.01))
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert not isinstance(obj.fields["x"].type, EnumNode)

    def test_boundary_exactly_max_values(self) -> None:
        values = [f"v{i}" for i in range(20)]
        data = [{"x": v} for v in values * 50]
        r = describe(data, config=_cfg(enum_max_values=20))
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert isinstance(obj.fields["x"].type, EnumNode)

    def test_boundary_one_over_max_values(self) -> None:
        values = [f"v{i}" for i in range(21)]
        data = [{"x": v} for v in values * 50]
        r = describe(data, config=_cfg(enum_max_values=20))
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert not isinstance(obj.fields["x"].type, EnumNode)

    def test_cap_exceeded_no_enum(self) -> None:
        data = [{"x": f"val_{i}"} for i in range(200)]
        r = describe(data, config=_cfg(unique_value_cap=50))
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert not isinstance(obj.fields["x"].type, EnumNode)

    def test_pure_booleans_not_enum(self) -> None:
        data = [{"x": True}, {"x": False}] * 100
        r = describe(data, config=_cfg())
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert not isinstance(obj.fields["x"].type, EnumNode)

    def test_with_frequency(self) -> None:
        data = [{"x": v} for v in ["a", "b", "c"] * 100]
        r = describe(data, config=_cfg(include_frequency=True))
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        ft = obj.fields["x"].type
        assert isinstance(ft, EnumNode)
        assert ft.frequencies is not None
        assert len(ft.frequencies) == len(ft.values)


class TestAlwaysNull:
    def test_always_null_detected(self) -> None:
        data = [{"x": None}] * 5
        r = describe(data, config=_cfg())
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert obj.fields["x"].type == ALWAYS_NULL

    def test_not_always_null_below_threshold(self) -> None:
        data = [{"x": None}] * 2
        r = describe(data, config=_cfg(always_null_min_observations=3))
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert obj.fields["x"].type != ALWAYS_NULL

    def test_not_always_null_when_mixed(self) -> None:
        data = [{"x": None}] * 4 + [{"x": 1}]
        r = describe(data, config=_cfg())
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert obj.fields["x"].type != ALWAYS_NULL

    def test_always_empty_array(self) -> None:
        data = [{"items": []}] * 5
        r = describe(data, config=_cfg())
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert obj.fields["items"].type == ALWAYS_EMPTY_ARRAY

    def test_detect_always_null_disabled(self) -> None:
        data = [{"x": None}] * 5
        r = describe(data, config=_cfg(detect_always_null=False))
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        assert obj.fields["x"].type != ALWAYS_NULL


class TestNumericStats:
    def test_numeric_annotation(self) -> None:
        data = [{"v": n} for n in [10, 20, 30]]
        r = describe(data, config=_cfg(enum_cardinality_ratio=0.0))
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        ft = obj.fields["v"].type
        assert isinstance(ft, Primitive)
        assert ft.string_meta is not None
        assert "min=10" in ft.string_meta
        assert "max=30" in ft.string_meta
        assert "mean=20" in ft.string_meta

    def test_stats_disabled(self) -> None:
        data = [{"v": n} for n in [10, 20, 30]]
        r = describe(data, config=_cfg(include_stats=False, enum_cardinality_ratio=0.0))
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        ft = obj.fields["v"].type
        assert isinstance(ft, Primitive)
        assert ft.string_meta is None


class TestStringStats:
    def test_string_length_annotation(self) -> None:
        data = [{"t": s} for s in ["ab", "abcde", "abc"]]
        r = describe(
            data,
            config=_cfg(enum_cardinality_ratio=0.0),
        )
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        ft = obj.fields["t"].type
        assert isinstance(ft, Primitive)
        assert ft.string_meta is not None
        assert "len 2..5" in ft.string_meta
        assert "avg 3" in ft.string_meta


class TestBooleanStats:
    def test_skewed_true(self) -> None:
        data = [{"published": True}] * 19 + [{"published": False}]
        r = describe(data, config=_cfg())
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        ft = obj.fields["published"].type
        assert isinstance(ft, Primitive)
        assert ft.string_meta is not None
        assert "95% true" in ft.string_meta

    def test_balanced_no_annotation(self) -> None:
        data = [{"x": True}] * 10 + [{"x": False}] * 10
        r = describe(data, config=_cfg())
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        ft = obj.fields["x"].type
        assert isinstance(ft, Primitive)
        assert ft.string_meta is None


class TestTimestampDetection:
    def test_unix_seconds_detected(self) -> None:
        data = [{"ts": 1700000000}, {"ts": 1700100000}]
        r = describe(data, config=_cfg(enum_cardinality_ratio=0.0))
        assert isinstance(r.root, ArrayNode)
        assert r.root.items is not None
        obj = r.root.items
        assert isinstance(obj, ObjectNode)
        ft = obj.fields["ts"].type
        assert isinstance(ft, Primitive)
        assert ft.string_meta is not None
        assert "range:" in ft.string_meta
        assert "2023-11" in ft.string_meta


class TestRendering:
    def test_compact_enum(self) -> None:
        data = [{"x": v} for v in ["a", "b"] * 100]
        r = describe(data, config=_cfg())
        assert "enum(" in r.compact
        assert "'a'" in r.compact
        assert "'b'" in r.compact

    def test_typescript_enum(self) -> None:
        data = [{"x": v} for v in ["a", "b"] * 100]
        r = describe(data, config=_cfg())
        ts = r.typescript()
        assert "'a'" in ts
        assert "'b'" in ts

    def test_yaml_enum(self) -> None:
        data = [{"x": v} for v in ["a", "b"] * 100]
        r = describe(data, config=_cfg())
        assert "enum(" in r.yaml

    def test_json_schema_enum(self) -> None:
        data = [{"x": v} for v in ["a", "b"] * 100]
        r = describe(data, config=_cfg())
        schema = r.json_schema
        item_schema = schema["items"]["properties"]["x"]
        assert "enum" in item_schema

    def test_compact_always_null(self) -> None:
        data = [{"x": None}] * 5
        r = describe(data, config=_cfg())
        assert "always_null" in r.compact

    def test_compact_numeric_stats(self) -> None:
        data = [{"v": n} for n in [10, 20, 30]]
        r = describe(data, config=_cfg(enum_cardinality_ratio=0.0))
        assert "min=10" in r.compact

    def test_compact_string_stats(self) -> None:
        data = [{"t": s} for s in ["ab", "abcde", "abc"]]
        r = describe(data, config=_cfg(enum_cardinality_ratio=0.0))
        assert "len 2..5" in r.compact

    def test_compact_boolean_skew(self) -> None:
        data = [{"x": True}] * 19 + [{"x": False}]
        r = describe(data, config=_cfg())
        assert "95% true" in r.compact

    def test_compact_enum_with_frequency(self) -> None:
        data = [{"x": v} for v in ["a", "b"] * 100]
        r = describe(data, config=_cfg(include_frequency=True))
        assert "[" in r.compact
        assert "]" in r.compact
