# Contributing to jsonhaiku

Thanks for considering a contribution. This document should let you go from
`git clone` to a green test run without asking anyone anything. If it doesn't,
that's a bug — please open an issue.

## TL;DR

```bash
git clone https://github.com/ysnghr/jsonhaiku
cd jsonhaiku
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pre-commit install --install-hooks
pytest
```

Everything CI checks, in one command: `make check` (or `nox`).

## Development setup

We use [uv](https://docs.astral.sh/uv/) — it's the fastest path and it can
fetch interpreters for you. Plain `pip` works too: `pip install -e ".[dev]"`.

| Task | Command | Notes |
|---|---|---|
| Install | `make install` | creates `.venv`, installs `dev` extras |
| Format + autofix | `make fmt` | `ruff check --fix` then `ruff format` |
| Lint | `make lint` | no writes; what CI runs |
| Type check | `make typecheck` | `mypy` in strict mode, over `src` and `tests` |
| Test | `make test` | `pytest` with coverage |
| HTML coverage | `make cov` | writes `htmlcov/` |
| All of CI | `make check` | |
| Every Python version | `nox -s tests` | uv downloads 3.10–3.14 as needed |
| Build + validate dist | `make build` | |

Supported interpreters: CPython 3.10 through 3.14, including free-threaded
3.14. If a change can't work on 3.10, it needs a discussion first.

## Ground rules for code

- **Typed, strictly.** `mypy --strict` covers `src` *and* `tests`. No bare
  `# type: ignore` — use `# type: ignore[code]` (enforced by
  `ignore-without-code`).
- **The core library has zero runtime dependencies.** That's a feature, not an
  accident. Anything heavier (tokenizers, MCP transport, streaming parsers)
  goes behind an extra and is imported lazily. A test enforces this.
- **Public API is explicit.** If it isn't in `__all__` with a docstring and a
  test, it isn't public.
- **`from __future__ import annotations` at the top of every module.** Ruff
  adds it for you.
- **Google-style docstrings** on every public module, class and function.
- Line length is 100. Ruff owns formatting; don't argue with it in review.

## Tests

- `pytest` with coverage; the merged CI run must be at **100%** line and branch
  coverage. If a line genuinely can't be covered, exclude it explicitly in
  `[tool.coverage.report]` with a comment saying why.
- Warnings are errors (`filterwarnings = ["error"]`). If a dependency warns,
  handle it or narrow the filter in `pyproject.toml` with a reason.
- Snapshot tests use [syrupy](https://github.com/syrupy-project/syrupy):
  `pytest --snapshot-update` after an intentional rendering change, and
  **review the snapshot diff** — that diff is what an LLM will actually see.
- Property-based tests use [Hypothesis](https://hypothesis.works/). Inference
  code is exactly the kind of thing property tests find bugs in; prefer them
  for anything that walks arbitrary JSON.
- Mark anything slower than a second with `@pytest.mark.slow`.

## Commits and pull requests

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(render): add YAML renderer
fix(infer): treat empty list as unknown element type
docs: clarify enum threshold in README
test(samples): cover single-record payloads
build: raise minimum hatchling to 1.27
ci: pin setup-uv to v9
refactor|perf|chore: ...
```

Breaking changes get a `!` (`feat!: ...`) and a `BREAKING CHANGE:` footer.

For pull requests:

1. Branch off `main`. One logical change per PR.
2. Add or update tests. A PR that changes behaviour without a failing-then-
   passing test will be asked for one.
3. Add a `CHANGELOG.md` entry under `## [Unreleased]`.
4. Make sure `make check` is green locally — CI runs the same thing on five
   interpreters and three operating systems.
5. Describe *why*, not just *what*. Link the issue.

Small, focused PRs get merged in hours. Large unannounced PRs get stuck. For
anything bigger than a bug fix, open an issue first and sketch the design —
that conversation is cheaper than a rejected 800-line diff.

## Versioning and releases

The version lives in exactly one place: `src/jsonhaiku/__about__.py`.

- `0.x.y` — minor bumps may break the API. It's early; that's the deal.
- `1.0.0` — an API stability commitment. Not before the progressive-disclosure
  API has settled and been used in anger.
- After 1.0, breaking changes need a `DeprecationWarning` shipped at least one
  minor release earlier.

Releases are tag-driven: bump `__about__.py`, move the `Unreleased` changelog
section under a dated version heading, then push a `vX.Y.Z` tag. CI verifies
the tag matches the version and publishes via PyPI Trusted Publishing.

## Project layout

```
src/jsonhaiku/        the package (src-layout: tests run against an install)
  __about__.py        the one true version string
  __init__.py         public API surface
  py.typed            PEP 561 marker — do not delete
tests/                mirrors src/ module for module
.github/workflows/    ci.yml (every push/PR), release.yml (tags)
noxfile.py            multi-interpreter task runner
```

Why src-layout: with a flat layout, `import jsonhaiku` succeeds from the
working directory even when the package is broken, so packaging bugs reach
users. Here, tests only pass against a real install.

## Code of Conduct

This project follows the [Contributor Covenant](./CODE_OF_CONDUCT.md).
Be the kind of reviewer you'd want reviewing your first PR.
