"""Page geometry, furniture and the running cursor.

A :class:`Sheet` wraps a reportlab canvas and holds everything that is true of every
page of a book: how big the paper is, which way the bleed leans on this side of the
spine, where the text column sits, what the frame looks like, and how far down the page
the cursor has got.

Coordinates
-----------
The canvas is larger than the trim, because printing needs bleed. Rather than make
every template do that arithmetic, each page is opened with the origin already
translated to the bottom-left corner of the **trim**. So a template works in trim
coordinates — ``0..sheet.tw`` across, ``0..sheet.th`` up — and bleed takes care of
itself. Odd pages (rectos) bleed off the outer edge on the right, even pages (versos)
on the left, which is why the horizontal offset alternates.
"""
from __future__ import annotations

from reportlab.lib.pagesizes import inch

from . import fonts, numbers


class DoubleRule:
    """Two concentric rules with an ornament centred at the head. A classical frame."""

    inner_inset = 28

    def __call__(self, sheet, folio):
        c = sheet.canvas
        c.setStrokeColor(sheet.accent2)
        c.setLineWidth(1.0)
        c.rect(24, 24, sheet.tw - 48, sheet.th - 48, fill=0, stroke=1)
        c.setLineWidth(0.5)
        c.rect(28, 28, sheet.tw - 56, sheet.th - 56, fill=0, stroke=1)
        sheet.diamond(sheet.tw / 2, sheet.th - 40, 3.4, sheet.accent)
        if folio:
            c.setFillColor(sheet.mute)
            c.setFont(fonts.SERIF, 9)
            c.drawCentredString(sheet.tw / 2, 30, str(folio))


class CornerMarks:
    """A rule, a fainter inner rule, and a bracket at each corner. A technical frame."""

    inner_inset = 23

    def __call__(self, sheet, folio):
        c = sheet.canvas
        c.setStrokeColor(sheet.rule)
        c.setLineWidth(1.0)
        c.rect(18, 18, sheet.tw - 36, sheet.th - 36, fill=0, stroke=1)
        c.setStrokeColor(sheet.faint)
        c.setLineWidth(0.6)
        c.rect(23, 23, sheet.tw - 46, sheet.th - 46, fill=0, stroke=1)
        c.setFillColor(sheet.accent)
        for cx, cy, sx, sy in ((18, sheet.th - 18, 1, -1), (sheet.tw - 18, sheet.th - 18, -1, -1),
                               (18, 18, 1, 1), (sheet.tw - 18, 18, -1, 1)):
            c.saveState()
            c.translate(cx, cy)
            c.scale(sx, sy)
            c.rect(0, -1.1, 12, 1.1, fill=1, stroke=0)
            c.rect(-1.1, 0, 1.1, 12, fill=1, stroke=0)
            c.restoreState()
        if folio is not None:
            c.setFillColor(sheet.mute)
            c.setFont(fonts.MONO, 8.5)
            c.drawCentredString(sheet.tw / 2, 29, str(folio))


class Plain:
    """No frame at all."""

    inner_inset = 0

    def __call__(self, sheet, folio):
        if folio:
            c = sheet.canvas
            c.setFillColor(sheet.mute)
            c.setFont(fonts.SERIF, 9)
            c.drawCentredString(sheet.tw / 2, 30, str(folio))


FRAMES = {"double-rule": DoubleRule, "corner-marks": CornerMarks, "plain": Plain}


