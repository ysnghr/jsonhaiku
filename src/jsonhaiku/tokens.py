"""Token counting via ``tiktoken``, behind the ``[tokens]`` extra.

The core library has zero heavy dependencies.  ``tiktoken`` is pulled in only
when a user installs ``pip install jsonhaiku[tokens]``.  If it is absent and
this module is called, a clear :class:`ImportError` explains how to fix it.

Anthropic does not ship a public tokenizer.  We use OpenAI's ``cl100k_base``
encoding as a close proxy — documented ±10%% error — which is the same
approach Anthropic's own documentation suggests for estimation.
"""

from __future__ import annotations

__all__ = ["count_tokens"]

_ANTHROPIC_PREFIXES = frozenset(
    {
        "claude",
        "anthropic",
    }
)

_MODEL_TO_ENCODING: dict[str, str] = {
    "gpt-4": "cl100k_base",
    "gpt-4o": "o200k_base",
    "gpt-3.5-turbo": "cl100k_base",
}


def count_tokens(text: str, *, model: str = "gpt-4") -> int:
    """Count the number of tokens in ``text``.

    Args:
        text: The string to tokenise.
        model: A model name (``"gpt-4"``, ``"claude-3-5"``, …) or a tiktoken
            encoding name (``"cl100k_base"``).

    Returns:
        Token count.

    Raises:
        ImportError: If ``tiktoken`` is not installed.
    """
    try:
        import tiktoken  # noqa: PLC0415
    except ImportError:
        msg = (
            "tiktoken is required for token counting. "
            "Install it with: pip install jsonhaiku[tokens]"
        )
        raise ImportError(msg) from None

    encoding_name = _resolve_encoding(model)
    enc = tiktoken.get_encoding(encoding_name)
    return len(enc.encode(text))


def _resolve_encoding(model: str) -> str:
    """Map a model name to a tiktoken encoding name."""
    if model in _MODEL_TO_ENCODING:
        return _MODEL_TO_ENCODING[model]

    lower = model.lower()
    for prefix in _ANTHROPIC_PREFIXES:
        if lower.startswith(prefix):
            return "cl100k_base"

    try:
        import tiktoken  # noqa: PLC0415

        tiktoken.get_encoding(model)
    except Exception:  # noqa: BLE001
        return "cl100k_base"
    else:
        return model
