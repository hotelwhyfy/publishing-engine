"""The ``atlas`` template: one numbered entry per page, each with a computed figure.

For reference books whose unit is the page — a definition, its figure, its explanation,
one to a leaf. Entries are grouped into parts, and the front matter is fuller than the
other templates: half-title, title, copyright, epigraph, contents, then any number of
introductory sections, then part dividers and entry pages, then a colophon.

Figures are drawn by the book's own figure module — see :mod:`publishing_engine.figures`.
"""
from __future__ import annotations

import copy
import os

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import Frame, Paragraph

from .. import figures as figure_source
from .. import fonts, numbers, raster
from ..markup import paragraphs, to_html, to_reportlab
from ..page import CornerMarks, Sheet
from . import html_base

#: A figure is never allowed to take more than this share of the page height.
MAX_FIGURE_HEIGHT = 0.40


def entries_of(book):
    """The book's entries, accepting the older key name."""
    return book.raw.get("entry") or book.raw.get("axiom") or []


def parts_of(book):
    parts = {}
    for part in book.raw.get("part", []):
        part = dict(part)
        part.setdefault("roman", numbers.roman(part["n"]))
        parts[part["n"]] = part
    return parts


def front_sections(book):
    """Introductory flow pages: any ``[[front]]`` entries, else the older fixed pair."""
    sections = book.raw.get("front")
    if sections:
        return list(sections)
    return [book.raw[key] for key in ("preface", "notation") if key in book.raw]


def figure_key(entry):
    return entry.get("figure") or entry.get("graph")


def _render_figures(book, figures, render_dir):
    paths = {}
    for entry in entries_of(book):
        key = figure_key(entry)
        if key and key not in paths:
            out = os.path.join(render_dir, f"figure-{key}.png")
            paths[key] = raster.svg_string_to_png(figures.svg(key), out, width=1200)
    return paths


