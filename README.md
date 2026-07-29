# jsonhaiku

**Compact, LLM-friendly descriptions of large JSON payloads.**

[![CI](https://github.com/ysnghr/jsonhaiku/actions/workflows/ci.yml/badge.svg)](https://github.com/ysnghr/jsonhaiku/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%E2%80%93%203.14-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Checked with mypy](https://img.shields.io/badge/mypy-strict-2a6db2)](https://mypy-lang.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Turn a multi-megabyte API response into a few kilobytes of structured, type-aware description that an LLM can actually reason about — without ever having to see the raw data.

> **Status:** early development. API is not yet stable. Not published to PyPI yet.

## The problem

You have a large JSON blob — an API response, a log dump, a scraped dataset — and you want an LLM to help you work with it. The obvious approach is to paste the JSON into the prompt. It doesn't work:

- The payload doesn't fit in the context window.
- Even if it fits, you're burning thousands of tokens on repeated field names and values.
- The LLM sees leaves, not shape — it can't tell you "how many event types are there" without scanning every record.

The obvious fix is to hand-write a schema. That's tedious and it throws away information the LLM would actually use, like which fields are enums, which are always null, and what typical values look like.

## What jsonhaiku does

Given a JSON value — one object, a list of thousands, a streamed multi-gigabyte file — jsonhaiku produces a small, expressive description that captures:

- **Types**, in a TypeScript-flavored compact format LLMs parse well.
- **Enums** — fields that only ever take a handful of values are surfaced as unions, not `"string"`.
- **Statistics** — numeric ranges, string length distributions, boolean skews.
- **Always-null fields** — the noise that clutters real API responses, flagged so the LLM can ignore it.
- **Representative samples** — a few real records chosen to cover the edge cases, not just `data[0]`.

The output is designed to be dropped into a prompt as-is, or exposed to an agent via an MCP server so it can drill into paths on demand.

## Quick look

Given a JSON response with 500 conference session records, instead of pasting hundreds of KB into the prompt, you'd hand the LLM this:

```
[{
  "id": "integer",
  "code": "string (len 3..6)",
  "title": "string",
  "duration": "integer (min=30, max=240, mean=95)",
  "content": {
    "outline": "html_string | null",
    "internal_comment": "always_null"
  },
  "room": {
    "id": "integer",
    "name": "enum('HALL A' | 'HALL B' | 'HALL C' | 'HALL D' | 'HALL E')"
  },
  "session_type": {
    "name": "enum('Symposium' | 'Workshop' | 'Special Interest' | 'Plenary')"
  }
}]
```

Every field is now something the LLM can reason about: it knows the enums, it knows what's noise, it knows the numeric ranges. Roughly a 100x token reduction vs. the raw payload, with more usable information — not less.

## Install

Not on PyPI yet. Until the first release, install from source:

```bash
pip install "git+https://github.com/ysnghr/jsonhaiku"
# or, with uv:
uv pip install "git+https://github.com/ysnghr/jsonhaiku"
```

Once released, this becomes:

```bash
pip install jsonhaiku              # core, zero dependencies
pip install "jsonhaiku[tokens]"    # + tiktoken, for token counting
```

Requires Python 3.10 or newer. The core package has no runtime dependencies and
ships type hints ([PEP 561](https://peps.python.org/pep-0561/)).

## Usage

```python
from jsonhaiku import describe

result = describe(data)

result.compact          # str  — the TypeScript-flavored type map (default)
result.typescript()     # str  — TypeScript interfaces
result.yaml             # str  — YAML type description
result.json_schema      # dict — JSON Schema (Draft 2020-12)
result.schema           # dict — alias for json_schema
result.tree             # dict — the type tree as plain dicts
result.root             # the internal type tree, for advanced use
```

`print(result)` gives you the compact rendering, so it drops straight into an
f-string in a prompt.

### Output formats

jsonhaiku renders to four formats. Each addresses a different use case:

**compact** — the default. TypeScript-flavored inline JSON.
```python
>>> print(describe([{"id": 1, "name": "a"}, {"id": 2, "name": None}]))
[{
  "id": "integer",
  "name": "string | null"
}]
```

**typescript** — full TypeScript interfaces. Best-in-class for GPT-4 and Claude.
```python
>>> print(result.typescript(root_name="Session"))
interface Session {
  id: number;
  name: string | null;
}
```

**yaml** — YAML type description. Cheapest in tokens for deeply nested schemas.
```python
>>> print(result.yaml)
id: integer
name: string | null
```

**json_schema** — Standard JSON Schema (Draft 2020-12). For Pydantic, OpenAI
structured outputs, Anthropic tool schemas.
```python
>>> import json
>>> print(json.dumps(result.json_schema, indent=2))
```

Use `result.render(format, ...)` for explicit format selection:
```python
result.render("typescript", root_name="Session")
result.render("yaml")
```

### Content-type detection

Opt-in scanning recognises common string patterns:

```python
from jsonhaiku import describe, Config

cfg = Config(detect_content_types=True)
result = describe(data, config=cfg)
```

This detects HTML, URLs, ISO dates, UUIDs, emails, and JWTs — emitting
`html_string`, `url_string`, `iso_datetime`, etc. instead of plain `string`.
Long strings without a pattern get a length and sample annotation:
`"string (len≈523, sample: 'The quick brown fox…')"`.

### Depth control

Truncate deeply nested schemas:

```python
result = describe(data, config=Config(max_depth=2))
# At max_depth, objects become: { ... 3 fields, depth 4 }
```

### Token counting

Compare how many tokens each format costs:

```python
pip install "jsonhaiku[tokens]"   # pulls in tiktoken
```

```python
result.token_count()                       # compact form, gpt-4 encoding
result.token_count(model="claude-3-5")     # Anthropic estimate (±10%)
result.token_count(fmt="typescript")       # count for a specific format
result.token_breakdown()                   # all four formats side by side
# {"compact": 412, "typescript": 385, "json_schema": 891, "yaml": 361}
```

### Rules worth knowing

- `"string | null"` — the value was sometimes null. `"string | undefined"` — the
  key was sometimes missing. Different facts, never conflated.
- `integer` and `float` in one field become `number`; JSON has one number type.
- `[]` means "an array we only ever saw empty", `{}` an object with no keys.
- Object keys are sorted and unions are canonically ordered, so the same data
  always produces byte-identical output — good for caching, diffing and prompt
  stability.
- Values `json.dumps` could not serialize are described as `unknown`, with a
  warning. jsonhaiku never guesses.

### From the shell

```bash
curl -s https://api.example.com/sessions | jsonhaiku
jsonhaiku response.json --format typescript --root-name Session
jsonhaiku response.json --format yaml
jsonhaiku response.json --format json_schema
jsonhaiku response.json --detect-content-types --max-depth 3
```

### Planned API

Not built yet — see the roadmap below:

```python
result.samples            # list — smart-selected representative records
```

For agentic exploration of large payloads, a stateful interface with path-scoped access:

```python
from jsonhaiku import JsonHaiku

h = JsonHaiku(data)
h.overview()                                # top-level orientation
h.describe(path="$[*].room")                # schema of a subtree
h.enum(path="$[*].session_type.name")       # unique values of a field
h.filter(path="$[*]", where="duration > 60 and room.name == 'HALL H'")
```

## Positioning

- **Not a schema validator.** Use `pydantic` or `jsonschema` for that. jsonhaiku describes; it doesn't enforce.
- **Not a schema generator.** [`GenSON`](https://github.com/wolverdude/GenSON) already does JSON Schema inference well; jsonhaiku is the LLM-consumer-focused layer above it.
- **Not a JSON viewer.** Interactive tree browsers exist. jsonhaiku is a machine-to-machine format aimed at prompts and tool calls.

## Roadmap — coming soon

Actively developed. What's done and what's landing next, roughly in order:

- [x] The core `describe()` API, compact rendering, JSON Schema, and a CLI.
- [x] More output formats (TypeScript, YAML), content-type detection, and token counting.
- [ ] Enum detection and value statistics.
- [ ] Smart representative sample selection.
- [ ] A stateful path-scoped API for agent-driven exploration.
- [ ] An MCP server for Claude Desktop, Cursor, Continue, and other MCP clients.
- [ ] Streaming support for JSON files that don't fit in memory.

## Development

```bash
git clone https://github.com/ysnghr/jsonhaiku && cd jsonhaiku
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pre-commit install --install-hooks
pytest
```

`make check` runs exactly what CI runs: `ruff check`, `ruff format --check`,
`mypy --strict`, and the test suite. `nox -s tests` runs the suite on every
supported interpreter (3.10–3.14, including free-threaded 3.14).

Contributions are very welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md) for
the ground rules, and [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md). Security
issues go through [SECURITY.md](./SECURITY.md), not the issue tracker.

## License

MIT — see [LICENSE](./LICENSE).
