"""Tiny screener DSL.

Grammar (intentionally minimal):

    expression := term ( ("AND" | "OR") term )*
    term       := "NOT"? atom
    atom       := "(" expression ")" | comparison
    comparison := field op value
    field      := IDENT ("." IDENT)*
    op         := "<" | "<=" | ">" | ">=" | "==" | "!=" | "BETWEEN" | "IN"
    value      := NUMBER | STRING | "[" NUMBER ("," NUMBER)* "]"

Examples:
    "ret_1m > 10 AND rsi_14 < 70"
    "rs_rating >= 80 AND close > sma_50 AND volume_spike_z > 1.5"
    "sector == 'Banks' AND ret_1y BETWEEN [-20, 50]"
    "is_breakout_20d == 1 AND delivery_pct >= 50"

The DSL is evaluated against a single pandas DataFrame; fields map directly to
DataFrame columns. The engine.run() function assembles the DataFrame from
joins of EquityFeaturesEOD + AnomalyFlags + SymbolSector + BhavcopyEOD.
"""
from __future__ import annotations

import operator
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd


class ScreenerError(Exception):
    pass


_OPS = {
    "<": operator.lt, "<=": operator.le,
    ">": operator.gt, ">=": operator.ge,
    "==": operator.eq, "!=": operator.ne,
}

_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<NUMBER>-?\d+(?:\.\d+)?)
      | (?P<STRING>'[^']*'|"[^"]*")
      | (?P<LBRACKET>\[)
      | (?P<RBRACKET>\])
      | (?P<COMMA>,)
      | (?P<LPAREN>\()
      | (?P<RPAREN>\))
      | (?P<OP><=|>=|==|!=|<|>)
      | (?P<KW>AND|OR|NOT|BETWEEN|IN)
      | (?P<IDENT>[A-Za-z_][A-Za-z0-9_\.]*)
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


@dataclass
class Token:
    kind: str
    value: Any


def _tokenize(s: str) -> list[Token]:
    out: list[Token] = []
    pos = 0
    while pos < len(s):
        m = _TOKEN_RE.match(s, pos)
        if not m:
            if s[pos].isspace():
                pos += 1
                continue
            raise ScreenerError(f"Unexpected char at {pos}: {s[pos]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind is None:
            continue
        v = m.group(kind)
        if kind == "NUMBER":
            v = float(v) if "." in v else int(v)
        elif kind == "STRING":
            v = v[1:-1]
        elif kind == "KW":
            v = v.upper()
        elif kind == "IDENT":
            v = v.lower()
        out.append(Token(kind, v))
    return out


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _eat(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def _accept(self, kind: str, value: Any = None) -> Token | None:
        t = self._peek()
        if t and t.kind == kind and (value is None or t.value == value):
            return self._eat()
        return None

    def _expect(self, kind: str, value: Any = None) -> Token:
        t = self._accept(kind, value)
        if t is None:
            raise ScreenerError(f"Expected {kind} {value}, got {self._peek()}")
        return t

    def parse(self) -> dict:
        node = self._expression()
        if self.pos < len(self.tokens):
            raise ScreenerError(f"Unparsed trailing tokens: {self.tokens[self.pos:]}")
        return node

    def _expression(self) -> dict:
        left = self._term()
        while True:
            t = self._peek()
            if t and t.kind == "KW" and t.value in {"AND", "OR"}:
                self._eat()
                right = self._term()
                left = {"type": "binop", "op": t.value, "left": left, "right": right}
            else:
                break
        return left

    def _term(self) -> dict:
        t = self._peek()
        if t and t.kind == "KW" and t.value == "NOT":
            self._eat()
            return {"type": "not", "expr": self._term()}
        return self._atom()

    def _atom(self) -> dict:
        if self._accept("LPAREN"):
            node = self._expression()
            self._expect("RPAREN")
            return node
        return self._comparison()

    def _comparison(self) -> dict:
        field_tok = self._expect("IDENT")
        op_tok = self._peek()
        if op_tok is None:
            raise ScreenerError("Expected operator after field")
        if op_tok.kind == "OP":
            self._eat()
            value_tok = self._eat()
            if value_tok.kind not in {"NUMBER", "STRING"}:
                raise ScreenerError(f"Expected literal, got {value_tok}")
            return {"type": "cmp", "field": field_tok.value, "op": op_tok.value,
                    "value": value_tok.value}
        if op_tok.kind == "KW" and op_tok.value == "BETWEEN":
            self._eat()
            self._expect("LBRACKET")
            lo = self._eat()
            self._expect("COMMA")
            hi = self._eat()
            self._expect("RBRACKET")
            return {"type": "between", "field": field_tok.value,
                    "low": lo.value, "high": hi.value}
        if op_tok.kind == "KW" and op_tok.value == "IN":
            self._eat()
            self._expect("LBRACKET")
            items: list[Any] = []
            while True:
                v = self._eat()
                items.append(v.value)
                if not self._accept("COMMA"):
                    break
            self._expect("RBRACKET")
            return {"type": "in", "field": field_tok.value, "values": items}
        raise ScreenerError(f"Unexpected token after field: {op_tok}")


def parse(expr: str) -> dict:
    """Parse DSL string into an AST dict."""
    return _Parser(_tokenize(expr)).parse()


def evaluate(node: dict, df: pd.DataFrame) -> pd.Series:
    """Evaluate AST against a DataFrame; returns a boolean mask Series."""
    t = node["type"]
    if t == "binop":
        left = evaluate(node["left"], df)
        right = evaluate(node["right"], df)
        return (left & right) if node["op"] == "AND" else (left | right)
    if t == "not":
        return ~evaluate(node["expr"], df)
    if t == "cmp":
        col = _col(df, node["field"])
        return _OPS[node["op"]](col, node["value"])
    if t == "between":
        col = _col(df, node["field"])
        return col.between(node["low"], node["high"])
    if t == "in":
        col = _col(df, node["field"])
        return col.isin(node["values"])
    raise ScreenerError(f"Unknown AST node: {node}")


def _col(df: pd.DataFrame, field: str) -> pd.Series:
    if field not in df.columns:
        raise ScreenerError(
            f"Unknown field {field!r}. Available: {sorted(df.columns)[:25]}..."
        )
    return df[field]