def build_pdf(book, dist_dir, render_dir):
    fonts.register(book.raw.get("fonts"))
    figures = figure_source.for_book(book)
    theme = book.theme
    entries = entries_of(book)
    parts = parts_of(book)
    by_part = {}
    for entry in entries:
        by_part.setdefault(entry.get("part", 1), []).append(entry)

    ink = fonts.color(theme.ink)
    accent = fonts.color(theme.accent)
    accent2 = fonts.color(theme.accent2)
    mute = fonts.color(theme.mute)
    caption_ink = fonts.color(theme.caption_ink)
    mono_ink = f"#{theme.mono_ink}"

    volume_word = numbers.in_words(book.volume).upper() if book.volume else ""
    series_caps = book.series_label.upper()

    body_style = ParagraphStyle("body", fontName=fonts.SERIF, fontSize=11, leading=16.4,
                                textColor=ink, alignment=TA_JUSTIFY, spaceAfter=8)
    formula_style = ParagraphStyle("formula", fontName=fonts.MONO, fontSize=11, leading=15,
                                   textColor=fonts.color(theme.mono_ink), alignment=TA_CENTER,
                                   spaceBefore=3, spaceAfter=7)
    caption_style = ParagraphStyle("caption", fontName=fonts.SERIF_I, fontSize=9, leading=12,
                                   textColor=caption_ink, alignment=TA_CENTER)

    def markup(text):
        return to_reportlab(text, mono=fonts.MONO, mono_color=mono_ink)

    def block_flow(block):
        if "p" in block:
            return Paragraph(markup(block["p"]), body_style)
        return Paragraph(markup(block["f"]), formula_style)

    outputs, page_counts = [], {}

    def one_trim(trim):
        name = book.output_name("interior", trim, "pdf")
        path = os.path.join(dist_dir, name)
        c = pdfcanvas.Canvas(path, pagesize=(0, 0))
        sheet = Sheet(c, trim, theme, frame=CornerMarks(), margin=46)
        c.setPageSize((sheet.pw, sheet.ph))
        title_line = book.title
        if book.series_label and volume_word:
            title_line = f"{book.title} - {book.series_label}, Volume {volume_word.title()}"
        c.setTitle(title_line)
        c.setAuthor(book.imprint)
        c.setSubject(f"{book.series_label} - {book.imprint}".strip(" -"))

        cx = sheet.tw / 2
        figure_png = _render_figures(book, figures, render_dir)

        def flows_in(x, width, top, bottom, flows):
            frame = Frame(x, bottom, width, top - bottom, leftPadding=0, rightPadding=0,
                          topPadding=0, bottomPadding=0, showBoundary=0)
            frame.addFromList([copy.copy(f) for f in flows], c)

        def hrule(y, half=46):
            sheet.broken_rule(cx, y, half=half, r=3.2, color=sheet.rule,
                              ornament=accent2, width=1)

        # -- pages ---------------------------------------------------------
        def page_halftitle():
            sheet.open(folio=False)
            c.setFillColor(ink)
            c.setFont(fonts.MONO_B, 30)
            c.drawCentredString(cx, sheet.th / 2 + 4, book.title.upper())
            c.setStrokeColor(accent)
            c.setLineWidth(1.4)
            c.line(cx - 46, sheet.th / 2 - 18, cx + 46, sheet.th / 2 - 18)
            sheet.close()

        def page_title():
            sheet.open(folio=False)
            if series_caps:
                label = f"{series_caps}   ·   VOLUME {volume_word}" if volume_word else series_caps
                sheet.tracked(cx, sheet.th - 150, label, fonts.SERIF_B, 9.5, accent, 2.6)
            c.setFillColor(ink)
            c.setFont(fonts.MONO_B if book.title_mono else fonts.SERIF_B, 52)
            c.drawCentredString(cx, sheet.th - 235, book.title.upper())
            c.setStrokeColor(accent)
            c.setLineWidth(2)
            c.line(cx - 78, sheet.th - 258, cx + 78, sheet.th - 258)
            safe = sheet.safe_width()
            c.setFillColor(ink)
            y = fonts.wrap_centred(c, cx, sheet.th - 290, book.subtitle, fonts.SERIF_I, 14.5, safe)
            c.setFillColor(mute)
            fonts.wrap_centred(c, cx, y - 22, book.tagline, fonts.SERIF, 11, safe)
            if book.imprint:
                sheet.tracked(cx, 150, book.imprint.upper(), fonts.SERIF, 10, mute, 2.4)
            sheet.close()

        def page_copyright():
            sheet.open(folio=False)
            sheet.diamond(cx, sheet.th - 150, 4, accent2)
            y = sheet.th - 186
            for text in book.raw.get("copyright", {}).get("lines", []):
                if not text:
                    y -= 6
                    continue
                reserved = "rights reserved" in text.lower()
                font = fonts.SERIF_B if text.isupper() else (fonts.SERIF_I if reserved else fonts.SERIF)
                color = accent if text.isupper() else (mute if reserved else ink)
                c.setFillColor(color)
                c.setFont(font, 10.5 if text.isupper() else 10)
                c.drawCentredString(cx, y, text)
                y -= 16
            sheet.close()

        def page_epigraph():
            sheet.open(folio=False)
            sheet.diamond(cx, sheet.th - 216, 4, accent2)
            c.setFillColor(ink)
            c.setFont(fonts.SERIF_I, 16)
            y = sheet.th - 278
            for line in book.epigraph.get("lines", []):
                c.drawCentredString(cx, y, line)
                y -= 26
            attribution = book.epigraph.get("attribution", "")
            if attribution:
                sheet.tracked(cx, y - 22, attribution.upper(), fonts.SERIF, 8.5, mute, 2)
            sheet.close()

        def page_contents():
            sheet.open(folio=False)
            sheet.tracked(cx, sheet.th - 72, "CONTENTS", fonts.SERIF_B, 10, accent, 2.4)
            hrule(sheet.th - 98)
            y = sheet.th - 140
            for index in sorted(by_part):
                part = parts.get(index, {"roman": numbers.roman(index), "label": ""})
                sheet.tracked(cx, y, f"PART {part['roman']} · {part['label']}".upper(),
                              fonts.SERIF_B, 9, accent2, 2.2)
                y -= 24
                for entry in by_part[index]:
                    c.setFillColor(accent)
                    c.setFont(fonts.MONO_B, 10)
                    c.drawString(sheet.margin + 8, y, f"{entry['n']:02d}")
                    c.setFillColor(ink)
                    c.setFont(fonts.SERIF, 11.5)
                    c.drawString(sheet.margin + 38, y, entry["title"])
                    y -= 19
                y -= 10
            sheet.close()

        def page_flow(section):
            sheet.open(folio=False)
            sheet.tracked(cx, sheet.th - 72, section.get("kicker", "").upper(),
                          fonts.SERIF_B, 10, accent, 2.4)
            c.setFillColor(ink)
            c.setFont(fonts.SERIF_B, 20)
            c.drawCentredString(cx, sheet.th - 100, section.get("title", ""))
            hrule(sheet.th - 118)
            flows = [Paragraph(markup(t), body_style) for t in paragraphs(section.get("body", ""))]
            flows_in(sheet.margin, sheet.cw, sheet.th - 140, 60, flows)
            sheet.close()

        def page_part(part):
            sheet.open(folio=False)
            mid = sheet.th / 2
            sheet.tracked(cx, mid + 64, f"PART {part['roman']}", fonts.SERIF_B, 12, accent2, 6)
            c.setFillColor(ink)
            c.setFont(fonts.MONO_B, 30)
            c.drawCentredString(cx, mid + 10, part["label"])
            c.setStrokeColor(accent)
            c.setLineWidth(2)
            c.line(cx - 60, mid - 12, cx + 60, mid - 12)
            c.setFillColor(mute)
            c.setFont(fonts.SERIF_I, 12)
            for i, line in enumerate(part.get("blurb", [])):
                c.drawCentredString(cx, mid - 44 - i * 18, line)
            sheet.close()

        def page_entry(entry):
            sheet.open()
            part = parts.get(entry.get("part", 1), {"roman": "", "label": ""})
            badge_w, badge_h = 46, 34
            badge_x = sheet.margin
            badge_y = sheet.th - 60 - badge_h
            c.setFillColor(sheet.badge)
            c.setStrokeColor(accent)
            c.setLineWidth(1.4)
            c.roundRect(badge_x, badge_y, badge_w, badge_h, 5, fill=1, stroke=1)
            c.setFillColor(accent)
            c.setFont(fonts.MONO_B, 19)
            c.drawCentredString(badge_x + badge_w / 2, badge_y + 10, f"{entry['n']:02d}")
            c.setFillColor(mute)
            c.setFont(fonts.SERIF_B, 8)
            c.drawString(badge_x + badge_w + 14, badge_y + badge_h - 10,
                         f"PART {part['roman']}  ·  {part['label'].upper()}".strip(" ·"))
            c.setFillColor(ink)
            c.setFont(fonts.SERIF_B, 19)
            c.drawString(badge_x + badge_w + 13, badge_y + 4, entry["title"])
            c.setStrokeColor(sheet.rule)
            c.setLineWidth(1)
            c.line(sheet.margin, badge_y - 12, sheet.tw - sheet.margin, badge_y - 12)

            key = figure_key(entry)
            base = 84
            height = 0
            if key:
                aspect = figures.aspect(key)
                width = sheet.cw
                height = width / aspect
                if height > MAX_FIGURE_HEIGHT * sheet.th:
                    height = MAX_FIGURE_HEIGHT * sheet.th
                    width = height * aspect
                c.drawImage(ImageReader(figure_png[key]), (sheet.tw - width) / 2, base,
                            width=width, height=height, preserveAspectRatio=True, mask="auto")
            if entry.get("caption"):
                cap = Paragraph(markup(entry["caption"]), caption_style)
                _, ch = cap.wrap(sheet.cw, 40)
                cap.drawOn(c, sheet.margin, base - 6 - ch)
            flows_in(sheet.margin, sheet.cw, badge_y - 22, base + height + 14,
                     [block_flow(b) for b in entry.get("blocks", [])])
            sheet.close()

        def page_colophon():
            sheet.open(folio=False)
            mid = sheet.th / 2
            sheet.diamond(cx, mid + 58, 4.5, accent2)
            c.setFillColor(ink)
            c.setFont(fonts.SERIF_I, 16)
            c.drawCentredString(cx, mid + 6, book.closing_line())
            c.setStrokeColor(accent)
            c.setLineWidth(1)
            c.line(cx - 46, mid - 22, cx + 46, mid - 22)
            if series_caps and volume_word:
                sheet.tracked(cx, mid - 58, f"VOLUME {volume_word} · {series_caps}",
                              fonts.SERIF_B, 10, accent, 2.2)
            if book.imprint:
                sheet.tracked(cx, mid - 78, book.imprint.upper(), fonts.SERIF, 10, mute, 2.4)
            sheet.close()

        # -- assemble ------------------------------------------------------
        page_halftitle()
        page_title()
        if "copyright" in book.raw:
            page_copyright()
        if book.epigraph.get("lines"):
            page_epigraph()
        if entries:
            page_contents()
        for section in front_sections(book):
            page_flow(section)
        for index in sorted(by_part):
            if index in parts:
                page_part(parts[index])
            for entry in by_part[index]:
                page_entry(entry)
        page_colophon()
        sheet.pad_to(book.min_pages)

        c.save()
        outputs.append(path)
        page_counts[trim.name] = sheet.n

    for trim in book.trims:
        one_trim(trim)
    return outputs, page_counts


