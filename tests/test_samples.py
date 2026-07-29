"""Tests for smart sample selection and PII redaction."""

from __future__ import annotations

from jsonhaiku import Config, Sample, describe
from jsonhaiku.redact import redact
from jsonhaiku.samples import (
    DefaultStrategy,
    FirstNStrategy,
    RandomStrategy,
    SampleStrategy,
    select_samples,
)


class TestDeterminism:
    def test_100_runs_identical(self) -> None:
        data = [{"id": i, "name": f"item-{i}", "value": i * 10} for i in range(50)]
        baseline = select_samples(data, 3)
        for _ in range(99):
            result = select_samples(data, 3)
            assert len(result) == len(baseline)
            for a, b in zip(result, baseline, strict=True):
                assert a.value == b.value
                assert a.path == b.path
                assert a.reason == b.reason

    def test_determinism_with_nullable_fields(self) -> None:
        data = [
            {"id": i, "name": f"item-{i}", "group": None if i % 20 == 0 else "A"}
            for i in range(100)
        ]
        baseline = select_samples(data, 4)
        for _ in range(49):
            result = select_samples(data, 4)
            for a, b in zip(result, baseline, strict=True):
                assert a.value == b.value
                assert a.path == b.path


class TestNullableCoverage:
    def test_rare_null_field_selected(self) -> None:
        data: list[object] = [
            {
                "id": i,
                "email": None if i == 42 else f"u{i}@test.com",
                "extra": "x" if i % 3 == 0 else None,
            }
            for i in range(100)
        ]
        result = select_samples(data, 4)
        null_email_found = any(
            isinstance(s.value, dict) and s.value.get("email") is None for s in result
        )
        assert null_email_found

    def test_nullable_reason_mentions_field(self) -> None:
        data: list[object] = []
        for i in range(50):
            rec: dict[str, object] = {"id": i, "name": f"item-{i}"}
            rec["group"] = None if i in (10, 20) else "active"
            if i == 49:
                rec["payload"] = "x" * 500
            data.append(rec)
        result = select_samples(data, 4)
        nullable_samples = [s for s in result if "nullable" in s.reason]
        assert len(nullable_samples) >= 1
        assert any("group" in s.reason for s in nullable_samples)

    def test_rarest_null_prioritized(self) -> None:
        data: list[object] = []
        for i in range(100):
            rec: dict[str, object] = {"id": i}
            rec["common_null"] = None if i % 5 == 0 else "present"
            rec["rare_null"] = None if i == 99 else "present"
            data.append(rec)

        result = select_samples(data, 3)
        nullable_reasons = [s.reason for s in result if "nullable" in s.reason]
        if nullable_reasons:
            assert "rare_null" in nullable_reasons[0]


class TestExtremeDetection:
    def test_giant_record_selected(self) -> None:
        data: list[object] = [{"id": i, "val": "x"} for i in range(50)]
        giant = {"id": 999, "val": "x" * 5000, "extra": list(range(100))}
        data.append(giant)

        result = select_samples(data, 3)
        extreme_samples = [s for s in result if "extreme" in s.reason]
        assert len(extreme_samples) == 1
        assert extreme_samples[0].value["id"] == 999

    def test_extreme_reason_contains_size(self) -> None:
        data: list[object] = [{"id": i} for i in range(20)]
        data.append({"id": 999, "payload": "A" * 10_000})

        result = select_samples(data, 3)
        extreme = [s for s in result if "extreme" in s.reason]
        assert extreme
        assert "KB" in extreme[0].reason


class TestDiversity:
    def test_identical_records_dont_dominate(self) -> None:
        template: dict[str, object] = {"type": "talk", "length": 30, "track": "main"}
        data: list[object] = [dict(template) for _ in range(90)]
        data.extend(
            [
                {"type": "workshop", "length": 120, "track": "labs"},
                {"type": "keynote", "length": 60, "track": "main", "featured": True},
            ]
        )

        result = select_samples(data, 3)
        values = [s.value for s in result]
        unique_types = {v.get("type") if isinstance(v, dict) else None for v in values}
        assert len(unique_types) >= 2


