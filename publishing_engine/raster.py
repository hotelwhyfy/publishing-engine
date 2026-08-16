"""SVG to PNG, at print resolution.

Vector art is authored as SVG and rasterised before being placed in the PDF, because
embedding SVG directly is not something reportlab does. Everything here writes into a
scratch directory that the builder deletes when the book is done.
"""
from __future__ import annotations

import os

import cairosvg


def svg_to_png(src, out, width=None, height=None):
    """Rasterise *src* to *out*. Give a width, a height, or both.

    Passing both forces the output size and will distort the art if it does not share
    the source's aspect ratio — which is what full-page plates want, since they are
    stretched to the page.
    """
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    kwargs = {}
    if width:
        kwargs["output_width"] = width
    if height:
        kwargs["output_height"] = height
    cairosvg.svg2png(url=src, write_to=out, **kwargs)
    return out


def svg_string_to_png(svg, out, width=1200):
    """Rasterise an SVG held in memory — used for computed figures."""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=out, output_width=width)
    return out


def prepare(path, out, width=1400, height=None):
    """Rasterise *path* if it is SVG; pass any other image straight through."""
    if os.path.splitext(path)[1].lower() == ".svg":
        return svg_to_png(path, out, width=width, height=height)
    return path
