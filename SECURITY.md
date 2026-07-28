# Security Policy

## Supported versions

jsonhaiku is pre-1.0. Security fixes land on the latest release only; there are
no backports until a `1.x` line exists.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private reporting:
[Security → Report a vulnerability](https://github.com/ysnghr/jsonhaiku/security/advisories/new).

Please include:

- the version of jsonhaiku and the Python interpreter,
- a minimal payload or snippet that reproduces the issue,
- what you expected, and what happened instead.

You'll get an acknowledgement within 72 hours and an assessment within seven
days. If a fix is warranted, we'll coordinate a release and credit you in the
advisory unless you'd rather stay anonymous.

## Threat model

jsonhaiku's job is to read untrusted JSON and describe it. Treat every input as
hostile. In scope:

- Unbounded memory or CPU growth from adversarial payloads (deep nesting, huge
  key sets, pathological string sizes) — a description should be cheap to
  produce no matter what the input looks like.
- Any crash that isn't a documented, typed exception.
- Leaking values that were meant to be redacted or summarised, including
  through samples, statistics, or error messages.
- Code execution or filesystem access triggered by input content.

Out of scope:

- The correctness or safety of whatever you do with the description afterwards,
  including prompt injection carried inside your own data. jsonhaiku describes
  content; it does not sanitise it for an LLM. If your payloads contain
  attacker-controlled text, treat the description as untrusted input to your
  model, exactly as you would the raw JSON.
- Denial of service caused by deliberately passing multi-gigabyte input to the
  in-memory API rather than the streaming API.