class TestRedaction:
    def test_api_key_redacted(self) -> None:
        val: object = {"name": "test", "api_key": "sk-1234567890"}
        redacted = redact(val)
        assert isinstance(redacted, dict)
        assert redacted["api_key"] == "<redacted>"
        assert redacted["name"] == "test"

    def test_email_redacted(self) -> None:
        val: object = {"email": "alice@example.com", "id": 1}
        redacted = redact(val)
        assert isinstance(redacted, dict)
        assert redacted["email"] == "user@example.com"
        assert redacted["id"] == 1

    def test_phone_redacted(self) -> None:
        val: object = {"phone": "+1-555-123-4567", "name": "Bob"}
        redacted = redact(val)
        assert isinstance(redacted, dict)
        assert redacted["phone"] == "+1-555-0100"

    def test_normal_string_not_redacted(self) -> None:
        val: object = {"title": "Hello world", "count": 42}
        redacted = redact(val)
        assert isinstance(redacted, dict)
        assert redacted["title"] == "Hello world"

    def test_sensitive_field_names(self) -> None:
        val: object = {
            "password": "hunter2",
            "token": "abc123",
            "secret": "s3cr3t",
            "authorization": "Bearer xyz",
            "access_token": "at-123",
            "refresh_token": "rt-456",
            "private_key": "pk-789",
            "secret_key": "sk-000",
        }
        redacted = redact(val)
        assert isinstance(redacted, dict)
        for key in val:  # type: ignore[union-attr]
            assert redacted[key] == "<redacted>"

    def test_nested_redaction(self) -> None:
        val: object = {"user": {"email": "a@b.com", "password": "x"}}
        redacted = redact(val)
        assert isinstance(redacted, dict)
        inner = redacted["user"]
        assert isinstance(inner, dict)
        assert inner["email"] == "user@example.com"
        assert inner["password"] == "<redacted>"  # noqa: S105

    def test_list_redaction(self) -> None:
        val: object = {"emails": ["a@b.com", "c@d.com"]}
        redacted = redact(val)
        assert isinstance(redacted, dict)
        assert redacted["emails"] == ["user@example.com", "user@example.com"]

    def test_does_not_mutate_original(self) -> None:
        val: object = {"api_key": "original-secret"}
        redacted = redact(val)
        assert isinstance(val, dict)
        assert val["api_key"] == "original-secret"
        assert isinstance(redacted, dict)
        assert redacted["api_key"] == "<redacted>"

    def test_redact_samples_via_describe(self) -> None:
        data = [
            {"id": 1, "email": "alice@test.com", "api_key": "sk-abc"},
            {"id": 2, "email": "bob@test.com", "api_key": "sk-def"},
            {"id": 3, "email": "carol@test.com", "api_key": "sk-ghi"},
        ]
        result = describe(data, samples=2, redact_samples=True)
        for sample in result.samples:
            assert isinstance(sample, Sample)
            assert isinstance(sample.value, dict)
            assert sample.value["api_key"] == "<redacted>"
            assert sample.value["email"] == "user@example.com"


class TestCustomStrategy:
    def test_score_based_strategy(self) -> None:
        class HighIdStrategy(SampleStrategy):
            """Select records with the highest id."""

            def score(self, record: object, corpus: list[object]) -> float:  # noqa: ARG002
                """Score by id value."""
                if isinstance(record, dict):
                    return float(record.get("id", 0))
                return 0.0

        data = [{"id": i, "name": f"item-{i}"} for i in range(20)]
        result = select_samples(data, 3, strategy=HighIdStrategy())
        ids = [s.value["id"] for s in result]
        assert ids == [19, 18, 17]

    def test_custom_strategy_via_describe(self) -> None:
        data = [{"id": i} for i in range(10)]
        result = describe(data, samples=3, sample_strategy=FirstNStrategy())
        assert len(result.samples) == 3
        for i, sample in enumerate(result.samples):
            assert isinstance(sample, Sample)
            assert sample.value == {"id": i}


class TestFirstNStrategy:
    def test_returns_first_k(self) -> None:
        data = [{"id": i} for i in range(10)]
        result = select_samples(data, 3, strategy=FirstNStrategy())
        assert len(result) == 3
        for i, sample in enumerate(result):
            assert sample.value == {"id": i}
            assert sample.path == f"$[{i}]"
            assert sample.reason == "first-N selection"

    def test_k_larger_than_data(self) -> None:
        data = [{"id": i} for i in range(2)]
        result = select_samples(data, 5, strategy=FirstNStrategy())
        assert len(result) == 2


