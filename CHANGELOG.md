# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While the version is `0.x`, minor bumps may contain breaking changes. From
`1.0.0` onwards, breaking changes require a major bump and one minor release of
deprecation warnings first.

## [Unreleased]

### Added

- **MCP server** (`jsonhaiku-mcp` package): expose the JsonHaiku API as
  10 MCP tools for Claude Desktop, Cursor, Continue, Zed, and any
  MCP-capable client. Install with `pip install jsonhaiku-mcp` or use
  `uvx jsonhaiku-mcp` for zero-install setup.
  - `jsonhaiku_load` — load JSON from file, URL, or inline text.
  - `jsonhaiku_overview` — high-level summary of the payload.
  - `jsonhaiku_describe` — inferred type schema at any JSONPath.
  - `jsonhaiku_sample` — representative sample values.
  - `jsonhaiku_enum` — unique values sorted by frequency.
  - `jsonhaiku_stats` — numeric/string statistics.
  - `jsonhaiku_filter` — safe DSL filtering.
  - `jsonhaiku_search` — substring search across values.
  - `jsonhaiku_list_paths` — enumerate all observed paths.
  - `jsonhaiku_unload` — release session memory.
- **Session management** with configurable TTL (default 1 hour),
  automatic cleanup, and thread-safe concurrent access.
- **Size and timeout caps**: 200 MB max payload, 30s URL fetch timeout.
- Setup documentation for Claude Desktop, Cursor, Continue.dev, and Zed.

- **Progressive disclosure API** via `JsonHaiku(data)`: a stateful explorer
  for interactive, path-scoped JSON inspection. Seven accessors return
  compact, LLM-friendly dicts:
  - `overview()` — root kind, size, top-level keys.
  - `describe(path, depth)` — inferred schema at any JSONPath.
  - `sample(path, n)` — representative values at a path.
  - `enum(path)` — unique values sorted by frequency.
  - `stats(path)` — numeric/string statistics.
  - `search(value_contains, path)` — substring search across values.
  - `filter(path, where)` — safe DSL filter with `and`/`or`, comparison
    operators, `in`, and `contains`.
  - `list_paths(min_depth, max_depth)` — enumerate all observed paths.