class Sheet:
    """The canvas, the geometry, and the cursor for one trim of one book."""

    def __init__(self, canvas, trim, theme, *, frame=None, margin=54, top=76, bottom=60):
        self.canvas = canvas
        self.trim = trim
        self.tw = trim.width * inch
        self.th = trim.height * inch
        self.bleed = trim.bleed * inch
        self.pw = self.tw + self.bleed
        self.ph = self.th + 2 * self.bleed
        self.margin = margin
        self.cw = self.tw - 2 * margin
        self.top = self.th - top
        self.bottom = bottom
        self.frame = frame or DoubleRule()

        self.paper_color = fonts.color(theme.paper)
        self.ink = fonts.color(theme.ink)
        self.accent = fonts.color(theme.accent)
        self.accent2 = fonts.color(theme.accent2)
        self.mute = fonts.color(theme.mute)
        self.rule = fonts.color(theme.rule)
        self.faint = fonts.color(theme.faint)
        self.badge = fonts.color(theme.badge)

        self.n = 0
        self.y = self.top
        self._open = False

    # -- geometry ---------------------------------------------------------
    def safe_width(self, padding=28):
        """The widest a centred line may be and stay clear of the frame."""
        return self.tw - 2 * self.frame.inner_inset - padding

    # -- page lifecycle ---------------------------------------------------
    def _offsets(self):
        self.n += 1
        return (0 if self.n % 2 == 1 else self.bleed), self.bleed

    def open(self, folio=True):
        """Start a page: lay the paper, translate to trim, draw the frame."""
        x0, y0 = self._offsets()
        c = self.canvas
        c.setFillColor(self.paper_color)
        c.rect(0, 0, self.pw, self.ph, fill=1, stroke=0)
        c.saveState()
        c.translate(x0, y0)
        self.frame(self, self.n if folio else None)
        self.y = self.top
        self._open = True

    def close(self):
        self.canvas.restoreState()
        self.canvas.showPage()
        self._open = False

    def blank(self):
        """A framed page with nothing on it — used to pad out a signature."""
        self.open(folio=False)
        self.close()

    def bleed_page(self, png):
        """A page filled edge to edge by one image: no frame, no folio, no margins."""
        self._offsets()
        self.canvas.drawImage(png, 0, 0, width=self.pw, height=self.ph,
                              preserveAspectRatio=False)
        self.canvas.showPage()

    def ensure(self, height):
        """Break to a new page if *height* will not fit below the cursor."""
        if self.y - height < self.bottom:
            self.close()
            self.open()

    def pad_to(self, minimum, even=True):
        """Add blank pages until the count reaches *minimum* and, if asked, is even."""
        while self.n < minimum or (even and self.n % 2 != 0):
            self.blank()

    # -- drawing primitives -----------------------------------------------
    def tracked(self, x, y, text, font, size, color, tracking):
        """A letter-spaced centred string. reportlab has no tracking, so space by hand."""
        c = self.canvas
        c.setFont(font, size)
        c.setFillColor(color)
        widths = [c.stringWidth(ch, font, size) for ch in text]
        total = sum(widths) + tracking * max(len(text) - 1, 0)
        cx = x - total / 2
        for ch, w in zip(text, widths):
            c.drawString(cx, y, ch)
            cx += w + tracking

    def diamond(self, cx, cy, r=3.4, color=None):
        c = self.canvas
        c.setFillColor(color or self.accent2)
        c.saveState()
        c.translate(cx, cy)
        c.rotate(45)
        c.rect(-r, -r, 2 * r, 2 * r, fill=1, stroke=0)
        c.restoreState()

    def broken_rule(self, cx, y, half=52, gap=11, r=2.6, color=None, ornament=None, width=0.8):
        """Two short rules with an ornament in the gap between them.

        *color* draws the rules; *ornament* draws the mark between them, and defaults
        to the rule colour when it is not given separately.
        """
        c = self.canvas
        color = color or self.accent2
        c.setStrokeColor(color)
        c.setLineWidth(width)
        c.line(cx - half, y, cx - gap, y)
        c.line(cx + gap, y, cx + half, y)
        self.diamond(cx, y, r, ornament or color)

    # -- shared front and back matter -------------------------------------
    def title_page(self, book):
        """Series line, title, rule, subtitle, epigraph, imprint."""
        self.open(folio=False)
        c = self.canvas
        cx = self.tw / 2
        if book.series_label:
            label = book.series_label.upper()
            if book.volume:
                label += f"   ·   VOLUME {numbers.in_words(book.volume).upper()}"
            self.tracked(cx, self.th - 160, label, fonts.SERIF, 9.5, self.mute, 2.6)
        c.setFillColor(self.accent2)
        c.setFont(fonts.SERIF_B, 36)
        y = self.th - 250
        for line in book.title_lines:
            c.drawCentredString(cx, y, line)
            y -= 44
        self.broken_rule(cx, y + 10, half=60, r=3.6, width=1.2)

        safe = self.safe_width()
        if book.subtitle:
            c.setFillColor(self.ink)
            y = fonts.wrap_centred(c, cx, y - 22, book.subtitle, fonts.SERIF_I, 14.5, safe)
        epigraph = (book.epigraph.get("lines") or [""])[0]
        if epigraph:
            c.setFillColor(self.mute)
            fonts.wrap_centred(c, cx, 168, epigraph, fonts.SERIF_I, 11, safe, anchor="bottom")
        if book.imprint:
            self.tracked(cx, 132, book.imprint.upper(), fonts.SERIF, 9.5, self.mute, 2.4)
        self.close()

    def copyright_page(self, lines):
        """The rights page: an ornament, then the lines the book gives, centred.

        A line in capitals is set as a heading, and one mentioning reserved rights is
        set apart in italic — the two conventions of the form. An empty string is a gap.
        """
        if not lines:
            return
        self.open(folio=False)
        c = self.canvas
        cx = self.tw / 2
        self.diamond(cx, self.th - 150, 4, self.accent2)
        y = self.th - 186
        for text in lines:
            if not text:
                y -= 6
                continue
            reserved = "rights reserved" in text.lower()
            font = (fonts.SERIF_B if text.isupper()
                    else (fonts.SERIF_I if reserved else fonts.SERIF))
            color = (self.accent if text.isupper()
                     else (self.mute if reserved else self.ink))
            c.setFillColor(color)
            c.setFont(font, 10.5 if text.isupper() else 10)
            for line in fonts.wrap_lines(text, font, 10, self.safe_width()):
                c.drawCentredString(cx, y, line)
                y -= 14
            y -= 2
        self.close()

    def colophon(self, book):
        """The closing page: ornament, closing line, rule, imprint."""
        self.open(folio=False)
        c = self.canvas
        cx, mid = self.tw / 2, self.th / 2
        self.diamond(cx, mid + 54, 4.2, self.accent2)
        c.setFillColor(self.ink)
        c.setFont(fonts.SERIF_I, 15)
        c.drawCentredString(cx, mid + 2, book.closing_line())
        c.setStrokeColor(self.accent2)
        c.setLineWidth(1)
        c.line(cx - 46, mid - 22, cx + 46, mid - 22)
        if book.imprint:
            self.tracked(cx, mid - 58, book.imprint.upper(), fonts.SERIF, 10, self.mute, 2.6)
        self.close()