class TestRandomStrategy:
    def test_deterministic_with_seed(self) -> None:
        data = [{"id": i} for i in range(50)]
        r1 = select_samples(data, 5, strategy=RandomStrategy(seed=123))
        r2 = select_samples(data, 5, strategy=RandomStrategy(seed=123))
        assert [s.path for s in r1] == [s.path for s in r2]

    def test_different_seeds_differ(self) -> None:
        data = [{"id": i} for i in range(50)]
        r1 = select_samples(data, 5, strategy=RandomStrategy(seed=1))
        r2 = select_samples(data, 5, strategy=RandomStrategy(seed=2))
        assert [s.path for s in r1] != [s.path for s in r2]


class TestSelectSamples:
    def test_non_list_returns_empty(self) -> None:
        assert select_samples({"a": 1}, 3) == []
        assert select_samples("hello", 3) == []
        assert select_samples(42, 3) == []
        assert select_samples(None, 3) == []

    def test_empty_list_returns_empty(self) -> None:
        assert select_samples([], 3) == []

    def test_k_zero_returns_empty(self) -> None:
        assert select_samples([{"id": 1}], 0) == []

    def test_k_negative_returns_empty(self) -> None:
        assert select_samples([{"id": 1}], -1) == []

    def test_k_exceeds_records(self) -> None:
        data = [{"id": i} for i in range(3)]
        result = select_samples(data, 10)
        assert len(result) == 3

    def test_single_record(self) -> None:
        data = [{"id": 1}]
        result = select_samples(data, 1)
        assert len(result) == 1
        assert result[0].value == {"id": 1}

    def test_tuple_input(self) -> None:
        data = ({"id": 1}, {"id": 2}, {"id": 3})
        result = select_samples(data, 2)
        assert len(result) == 2

    def test_sample_has_path(self) -> None:
        data = [{"id": i} for i in range(10)]
        result = select_samples(data, 3)
        for sample in result:
            assert sample.path.startswith("$[")
            assert sample.path.endswith("]")

    def test_sample_has_reason(self) -> None:
        data = [{"id": i} for i in range(10)]
        result = select_samples(data, 3)
        for sample in result:
            assert len(sample.reason) > 0


class TestRenderWithSamples:
    def test_no_samples_returns_schema_only(self) -> None:
        result = describe([{"id": 1}])
        text = result.render_with_samples()
        assert "// Samples:" not in text

    def test_with_samples(self) -> None:
        data = [{"id": i, "name": f"item-{i}"} for i in range(10)]
        result = describe(data, samples=2)
        text = result.render_with_samples()
        assert "// Samples:" in text
        assert "// [0]" in text
        assert "// [1]" in text
        assert '"id"' in text

    def test_typescript_format(self) -> None:
        data = [{"id": i} for i in range(5)]
        result = describe(data, samples=1)
        text = result.render_with_samples("typescript")
        assert "Root" in text
        assert "// Samples:" in text

    def test_yaml_format(self) -> None:
        data = [{"id": i} for i in range(5)]
        result = describe(data, samples=1)
        text = result.render_with_samples("yaml")
        assert "// Samples:" in text


class TestDescribeIntegration:
    def test_describe_with_samples(self) -> None:
        data = [{"id": i, "status": "active"} for i in range(20)]
        result = describe(data, samples=3)
        assert len(result.samples) == 3
        for s in result.samples:
            assert isinstance(s, Sample)
            assert isinstance(s.value, dict)

    def test_describe_no_samples(self) -> None:
        data = [{"id": i} for i in range(10)]
        result = describe(data)
        assert result.samples == ()

    def test_describe_samples_with_config(self) -> None:
        cfg = Config(track_cardinality=True)
        data = [{"id": i, "val": "x"} for i in range(20)]
        result = describe(data, config=cfg, samples=2)
        assert len(result.samples) == 2

    def test_describe_scalar_ignores_samples(self) -> None:
        result = describe(42, samples=3)
        assert result.samples == ()

    def test_describe_dict_ignores_samples(self) -> None:
        result = describe({"a": 1}, samples=3)
        assert result.samples == ()
