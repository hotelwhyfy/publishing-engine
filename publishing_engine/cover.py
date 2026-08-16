"""Cover wraps, one per trim.

A cover is a single flat sheet carrying the back panel, the spine, and the front panel,
sized around the finished book. How much sheet that takes depends on the binding:

**wrap** (perfect binding)
    back panel, spine, front panel, plus bleed on all four edges. The spine is the page
    count times the per-page thickness of the chosen paper.

**case** (hardcover)
    the same three regions, but each board is larger than the trim and the sheet has to
    reach around it: a turn-in on every outer edge, a hinge either side of the spine,
    and a spine thickened by the boards themselves.

Panel art is supplied by the book as ``art/front-cover.svg`` and ``art/back-cover.svg``.
For a wrap the panels are stretched to the exact bleed size. For a case they are placed
at their own proportions across each board's trim area and allowed to bleed past the top
and bottom edges, so art drawn for one binding can be reused for the other.
"""
from __future__ import annotations

import os

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

from . import fonts, raster

INCH = 72.0
DPI = 300


class CoverArtMissing(Exception):
    """A book asked for a cover but has no panel art."""


def has_art(art_dir) -> bool:
    return all(os.path.exists(os.path.join(art_dir, f"{side}-cover.svg"))
               for side in ("front", "back"))


def _panels(art_dir, render_dir, width_px, height_px=None):
    out = {}
    for side in ("front", "back"):
        png = os.path.join(render_dir, f"cover-{side}-{width_px}x{height_px or 'auto'}.png")
        raster.svg_to_png(os.path.join(art_dir, f"{side}-cover.svg"), png,
                          width=width_px, height=height_px)
        out[side] = png
    return out


def _wrap(book, trim, pages, art_dir, render_dir, dist_dir):
    bleed = trim.bleed
    spine = trim.spine(pages)
    width = (2 * trim.width + spine + 2 * bleed) * INCH
    height = (trim.height + 2 * bleed) * INCH
    panel_w = (trim.width + bleed) * INCH

    panels = _panels(art_dir, render_dir,
                     round((trim.width + bleed) * DPI), round((trim.height + 2 * bleed) * DPI))

    path = os.path.join(dist_dir, book.output_name("cover-wrap", trim, "pdf"))
    c = pdfcanvas.Canvas(path, pagesize=(width, height))
    c.setTitle(f"{book.title} — cover wrap ({trim.name})")
    c.setFillColor(HexColor(int(book.cover_bg, 16)))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.drawImage(ImageReader(panels["back"]), 0, 0, width=panel_w, height=height,
                preserveAspectRatio=False)
    c.drawImage(ImageReader(panels["front"]), (trim.width + bleed + spine) * INCH, 0,
                width=panel_w, height=height, preserveAspectRatio=False)
    c.showPage()
    c.save()
    return path


def _case(book, trim, pages, art_dir, render_dir, dist_dir):
    spine = trim.spine(pages)
    outer = trim.wrap + trim.bleed
    width = (2 * outer + 2 * trim.width + 2 * trim.hinge + spine) * INCH
    height = (2 * outer + trim.height) * INCH

    # rendered at board width only, so the art keeps its own proportions and bleeds
    # past the top and bottom board edges by however much taller than the trim it is
    panels = _panels(art_dir, os.path.join(render_dir, "case"), round(trim.width * DPI))
    px_w, px_h = ImageReader(panels["front"]).getSize()
    art_w = trim.width
    art_h = art_w * (px_h / float(px_w))
    art_y = outer - (art_h - trim.height) / 2.0

    back_x = outer
    front_x = outer + trim.width + trim.hinge + spine + trim.hinge

    path = os.path.join(dist_dir, book.output_name("cover-wrap", trim, "pdf"))
    c = pdfcanvas.Canvas(path, pagesize=(width, height))
    c.setTitle(f"{book.title} — case wrap ({trim.name})")
    c.setFillColor(HexColor(int(book.cover_bg, 16)))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    for x, side in ((back_x, "back"), (front_x, "front")):
        c.drawImage(ImageReader(panels[side]), x * INCH, art_y * INCH,
                    width=art_w * INCH, height=art_h * INCH, preserveAspectRatio=False)
    c.showPage()
    c.save()
    return path


BINDINGS = {"wrap": _wrap, "case": _case}


def build(book, render_dir, page_counts=None):
    """Render a cover for every trim. *page_counts* maps trim name to real page count."""
    if not has_art(book.art_dir):
        raise CoverArtMissing(
            f"{book.art_dir} needs front-cover.svg and back-cover.svg")
    fonts.register(book.raw.get("fonts"))
    page_counts = page_counts or {}
    outputs = []
    for trim in book.trims:
        pages = page_counts.get(trim.name, book.declared_pages)
        binding = BINDINGS.get(trim.binding)
        if binding is None:
            raise ValueError(f"unknown binding '{trim.binding}' for trim '{trim.name}'")
        outputs.append(binding(book, trim, pages, book.art_dir, render_dir, book.dist_dir))
    return outputs
