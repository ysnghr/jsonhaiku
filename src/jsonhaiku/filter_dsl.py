"""Safe filter expression DSL for the progressive disclosure API.

Grammar::

    expr    := or_expr
    or_expr := and_expr ('or' and_expr)*
    and_expr := comparison ('and' comparison)*
    comp    := path OP literal
    path    := identifier ('.' identifier | '[' int ']')*
    OP      := '==' | '!=' | '<' | '<=' | '>' | '>=' | 'in' | 'contains'
    literal := string | number | bool | null | '[' list ']'

No ``eval``, no ``exec``, safe by construction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

__all__ = ["FilterError", "evaluate", "parse"]

_TOKEN_PATTERNS = [
    ("STRING", r"'[^']*'"),
    ("NUMBER", r"-?\d+(?:\.\d+)?"),
    ("BOOL", r"\b(?:true|false)\b"),
    ("NULL", r"\bnull\b"),
    ("AND", r"\band\b"),
    ("OR", r"\bor\b"),
    ("IN", r"\bin\b"),
    ("CONTAINS", r"\bcontains\b"),
    ("OP", r"[!=<>]=?"),
    ("LBRACKET", r"\["),
    ("RBRACKET", r"\]"),
    ("DOT", r"\."),
    ("COMMA", r","),
    ("IDENT", r"[a-zA-Z_]\w*"),
    ("WS", r"\s+"),
]

_TOKEN_RE = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_PATTERNS))


class FilterError(ValueError):
    """Raised when a filter expression cannot be parsed or evaluated."""


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    pos: int


@dataclass(frozen=True)
class _PathExpr:
    segments: tuple[str | int, ...]


@dataclass(frozen=True)
class _Literal:
    value: Any


@dataclass(frozen=True)
class _ListLiteral:
    values: tuple[Any, ...]


@dataclass(frozen=True)
class _Comparison:
    path: _PathExpr
    op: str
    right: _Literal | _ListLiteral


@dataclass(frozen=True)
class _And:
    left: _FilterNode
    right: _FilterNode


@dataclass(frozen=True)
class _Or:
    left: _FilterNode
    right: _FilterNode


_FilterNode = _Comparison | _And | _Or


def _tokenize(expr: str) -> list[_Token]:
    tokens: list[_Token] = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if m is None:
            msg = f"unexpected character at position {pos}: {expr[pos:]!r}"
            raise FilterError(msg)
        kind = m.lastgroup
        if kind is None:
            msg = f"unexpected character at position {pos}"
            raise FilterError(msg)
        if kind != "WS":
            tokens.append(_Token(kind=kind, value=m.group(), pos=pos))
        pos = m.end()
    return tokens


class _Parser:
    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> _Token | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _advance(self) -> _Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, kind: str) -> _Token:
        tok = self._peek()
        if tok is None or tok.kind != kind:
            expected = kind
            got = tok.value if tok else "end of input"
            msg = f"expected {expected}, got {got!r}"
            raise FilterError(msg)
        return self._advance()

    def parse(self) -> _FilterNode:
        """Parse the full expression."""
        node = self._or_expr()
        if self._pos < len(self._tokens):
            tok = self._tokens[self._pos]
            msg = f"unexpected token {tok.value!r} at position {tok.pos}"
            raise FilterError(msg)
        return node

    def _or_expr(self) -> _FilterNode:
        left: _FilterNode = self._and_expr()
        while self._peek() and self._peek().kind == "OR":  # type: ignore[union-attr]
            self._advance()
            right: _FilterNode = self._and_expr()
            left = _Or(left=left, right=right)
        return left

    def _and_expr(self) -> _FilterNode:
        left: _FilterNode = self._comparison()
        while self._peek() and self._peek().kind == "AND":  # type: ignore[union-attr]
            self._advance()
            right: _FilterNode = self._comparison()
            left = _And(left=left, right=right)
        return left

    def _comparison(self) -> _Comparison:
        path = self._path()
        op = self._operator()
        right = self._literal_or_list()
        return _Comparison(path=path, op=op, right=right)

    def _path(self) -> _PathExpr:
        segments: list[str | int] = []
        tok = self._expect("IDENT")
        segments.append(tok.value)

        while self._peek():
            pk = self._peek()
            if pk is None:
                break
            if pk.kind == "DOT":
                self._advance()
                ident = self._expect("IDENT")
                segments.append(ident.value)
            elif pk.kind == "LBRACKET":
                self._advance()
                idx = self._expect("NUMBER")
                segments.append(int(idx.value))
                self._expect("RBRACKET")
            else:
                break

        return _PathExpr(segments=tuple(segments))

    def _operator(self) -> str:
        pk = self._peek()
        if pk is not None and pk.kind == "IN":
            self._advance()
            return "in"
        if pk is not None and pk.kind == "CONTAINS":
            self._advance()
            return "contains"
        tok = self._expect("OP")
        if tok.value not in ("==", "!=", "<", "<=", ">", ">="):
            msg = f"unsupported operator: {tok.value!r}"
            raise FilterError(msg)
        return tok.value

    def _literal_or_list(self) -> _Literal | _ListLiteral:
        pk = self._peek()
        if pk is not None and pk.kind == "LBRACKET":
            return self._list_literal()
        return self._literal()

    def _literal(self) -> _Literal:
        tok = self._peek()
        if tok is None:
            msg = "expected a literal value, got end of input"
            raise FilterError(msg)

        if tok.kind == "STRING":
            self._advance()
            return _Literal(value=tok.value[1:-1])
        if tok.kind == "NUMBER":
            self._advance()
            val: int | float = float(tok.value) if "." in tok.value else int(tok.value)
            return _Literal(value=val)
        if tok.kind == "BOOL":
            self._advance()
            return _Literal(value=tok.value == "true")
        if tok.kind == "NULL":
            self._advance()
            return _Literal(value=None)

        msg = f"expected a literal, got {tok.value!r}"
        raise FilterError(msg)

    def _list_literal(self) -> _ListLiteral:
        self._expect("LBRACKET")
        values: list[object] = []

        if self._peek() and self._peek().kind != "RBRACKET":  # type: ignore[union-attr]
            values.append(self._literal().value)
            while self._peek() and self._peek().kind == "COMMA":  # type: ignore[union-attr]
                self._advance()
                values.append(self._literal().value)

        self._expect("RBRACKET")
        return _ListLiteral(values=tuple(values))


def parse(expr: str) -> _FilterNode:
    """Parse a filter expression into an AST.

    Raises:
        FilterError: If the expression is syntactically invalid.
    """
    tokens = _tokenize(expr)
    if not tokens:
        msg = "empty filter expression"
        raise FilterError(msg)
    return _Parser(tokens).parse()


def evaluate(record: object, expr: str) -> bool:
    """Evaluate a filter expression against a record.

    Raises:
        FilterError: If the expression is invalid.
    """
    ast = parse(expr)
    return _eval_node(record, ast)


def _eval_node(record: object, node: _FilterNode) -> bool:
    if isinstance(node, _Comparison):
        return _eval_comparison(record, node)
    if isinstance(node, _And):
        return _eval_node(record, node.left) and _eval_node(record, node.right)
    return _eval_node(record, node.left) or _eval_node(record, node.right)


def _resolve_path(record: object, path: _PathExpr) -> object:
    current: object = record
    for seg in path.segments:
        if isinstance(seg, str):
            if not isinstance(current, dict):
                return None
            current = current.get(seg)
        elif isinstance(seg, int):
            if not isinstance(current, list | tuple) or seg >= len(current):
                return None
            current = current[seg]
    return current


def _eval_comparison(record: object, comp: _Comparison) -> bool:
    left = _resolve_path(record, comp.path)
    right_val: object = (
        comp.right.values if isinstance(comp.right, _ListLiteral) else comp.right.value
    )

    return _apply_op(left, comp.op, right_val)


def _apply_op(left: object, op: str, right: object) -> bool:
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "in":
        return left in right if isinstance(right, tuple) else False
    if op == "contains":
        return right in left if isinstance(left, str) and isinstance(right, str) else False
    return _compare_ordered(left, op, right) if op in ("<", "<=", ">", ">=") else False


_CMP_OPS: dict[str, str] = {"<": "__lt__", "<=": "__le__", ">": "__gt__", ">=": "__ge__"}


def _compare_ordered(left: object, op: str, right: object) -> bool:
    if not isinstance(left, int | float) or not isinstance(right, int | float):
        return False
    method = _CMP_OPS.get(op)
    if method is None:
        return False
    return bool(getattr(left, method)(right))