EXTRA_CSS = """
  .undertitle { text-align:center; color:var(--mute); font-size:1rem; margin:.5em 0 0; }
  .kicker { text-align:center; letter-spacing:.2em; text-transform:uppercase;
    font-size:.68rem; color:var(--accent); margin:0 0 4px; }
  section.front { margin:40px 0; }
  section.front h2 { text-align:center; font-size:1.25rem; margin:0; }
  article.entry { margin:44px 0; padding-top:22px; border-top:1px solid rgba(0,0,0,.08); }
  .entry-head { display:flex; align-items:baseline; gap:16px; }
  .entry-n { font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace; font-weight:700;
    color:var(--accent); font-size:1.1rem; }
  .entry-title { font-size:1.25rem; font-weight:700; margin:0; }
  .entry-part { text-transform:uppercase; letter-spacing:.14em; font-size:.62rem;
    color:var(--mute); margin:0 0 2px; }
  .entry figure { margin:18px 0; text-align:center; }
  .entry figure svg { max-width:100%; height:auto; }
  figcaption { font-style:italic; color:var(--mute); font-size:.86rem; margin-top:.5em; }
  .formula { text-align:center; font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace;
    color:var(--mono-ink); margin:.6em 0; }
  .part-divider { text-align:center; margin:56px 0 8px; }
  .part-divider .label { font-weight:700; font-size:1.15rem; }
  .part-divider .n { text-transform:uppercase; letter-spacing:.24em; font-size:.66rem;
    color:var(--accent2); }
  p { margin:.7em 0; text-align:justify; hyphens:auto; }
  @media (max-width:600px) { p { text-align:left; } }
"""


