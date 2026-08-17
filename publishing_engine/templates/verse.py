"""The ``verse`` template: sections of short numbered entries.

For proverbs, aphorisms, rules, clauses — anything that reads as a numbered list rather
than continuous prose. Entry numbers hang in their own gutter, so every line of an
entry, first and continuation alike, starts at the same left edge. Numbering is
generated at layout time and restarts in each section.
"""
from __future__ import annotations

import os

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import Paragraph

from .. import figures as figure_source
from .. import fonts
from ..markup import to_html, to_reportlab
from ..page import DoubleRule, Sheet
from ..sources.verse import parse
from . import figure, html_base

#: Width of the hanging gutter the entry number sits in.
GUTTER = 18
#: A figure is never allowed to take more than this share of the page height.
MAX_FIGURE_HEIGHT = 0.52


def build_pdf(book, dist_dir, render_dir):
    fonts.register(book.raw.get("fonts"))
    sections = parse(book.content_path)
    figures = figure_source.for_book(book)
    for i, block in enumerate(b for s in sections for b in s["entries"]
                              if isinstance(b, dict)):
        block["png"] = figure.rasterise(block, book, figures, render_dir, i)
    theme = book.theme

    ink = fonts.color(theme.ink)
    accent = fonts.color(theme.accent)
    mono_ink = f"#{theme.mono_ink}"

    caption_style = ParagraphStyle(
        "caption", fontName=fonts.SERIF_I, fontSize=9, leading=12,
        textColor=fonts.color(theme.caption_ink), alignment=TA_CENTER)
    entry_style = ParagraphStyle(
        "entry", fontName=fonts.SERIF, fontSize=11.5, leading=17, textColor=ink,
        alignment=TA_JUSTIFY, spaceAfter=8,
        leftIndent=GUTTER, bulletIndent=GUTTER - 6, bulletAnchor="end",
        bulletFontName=fonts.SERIF_B, bulletFontSize=8.5,
        bulletColor=accent, bulletOffsetY=1.5)

    outputs, page_counts = [], {}

    def one_trim(trim):
        name = book.output_name("interior", trim, "pdf")
        path = os.path.join(dist_dir, name)
        c = pdfcanvas.Canvas(path, pagesize=(0, 0))
        sheet = Sheet(c, trim, theme, frame=DoubleRule())
        c.setPageSize((sheet.pw, sheet.ph))
        c.setTitle(book.title)
        c.setAuthor(book.imprint)

        def heading(text):
            sheet.y -= 12
            sheet.ensure(52)
            label = text.upper()
            size, tracking = fonts.fit_tracking(label, fonts.SERIF_B, 13, 3.0, sheet.cw)
            sheet.tracked(sheet.tw / 2, sheet.y - 6, label, fonts.SERIF_B, size, accent, tracking)
            sheet.broken_rule(sheet.tw / 2, sheet.y - 19)
            sheet.y -= 38

        def markup(text):
            return to_reportlab(text, mono=fonts.MONO, mono_color=mono_ink)

        def entry(number, text):
            para = Paragraph(markup(text), entry_style, bulletText=str(number))
            _, height = para.wrap(sheet.cw, sheet.th)
            sheet.ensure(height + entry_style.spaceAfter)
            para.drawOn(c, sheet.margin, sheet.y - height)
            sheet.y -= height + entry_style.spaceAfter

        sheet.title_page(book)

        sheet.open()
        for section in sections:
            if section["name"]:
                heading(section["name"])
            number = 0
            for item in section["entries"]:
                if isinstance(item, dict):
                    if item["full"]:
                        sheet.close()
                        sheet.bleed_page(ImageReader(item["png"]))
                        sheet.open()
                    else:
                        figure.place(sheet, item["png"], item["caption"], caption_style,
                                     markup, MAX_FIGURE_HEIGHT)
                else:
                    number += 1
                    entry(number, item)
        sheet.close()

        sheet.colophon(book)
        sheet.pad_to(book.min_pages)

        c.save()
        outputs.append(path)
        page_counts[trim.name] = sheet.n

    for trim in book.trims:
        one_trim(trim)
    return outputs, page_counts


EXTRA_CSS = """
  .rule { margin:22px auto; }   /* entries sit closer together than flowing prose */
  section.entries { margin:48px 0; }
  h2 { text-align:center; font-size:1.2rem; letter-spacing:.2em; text-transform:uppercase;
    color:var(--accent); font-weight:700; margin:0 0 6px; }
  h2::after { content:"\\25C6"; display:block; color:var(--accent2); font-size:.6rem;
    margin:8px auto 0; }
  p.entry { margin:.6em 0; text-align:justify; hyphens:auto;
    display:grid; grid-template-columns:1.9em 1fr; }
  .n { color:var(--accent); font-weight:700; font-size:.72em; vertical-align:.4em;
    text-align:right; padding-right:.7em; }
  @media (max-width:560px) { p.entry { text-align:left; } }
"""


def _relative(src):
    """Content paths are relative to the book; the HTML is written one level down."""
    if src.startswith(("http://", "https://", "/", "../")):
        return src
    return "../" + src


def build_html(book, dist_dir):
    sections = parse(book.content_path)
    figures = figure_source.for_book(book)
    parts = []
    for section in sections:
        rendered, number = [], 0
        for item in section["entries"]:
            if isinstance(item, dict):
                rendered.append(figure.html(item, figures, _relative))
            else:
                number += 1
                rendered.append(
                    f'<p class="entry"><span class="n">{number}</span>{to_html(item)}</p>')
        head = f'<h2>{section["name"]}</h2>' if section["name"] else ""
        parts.append(f'<section class="entries">{head}{"".join(rendered)}</section>')

    out = os.path.join(dist_dir, f"{book.slug}-interior.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html_base.document(book, "\n".join(parts), EXTRA_CSS))
    return out
