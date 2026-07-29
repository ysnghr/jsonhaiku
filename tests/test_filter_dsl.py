"""Tests for the filter expression DSL — parsing and safety."""

from __future__ import annotations

import pytest

from jsonhaiku.filter_dsl import FilterError, evaluate, parse


class TestParsing:
    def test_simple_equality(self) -> None:
        ast = parse("name == 'Alice'")
        assert ast is not None

    def test_numeric_comparison(self) -> None:
        ast = parse("age > 30")
        assert ast is not None

    def test_boolean_literal(self) -> None:
        ast = parse("active == true")
        assert ast is not None

    def test_null_literal(self) -> None:
        ast = parse("value == null")
        assert ast is not None

    def test_float_literal(self) -> None:
        ast = parse("price > 9.99")
        assert ast is not None

    def test_negative_number(self) -> None:
        ast = parse("temp > -10")
        assert ast is not None

    def test_not_equal(self) -> None:
        ast = parse("status != 'deleted'")
        assert ast is not None

    def test_less_equal(self) -> None:
        ast = parse("age <= 65")
        assert ast is not None

    def test_greater_equal(self) -> None:
        ast = parse("score >= 0")
        assert ast is not None

    def test_in_operator(self) -> None:
        ast = parse("status in ['active', 'pending']")
        assert ast is not None

    def test_contains_operator(self) -> None:
        ast = parse("title contains 'AI'")
        assert ast is not None

    def test_and_expression(self) -> None:
        ast = parse("age > 18 and status == 'active'")
        assert ast is not None

    def test_or_expression(self) -> None:
        ast = parse("role == 'admin' or role == 'moderator'")
        assert ast is not None

    def test_nested_path(self) -> None:
        ast = parse("room.name == 'HALL A'")
        assert ast is not None

    def test_array_index_path(self) -> None:
        ast = parse("items[0].name == 'first'")
        assert ast is not None

    def test_complex_expression(self) -> None:
        ast = parse("duration > 60 and room.name == 'HALL H'")
        assert ast is not None

    def test_triple_and(self) -> None:
        ast = parse("a == 1 and b == 2 and c == 3")
        assert ast is not None

    def test_mixed_and_or(self) -> None:
        ast = parse("a == 1 and b == 2 or c == 3")
        assert ast is not None

    def test_list_of_numbers(self) -> None:
        ast = parse("id in [1, 2, 3]")
        assert ast is not None

    def test_empty_list(self) -> None:
        ast = parse("tags in []")
        assert ast is not None


class TestParseErrors:
    def test_empty_expression(self) -> None:
        with pytest.raises(FilterError, match="empty"):
            parse("")

    def test_missing_operator(self) -> None:
        with pytest.raises(FilterError):
            parse("name 'Alice'")

    def test_missing_value(self) -> None:
        with pytest.raises(FilterError):
            parse("name ==")

    def test_trailing_junk(self) -> None:
        with pytest.raises(FilterError, match="unexpected"):
            parse("name == 'Alice' JUNK")

    def test_unsupported_operator(self) -> None:
        with pytest.raises(FilterError, match="expected"):
            parse("name ~ 'pattern'")


class TestSafety:
    def test_no_python_exec(self) -> None:
        with pytest.raises(FilterError):
            parse("__import__('os').system('echo hacked')")

    def test_dunder_is_safe_dict_lookup(self) -> None:
        result = evaluate({"a": 1}, "__class__.__name__ == 'dict'")
        assert result is False

    def test_no_eval_injection(self) -> None:
        with pytest.raises(FilterError):
            evaluate({}, "eval('1+1') == 2")

    def test_no_semicolons(self) -> None:
        with pytest.raises(FilterError):
            parse("a == 1; import os")

    def test_no_parentheses(self) -> None:
        with pytest.raises(FilterError):
            parse("print('hello') == null")


class TestEvaluate:
    def test_equality_match(self) -> None:
        assert evaluate({"name": "Alice"}, "name == 'Alice'") is True

    def test_equality_mismatch(self) -> None:
        assert evaluate({"name": "Bob"}, "name == 'Alice'") is False

    def test_not_equal(self) -> None:
        assert evaluate({"status": "active"}, "status != 'deleted'") is True

    def test_less_than(self) -> None:
        assert evaluate({"age": 25}, "age < 30") is True
        assert evaluate({"age": 30}, "age < 30") is False

    def test_greater_than(self) -> None:
        assert evaluate({"score": 95}, "score > 90") is True
        assert evaluate({"score": 90}, "score > 90") is False

    def test_less_equal(self) -> None:
        assert evaluate({"age": 30}, "age <= 30") is True
        assert evaluate({"age": 31}, "age <= 30") is False

    def test_greater_equal(self) -> None:
        assert evaluate({"age": 30}, "age >= 30") is True
        assert evaluate({"age": 29}, "age >= 30") is False

    def test_in_list(self) -> None:
        assert evaluate({"status": "active"}, "status in ['active', 'pending']") is True
        assert evaluate({"status": "deleted"}, "status in ['active', 'pending']") is False

    def test_contains(self) -> None:
        assert evaluate({"title": "ML Workshop"}, "title contains 'Workshop'") is True
        assert evaluate({"title": "Keynote"}, "title contains 'Workshop'") is False

    def test_null_comparison(self) -> None:
        assert evaluate({"value": None}, "value == null") is True
        assert evaluate({"value": 0}, "value == null") is False

    def test_boolean_comparison(self) -> None:
        assert evaluate({"active": True}, "active == true") is True
        assert evaluate({"active": False}, "active == false") is True

    def test_float_comparison(self) -> None:
        assert evaluate({"price": 15.5}, "price > 9.99") is True

    def test_nested_path(self) -> None:
        record = {"room": {"name": "HALL A"}}
        assert evaluate(record, "room.name == 'HALL A'") is True
        assert evaluate(record, "room.name == 'HALL B'") is False

    def test_array_index_path(self) -> None:
        record = {"items": [{"name": "first"}, {"name": "second"}]}
        assert evaluate(record, "items[0].name == 'first'") is True

    def test_and_both_true(self) -> None:
        record = {"age": 25, "status": "active"}
        assert evaluate(record, "age > 18 and status == 'active'") is True

    def test_and_one_false(self) -> None:
        record = {"age": 15, "status": "active"}
        assert evaluate(record, "age > 18 and status == 'active'") is False

    def test_or_one_true(self) -> None:
        record = {"role": "admin"}
        assert evaluate(record, "role == 'admin' or role == 'user'") is True

    def test_or_both_false(self) -> None:
        record = {"role": "guest"}
        assert evaluate(record, "role == 'admin' or role == 'user'") is False

    def test_complex_filter(self) -> None:
        record = {"duration": 120, "room": {"name": "HALL H"}}
        assert evaluate(record, "duration > 60 and room.name == 'HALL H'") is True

    def test_missing_field_returns_false(self) -> None:
        assert evaluate({}, "name == 'Alice'") is False

    def test_numeric_compare_with_string_returns_false(self) -> None:
        assert evaluate({"name": "Alice"}, "name > 10") is False

    def test_contains_on_non_string_returns_false(self) -> None:
        assert evaluate({"value": 42}, "value contains 'test'") is False

    def test_in_with_non_tuple_returns_false(self) -> None:
        assert evaluate({"x": 1}, "x in 'hello'") is False
