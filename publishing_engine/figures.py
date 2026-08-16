"""Loading a book's computed figures.

Some books draw their figures rather than storing them: a chart whose data would be
tedious to keep in sync with the text is better generated. A book points at a module
that knows how to draw its own figures::

    [book]
    figures = "figures.py"          # a file beside the book config
    figures = "mypackage.figures"   # or any importable module

The module supplies two functions:

``figure_svg(name) -> str``
    the figure named *name*, as a complete SVG document

``aspect(name) -> float``
    its width divided by its height, used to place it before it is rasterised

Nothing else is required, and nothing about the figures is known to the engine — a book
is free to compute them however it likes.
"""
from __future__ import annotations

import importlib
import importlib.util
import os


class FigureError(Exception):
    """A book's figure module is missing or does not implement the interface."""


class Figures:
    """A loaded figure module, with the older function name accepted as an alias."""

    def __init__(self, module, origin):
        self.module = module
        self.origin = origin
        self._svg = getattr(module, "figure_svg", None) or getattr(module, "graph_svg", None)
        self._aspect = getattr(module, "aspect", None)
        if self._svg is None or self._aspect is None:
            raise FigureError(
                f"{origin} must define figure_svg(name) and aspect(name)")

    def svg(self, name) -> str:
        return self._svg(name)

    def aspect(self, name) -> float:
        return float(self._aspect(name))


def load(spec, book_dir=".") -> Figures:
    """Load *spec* — a path to a .py file beside the book, or a dotted module name."""
    if not spec:
        raise FigureError("this template needs [book].figures to name a figure module")

    path = spec if os.path.isabs(spec) else os.path.join(book_dir, spec)
    if spec.endswith(".py") or os.path.exists(path):
        if not os.path.exists(path):
            raise FigureError(f"no figure module at {path}")
        name = os.path.splitext(os.path.basename(path))[0]
        loader = importlib.util.spec_from_file_location(f"_figures_{name}", path)
        module = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(module)
        return Figures(module, path)

    try:
        module = importlib.import_module(spec)
    except ImportError as exc:
        raise FigureError(f"cannot import figure module '{spec}': {exc}") from exc
    return Figures(module, spec)
