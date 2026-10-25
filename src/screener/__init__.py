"""Screener: DSL → pandas filter → result table.

User-facing entry points:
    parse(expr) -> AST
    run(expr, universe=None) -> DataFrame
    save(name, expr) / load(name) / list_saved()
"""
from .dsl import parse, evaluate, ScreenerError  # noqa: F401
from .engine import run, save, load, list_saved, delete  # noqa: F401