- **JSONPath subset** supporting `$`, `.field`, `[N]`, `[*]`.
- **Safe filter DSL** — recursive-descent parser, no `eval`/`exec`. Supports
  `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `contains`, `and`, `or`.
- **Truncation transparency** — every accessor reports when results are
  trimmed, with total counts alongside returned counts.
- **Depth control** — uniform `depth` parameter across describe accessors.
- `jsonhaiku shell data.json` — interactive REPL for exploring payloads.
- `JsonHaiku` exported from the top-level package.

- **Smart sample selection** via `describe(data, samples=3)`: picks
  representative records covering typical shape, nullable-field variations,
  and extreme outliers rather than naively returning the first N.
  Each sample carries a `reason` string explaining why it was chosen.
- **Sample strategies**: `DefaultStrategy` (typical + nullable + extreme +
  diversity dedup), `RandomStrategy` (seeded), and `FirstNStrategy`. Custom
  strategies via the `SampleStrategy` abstract base class.
- **PII redaction** (opt-in `redact_samples=True`): replaces emails, phone
  numbers, and fields named `password`/`token`/`secret`/`api_key` etc. with
  safe placeholders in sample values.
- `result.render_with_samples(fmt)` — renders the type description with
  selected samples appended, ready to hand to an LLM.
- `Sample` dataclass exported from the top-level package.
- CLI gains `--samples K` and `--redact-samples` flags.

- **Cardinality tracking and enum detection** (opt-in via
  `Config(track_cardinality=True)`): tracks per-path statistics and detects
  low-cardinality fields, rendering them as enums instead of generic types.
  `"string"` becomes `"enum('active' | 'pending' | 'archived')"`.
- **Numeric statistics** (`include_stats=True`): min, max, and mean for numeric
  fields. Timestamp-range numbers are detected and rendered as ISO date ranges.
- **String statistics**: min/max/avg length for string fields.
- **Boolean distribution**: skew detection (≥95% one-sided) shown as
  `"boolean (94% true)"`.
- **Always-null and always-empty detection**: fields that are always `null`,
  empty arrays, or empty objects are replaced with explicit `always_null`,
  `always_empty_array`, or `always_empty_object` markers.
- **Enum rendering** in all four formats: compact, TypeScript literal unions,
  JSON Schema `enum` keyword, and YAML.
- **Frequency display** (opt-in `include_frequency=True`): shows observation
  counts per enum value.
- **Bounded memory**: unique-value tracking caps at `unique_value_cap` (default
  100) to prevent OOM on large datasets.
- `EnumNode` type in the type tree for programmatic access to detected enums.
- CLI gains `--track-cardinality`, `--include-frequency`, and `--no-stats` flags.
- Config gains: `track_cardinality`, `enum_max_values`, `enum_cardinality_ratio`,
  `unique_value_cap`, `include_frequency`, `include_stats`, `detect_always_null`,
  `always_null_min_observations`.

- **Four output formats** — each renderer is a pure function over the type tree:
  - `result.compact` — TypeScript-flavored inline JSON (the default, unchanged).
  - `result.typescript(root_name="Root")` — full TypeScript interface declarations.
  - `result.yaml` — YAML type descriptions, cheapest in tokens for nested schemas.
  - `result.json_schema` — JSON Schema (Draft 2020-12), for Pydantic / OpenAI / Anthropic.
- `result.render(format, ...)` — explicit format dispatch with aliases (`ts`, `yml`).
- `Config` dataclass consolidating all rendering knobs:
  `detect_content_types`, `long_string_threshold`, `long_string_sample_len`, `max_depth`.
- **Content-type detection** (opt-in via `Config(detect_content_types=True)`):
  scans string values for HTML, URL, ISO date/datetime, UUID, email, and JWT
  patterns, emitting specialised type names (`html_string`, `url_string`, etc.).
  Long strings without a pattern get `"string (len≈N, sample: '...')"`.
- **Depth control** via `Config(max_depth=N)`: renderers replace subtrees beyond
  the limit with a compact summary (`{ ... 3 fields, depth 4 }`).
- **Token counting** behind the `[tokens]` optional extra (`pip install jsonhaiku[tokens]`):
  `result.token_count()`, `result.token_breakdown()`. Supports GPT-4, GPT-4o,
  and Anthropic model names (uses `cl100k_base` as a ±10% proxy).
- CLI gains `--format typescript`, `--format yaml`, `--format json_schema`,
  `--root-name`, `--detect-content-types`, and `--max-depth` flags.
- `describe(data)` — the public entry point. Returns a frozen `Result` with
  `.compact` (the LLM-facing type map), `.schema` (JSON Schema Draft 2020-12),
  `.tree` (plain dicts) and `.root` (the type tree).
- Type inference over every JSON shape: scalars, unions, nested objects,
  homogeneous and heterogeneous arrays, nullables and empty containers.
  `integer` and `float` merge to `number`; booleans never merge with integers;
  fields missing from some observations are marked optional.
- Deterministic output by construction: object fields are stored sorted and
  union members canonically ordered, so key order in the source document cannot
  change a single byte of the result.
- Values that `json.dumps` cannot serialize are described as `unknown` and raise
  an `UnsupportedValueWarning` rather than being guessed at.
- `jsonhaiku` command line interface: reads a file or standard input, writes
  `compact`, `schema` or `tree` output.

#### Project infrastructure

- `src`-layout package, PEP 561 `py.typed` marker, MIT license.
- Build with `hatchling`; version single-sourced from `src/jsonhaiku/__about__.py`.
- Tooling: `ruff` (lint + format), `mypy --strict`, `pytest` with coverage, `nox` sessions.
- CI on GitHub Actions: lint, type check, test matrix (CPython 3.10-3.14 plus
  free-threaded 3.14 on Linux, and 3.10/3.14 on macOS and Windows), aggregated
  coverage, and distribution build checks.
- Release workflow using PyPI Trusted Publishing with build attestations.
- Contributor infrastructure: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, issue forms, PR template, pre-commit hooks, Dependabot.
- Smoke and packaging tests covering the public surface and installed metadata.

[Unreleased]: https://github.com/ysnghr/jsonhaiku/commits/main
