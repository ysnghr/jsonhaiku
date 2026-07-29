"""Tests for the Result render API."""

from __future__ import annotations

import json

import pytest

from jsonhaiku import Config, describe

DATA = {"id": 1, "name": "test", "tags": ["a"]}


class TestRenderMethod:
    def test_compact(self) -> None:
        result = describe(DATA)
        assert result.render("compact") == result.compact

    def test_typescript(self) -> None:
        result = describe(DATA)
        ts = result.render("typescript")
        assert "interface Root" in ts

    def test_typescript_with_root_name(self) -> None:
        result = describe(DATA)
        ts = result.render("typescript", root_name="Session")
        assert "interface Session" in ts

    def test_json_schema(self) -> None:
        result = describe(DATA)
        schema_str = result.render("json_schema")
        schema = json.loads(schema_str)
        assert "$schema" in schema

    def test_yaml(self) -> None:
        result = describe(DATA)
        yml = result.render("yaml")
        assert "id:" in yml

    def test_format_aliases(self) -> None:
        result = describe(DATA)
        assert result.render("ts") == result.render("typescript")
        assert result.render("yml") == result.render("yaml")

    def test_unknown_format_raises(self) -> None:
        result = describe(DATA)
        with pytest.raises(ValueError, match="unknown format"):
            result.render("nope")

    def test_max_depth_override(self) -> None:
        data = {"a": {"b": {"c": 1}}}
        result = describe(data)
        truncated = result.render("compact", max_depth=1)
        full = result.render("compact")
        assert "..." in truncated
        assert "..." not in full


class TestProperties:
    def test_compact_is_cached(self) -> None:
        result = describe(DATA)
        assert result.compact is result.compact

    def test_json_schema_property(self) -> None:
        result = describe(DATA)
        schema = result.json_schema
        assert schema["$schema"].startswith("https://")
        assert "properties" in schema

    def test_yaml_property(self) -> None:
        result = describe(DATA)
        yml = result.yaml
        assert "id:" in yml
        assert "integer" in yml

    def test_typescript_method(self) -> None:
        result = describe(DATA)
        ts = result.typescript()
        assert "interface Root" in ts

    def test_typescript_custom_name(self) -> None:
        result = describe(DATA)
        ts = result.typescript(root_name="Payload")
        assert "interface Payload" in ts

    def test_schema_backward_compat(self) -> None:
        result = describe(DATA)
        assert result.schema == result.json_schema

    def test_tree_still_works(self) -> None:
        result = describe(DATA)
        tree = result.tree
        assert tree["kind"] == "object"

    def test_str_returns_compact(self) -> None:
        result = describe(DATA)
        assert str(result) == result.compact


class TestConfigOnResult:
    def test_result_stores_config(self) -> None:
        cfg = Config(detect_content_types=True)
        result = describe(DATA, config=cfg)
        assert result.config == cfg

    def test_default_config(self) -> None:
        result = describe(DATA)
        assert result.config == Config()
