"""Declared figures: graphs and charts described in a book's config, drawn by the engine.

A book that needs a graph should not need a programmer. Instead of shipping Python that
emits SVG, a book declares what the figure *is* and the engine draws it in the book's own
colours::

    [[figure]]
    name = "limit"
    x = [-1, 3]

    [[figure.curve]]
    of = "(x^2 - 1)/(x - 1)"
    holes = [1]

    [[figure.point]]
    at = [1, 2]
    style = "open"
    label = "approaches 2"

Referred to as ``figure = "limit"`` in an atlas entry, or ``![Caption](plot:limit)``
anywhere prose or verse content can carry an image.

Expressions are evaluated under a whitelist — see :mod:`~publishing_engine.plotting.expr`
— so a config file cannot run arbitrary code.
"""
from __future__ import annotations

from .draw import FigureError, aspect, render
from .expr import ExpressionError, compile_expr, evaluate

__all__ = ["render", "aspect", "FigureError", "ExpressionError", "compile_expr", "evaluate"]
