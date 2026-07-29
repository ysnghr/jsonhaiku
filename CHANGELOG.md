# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While the version is `0.x`, minor bumps may contain breaking changes. From
`1.0.0` onwards, breaking changes require a major bump and one minor release of
deprecation warnings first.

## [Unreleased]

### Added

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
