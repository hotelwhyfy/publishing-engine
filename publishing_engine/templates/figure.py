"""Resolving and placing an image block, shared by the flowing templates.

An image in content is either a file the book ships (``art/plate.svg``) or a figure the
book declares (``plot:limit``). Both end up as a raster placed in the column, so the
difference is resolved once, here.
"""
from __future__ import annotations

import os

from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph

from .. import raster

#: How a declared figure is referred to from content.
PLOT_PREFIX = "plot:"


def is_declared(src):
    return str(src).startswith(PLOT_PREFIX)


def declared_name(src):
    return str(src)[len(PLOT_PREFIX):].strip()


def rasterise(block, book, figures, render_dir, index):
    """Return a PNG path for *block*, drawing a declared figure if that is what it is."""
    src = block["src"]
    full = block.get("full")
    if is_declared(src):
        name = declared_name(src)
        out = os.path.join(render_dir, f"plot-{name}-{'full' if full else 'inline'}.png")
        return raster.svg_string_to_png(figures.svg(name), out,
                                        width=1600 if full else 1400)
    path = src if os.path.isabs(src) else os.path.join(book.dir, src)
    out = os.path.join(render_dir, f"image-{index}.png")
    if full:
        # stretched to fill the page, so it is rendered at the page's own proportion
        return raster.prepare(path, out, width=1600, height=2576)
    return raster.prepare(path, out, width=1400)


def place(sheet, png, caption, caption_style, markup, max_share):
    """Draw a figure at column width with its caption, breaking the page if it will not fit.

    A figure taller than *max_share* of the page is scaled down **by height**, so it ends
    up narrower than the column — which is the usual reason a figure looks smaller than
    expected. Keep art close to the column's own proportion to fill it.
    """
    reader = ImageReader(png)
    iw, ih = reader.getSize()
    aspect = iw / float(ih)
    width = sheet.cw
    height = width / aspect
    if height > max_share * sheet.th:
        height = max_share * sheet.th
        width = height * aspect

    caption_height = 0
    if caption:
        para = Paragraph(markup(caption), caption_style)
        _, caption_height = para.wrap(sheet.cw, 60)

    sheet.ensure(height + (caption_height + 6 if caption_height else 0) + 12)
    sheet.y -= 6
    sheet.canvas.drawImage(reader, (sheet.tw - width) / 2, sheet.y - height,
                           width=width, height=height, preserveAspectRatio=True,
                           mask="auto")
    sheet.y -= height
    if caption:
        para = Paragraph(markup(caption), caption_style)
        _, ch = para.wrap(sheet.cw, 60)
        para.drawOn(sheet.canvas, sheet.margin, sheet.y - 6 - ch)
        sheet.y -= 6 + ch
    sheet.y -= 8


def html(block, figures, relative):
    """Render an image block for the reading HTML.

    A declared figure is embedded as inline SVG rather than linked, so the reading copy
    stays a single self-contained file with nothing to rasterise.
    """
    from ..markup import to_html

    caption = (f'<figcaption>{to_html(block["caption"])}</figcaption>'
               if block.get("caption") else "")
    if is_declared(block["src"]):
        svg = figures.svg(declared_name(block["src"]))
        cls = ' class="plate"' if block.get("full") else ""
        return f'<figure{cls}>{svg}{caption}</figure>'
    src = relative(block["src"])
    if block.get("full"):
        return f'<figure class="plate"><img src="{src}" alt=""></figure>'
    return f'<figure><img src="{src}" alt="{block.get("caption", "")}">{caption}</figure>'