def build_html(book, dist_dir):
    figures = figure_source.for_book(book)
    parts = parts_of(book)
    by_part = {}
    for entry in entries_of(book):
        by_part.setdefault(entry.get("part", 1), []).append(entry)

    chunks = []
    for section in front_sections(book):
        body = "".join(f"<p>{to_html(t)}</p>" for t in paragraphs(section.get("body", "")))
        chunks.append(
            f'<section class="front"><p class="kicker">{section.get("kicker", "")}</p>'
            f'<h2>{section.get("title", "")}</h2>{html_base.RULE}{body}</section>')

    for index in sorted(by_part):
        part = parts.get(index)
        if part:
            chunks.append(
                f'<div class="part-divider"><p class="n">Part {part["roman"]}</p>'
                f'<p class="label">{part["label"]}</p></div>')
        for entry in by_part[index]:
            blocks = "".join(
                f'<p>{to_html(b["p"])}</p>' if "p" in b else f'<p class="formula">{to_html(b["f"])}</p>'
                for b in entry.get("blocks", []))
            key = figure_key(entry)
            figure = ""
            if key:
                caption = (f'<figcaption>{to_html(entry["caption"])}</figcaption>'
                           if entry.get("caption") else "")
                figure = f'<figure>{figures.svg(key)}{caption}</figure>'
            label = f'PART {part["roman"]} · {part["label"]}' if part else ""
            chunks.append(
                f'<article class="entry"><p class="entry-part">{label}</p>'
                f'<div class="entry-head"><span class="entry-n">{entry["n"]:02d}</span>'
                f'<h2 class="entry-title">{entry["title"]}</h2></div>'
                f'{figure}{blocks}</article>')

    out = os.path.join(dist_dir, f"{book.slug}-interior.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html_base.document(book, "\n  ".join(chunks), EXTRA_CSS))
    return out
