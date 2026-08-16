"""The ``prose`` template: continuous prose with headings, pull-quotes and figures.

Title page, a flowing body, a colophon. Body paragraphs run across a page boundary
rather than jumping whole, which keeps the foot of each page even. A heading never
strands at the foot of a page: the space its following block needs is reserved past it,
and if that will not fit, the heading moves to the next page. Pull-quotes never split.
"""
from __future__ import annotations

import os

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import Paragraph

from .. import fonts, raster
from ..markup import to_html, to_reportlab
from ..page import DoubleRule, Sheet
from ..sources.prose import parse
from . import html_base

#: A figure is never allowed to take more than this share of the page height.
MAX_FIGURE_HEIGHT = 0.52


def _prepare_images(blocks, book, render_dir):
    """Rasterise each image once, at the resolution its placement needs."""
    for i, block in enumerate(blocks):
        if block["type"] != "image":
            continue
        src = block["src"]
        path = src if os.path.isabs(src) else os.path.join(book.dir, src)
        out = os.path.join(render_dir, f"image-{i}.png")
        if block["full"]:
            # stretched to fill the page, so it is rendered at the page's own proportion
            block["png"] = raster.prepare(path, out, width=1600, height=2576)
        else:
            block["png"] = raster.prepare(path, out, width=1400)


def build_pdf(book, dist_dir, render_dir):
    fonts.register(book.raw.get("fonts"))
    blocks = parse(book.content_path)
    _prepare_images(blocks, book, render_dir)
    theme = book.theme

    ink = fonts.color(theme.ink)
    accent = fonts.color(theme.accent)
    caption_ink = fonts.color(theme.caption_ink)
    mono_ink = f"#{theme.mono_ink}"

    body_style = ParagraphStyle(
        "body", fontName=fonts.SERIF, fontSize=11.5, leading=17, textColor=ink,
        alignment=TA_JUSTIFY, spaceAfter=8, allowWidows=0, allowOrphans=0)
    quote_style = ParagraphStyle(
        "quote", fontName=fonts.SERIF_I, fontSize=13, leading=18, textColor=accent,
        alignment=TA_CENTER, spaceBefore=6, spaceAfter=6)
    caption_style = ParagraphStyle(
        "caption", fontName=fonts.SERIF_I, fontSize=9, leading=12,
        textColor=caption_ink, alignment=TA_CENTER)

    #: lines of body a heading must be able to keep with it
    orphan = 3 * body_style.leading

    outputs, page_counts = [], {}

    def markup(text):
        return to_reportlab(text, mono=fonts.MONO, mono_color=mono_ink)

    def one_trim(trim):
        name = book.output_name("interior", trim, "pdf")
        path = os.path.join(dist_dir, name)
        c = pdfcanvas.Canvas(path, pagesize=(0, 0))
        sheet = Sheet(c, trim, theme, frame=DoubleRule())
        c.setPageSize((sheet.pw, sheet.ph))
        c.setTitle(book.title)
        c.setAuthor(book.imprint)

        def reserve(nxt):
            """How much room the block after a heading needs, so it is not left alone."""
            if nxt is None:
                return 0
            kind = nxt["type"]
            if kind == "p":                    # body splits, so a few lines are enough
                return min(Paragraph(markup(nxt["text"]), body_style).wrap(sheet.cw, sheet.th)[1],
                           orphan)
            if kind == "quote":                # never splits — reserve the whole of it
                return (Paragraph(markup(nxt["text"]), quote_style).wrap(sheet.cw, sheet.th)[1]
                        + quote_style.spaceAfter)
            if kind == "subheading":
                return 30 + orphan
            if kind == "image":
                return 0 if nxt["full"] else orphan
            return orphan

        def heading(text, keep=0):
            sheet.y -= 12
            sheet.ensure(52 + keep)
            label = text.upper()
            size, tracking = fonts.fit_tracking(label, fonts.SERIF_B, 13, 3.0, sheet.cw)
            sheet.tracked(sheet.tw / 2, sheet.y - 6, label, fonts.SERIF_B, size, accent, tracking)
            sheet.broken_rule(sheet.tw / 2, sheet.y - 19)
            sheet.y -= 38

        def subheading(text, keep=0):
            sheet.y -= 6
            sheet.ensure(30 + keep)
            sheet.tracked(sheet.tw / 2, sheet.y - 4, text.upper(), fonts.SERIF_B, 10,
                          sheet.accent2, 2.0)
            sheet.y -= 24

        def paragraph(style, text, split=True):
            para = Paragraph(markup(text), style)
            for _ in range(64):
                available = sheet.y - sheet.bottom
                _, height = para.wrap(sheet.cw, sheet.th)
                if height <= available:
                    break
                if split:
                    parts = para.split(sheet.cw, available) if available >= 3 * style.leading else []
                    if len(parts) == 2:
                        head, para = parts
                        _, hh = head.wrap(sheet.cw, sheet.th)
                        head.drawOn(c, sheet.margin, sheet.y - hh)
                sheet.close()
                sheet.open()
            _, height = para.wrap(sheet.cw, sheet.th)
            para.drawOn(c, sheet.margin, sheet.y - height)
            sheet.y -= height + style.spaceAfter

        def section_break():
            sheet.ensure(30)
            sheet.y -= 8
            sheet.diamond(sheet.tw / 2, sheet.y, 3.2)
            sheet.y -= 20

        def figure(block):
            reader = ImageReader(block["png"])
            iw, ih = reader.getSize()
            aspect = iw / float(ih)
            width = sheet.cw
            height = width / aspect
            if height > MAX_FIGURE_HEIGHT * sheet.th:
                height = MAX_FIGURE_HEIGHT * sheet.th
                width = height * aspect

            caption_height = 0
            if block["caption"]:
                cap = Paragraph(markup(block["caption"]), caption_style)
                _, caption_height = cap.wrap(sheet.cw, 60)

            sheet.ensure(height + (caption_height + 6 if caption_height else 0) + 12)
            sheet.y -= 6
            c.drawImage(reader, (sheet.tw - width) / 2, sheet.y - height,
                        width=width, height=height, preserveAspectRatio=True, mask="auto")
            sheet.y -= height
            if block["caption"]:
                cap = Paragraph(markup(block["caption"]), caption_style)
                _, ch = cap.wrap(sheet.cw, 60)
                cap.drawOn(c, sheet.margin, sheet.y - 6 - ch)
                sheet.y -= 6 + ch
            sheet.y -= 8

        sheet.title_page(book)

        sheet.open()
        for i, block in enumerate(blocks):
            kind = block["type"]
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            if kind == "image":
                if block["full"]:
                    sheet.close()
                    sheet.bleed_page(ImageReader(block["png"]))
                    sheet.open()
                else:
                    figure(block)
            elif kind == "heading":
                heading(block["text"], reserve(nxt))
            elif kind == "subheading":
                subheading(block["text"], reserve(nxt))
            elif kind == "quote":
                paragraph(quote_style, block["text"], split=False)
            elif kind == "break":
                section_break()
            else:
                paragraph(body_style, block["text"])
        sheet.close()

        sheet.colophon(book)
        sheet.pad_to(book.min_pages)

        c.save()
        outputs.append(path)
        page_counts[trim.name] = sheet.n

    for trim in book.trims:
        one_trim(trim)
    # each trim holds a different amount of text, so each spine is sized from its own count
    return outputs, page_counts


