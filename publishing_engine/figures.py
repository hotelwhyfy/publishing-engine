"""Where a book's figures come from.

Two sources, in order:

**Declared** — ``[[figure]]`` tables in the book's config, drawn by
:mod:`publishing_engine.plotting`. This is the usual way, and needs no code.

**Computed** — a Python module the book names, for artwork that genuinely has to be
generated. The escape hatch::

    [book]
    figures = "figures.py"          # a file beside the book config
    figures = "mypackage.figures"   # or any importable module

which supplies:

``figure_svg(name) -> str``
    the figure named *name*, as a complete SVG document

``aspect(name) -> float``
    its width divided by its height, used to place it before it is rasterised

A book may use either or both; a declared figure wins if both define the same name.
"""
from __future__ import annotations

import importlib
import importlib.util
import os

from . import plotting


class FigureError(Exception):
    """A figure is missing, or a book's figure module does not implement the interface."""


class _Module:
    """A loaded figure module, with the older function name accepted as an alias."""

    def __init__(self, module, origin):
        self.origin = origin
        self._svg = getattr(module, "figure_svg", None) or getattr(module, "graph_svg", None)
        self._aspect = getattr(module, "aspect", None)
        if self._svg is None or self._aspect is None:
            raise FigureError(f"{origin} must define figure_svg(name) and aspect(name)")

    def svg(self, name):
        return self._svg(name)

    def aspect(self, name):
        return float(self._aspect(name))


def load_module(spec, book_dir="."):
    """Load *spec* — a path to a .py file beside the book, or a dotted module name."""
    if not spec:
        raise FigureError("no figure module named")
    path = spec if os.path.isabs(spec) else os.path.join(book_dir, spec)
    if spec.endswith(".py") or os.path.exists(path):
        if not os.path.exists(path):
            raise FigureError(f"no figure module at {path}")
        name = os.path.splitext(os.path.basename(path))[0]
        loader = importlib.util.spec_from_file_location(f"_figures_{name}", path)
        module = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(module)
        return _Module(module, path)
    try:
        module = importlib.import_module(spec)
    except ImportError as exc:
        raise FigureError(f"cannot import figure module '{spec}': {exc}") from exc
    return _Module(module, spec)


class Figures:
    """Every figure a book can draw, from whichever source defines it."""

    def __init__(self, book):
        self.book = book
        self.declared = dict(book.figures)
        self._module = None
        self._module_failed = None

    def _module_source(self):
        if self._module is None and self._module_failed is None:
            if not self.book.graphs:
                self._module_failed = FigureError(
                    "this book declares no [[figure]] tables and names no figure module")
            else:
                try:
                    self._module = load_module(self.book.graphs, self.book.dir)
                except FigureError as exc:
                    self._module_failed = exc
        return self._module

    def __contains__(self, name):
        if name in self.declared:
            return True
        try:
            module = self._module_source()
        except FigureError:
            return False
        return module is not None

    def _resolve(self, name):
        if name in self.declared:
            return None
        module = self._module_source()
        if module is None:
            raise FigureError(
                f"no figure named '{name}': {self._module_failed}")
        return module

    def svg(self, name):
        module = self._resolve(name)
        if module is None:
            return plotting.render(self.declared[name], self.book.theme)
        return module.svg(name)

    def aspect(self, name):
        module = self._resolve(name)
        if module is None:
            return plotting.aspect(self.declared[name])
        return module.aspect(name)


def for_book(book):
    return Figures(book)
