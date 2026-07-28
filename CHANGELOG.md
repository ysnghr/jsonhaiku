# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While the version is `0.x`, minor bumps may contain breaking changes. From
`1.0.0` onwards, breaking changes require a major bump and one minor release of
deprecation warnings first.

## [Unreleased]

### Added

- Project scaffolding: `src`-layout package, PEP 561 `py.typed` marker, MIT license.
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