EXTRA_CSS = """
  h2 { text-align:center; font-size:1.2rem; letter-spacing:.2em; text-transform:uppercase;
    color:var(--accent); font-weight:700; margin:44px 0 6px; }
  h2::after { content:"\\25C6"; display:block; color:var(--accent2); font-size:.6rem;
    margin:8px auto 0; }
  h3 { text-align:center; font-size:.92rem; letter-spacing:.16em; text-transform:uppercase;
    color:var(--accent2); font-weight:700; margin:24px 0 4px; }
  h2, h3 { break-after:avoid; page-break-after:avoid; }
  p { margin:.7em 0; text-align:justify; hyphens:auto; orphans:3; widows:3; }
  blockquote { margin:1.2em auto; max-width:44ch; text-align:center; font-style:italic;
    font-size:1.16rem; color:var(--accent); border:0; }
  figure { margin:1.6em 0; text-align:center; }
  figure img { max-width:100%; height:auto; }
  figure.plate img { width:100%; }
  figcaption { font-style:italic; color:var(--mute); font-size:.86rem; margin-top:.5em; }
  @media (max-width:560px) { p { text-align:left; } }
"""


def _relative(src):
    """Content paths are relative to the book; the HTML is written one level down."""
    if src.startswith(("http://", "https://", "/", "../")):
        return src
    return "../" + src


def build_html(book, dist_dir):
    blocks = parse(book.content_path)
    parts = []
    for block in blocks:
        kind = block["type"]
        if kind == "heading":
            parts.append(f'<h2>{to_html(block["text"])}</h2>')
        elif kind == "subheading":
            parts.append(f'<h3>{to_html(block["text"])}</h3>')
        elif kind == "p":
            parts.append(f'<p>{to_html(block["text"])}</p>')
        elif kind == "quote":
            parts.append(f'<blockquote>{to_html(block["text"])}</blockquote>')
        elif kind == "break":
            parts.append(html_base.RULE)
        elif kind == "image":
            src = _relative(block["src"])
            if block["full"]:
                parts.append(f'<figure class="plate"><img src="{src}" alt=""></figure>')
            else:
                caption = (f'<figcaption>{to_html(block["caption"])}</figcaption>'
                           if block["caption"] else "")
                parts.append(f'<figure><img src="{src}" alt="{block["caption"]}">{caption}</figure>')

    out = os.path.join(dist_dir, f"{book.slug}-interior.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html_base.document(book, "\n  ".join(parts), EXTRA_CSS))
    return out
